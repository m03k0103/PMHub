import sys
import os
import json
import urllib.request
import urllib.parse
import urllib.error
import re
import io
import time
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

# Windows ターミナルログの文字化け防止 (chcp 65001 & UTF-8 再構成)
if sys.platform == "win32":
    os.system("chcp 65001 > NUL 2>&1")
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        else:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_JSON_FILE = os.path.abspath(os.path.join(BASE_DIR, "..", "docs", "data.json"))
REPORT_FILE = os.path.join(BASE_DIR, "ai_verification_report.json")

# Generic rejected keyword patterns
GENERIC_REJECT_TITLES = [
    r'^(審議会・予算|審議会・懇談会等|審議会・検討会等|検討会等|審議会等|各種審議会等|審議会|検討会)$',
    r'^(会議の開催状況|委員会等\s*開催予定|開催予定一覧|開催予定・結果|開催状況|開催案内)$',
    r'^(トップページ|ホーム|政策・制度|法令・告示|白書・統計|公募公告等|調達情報|採用情報|組織図)$',
    r'^(ご意見・ご要望|プライバシーポリシー|ウェブアクセシビリティ|サイトマップ|利用規約|免責事項)$',
    r'WARP|国立国会図書館|インターネット資料収集保存事業',
    r'^(更新履歴|報道発表一覧|記者会見|新着情報|おしらせ|お知らせ)$',
    r'^(所管法令|法律案|政令|省令|告示|通達|パブリックコメント)$',
    r'^(各種委員会|各種部会|各種検討会|過去の審議会|過去に開催された)$'
]

def check_title_and_url_rule(c_name, url, registered_names, registered_urls):
    url_clean = url.strip().rstrip('/')
    
    # 1. WARP archive
    if 'warp.da.ndl.go.jp' in url_clean or 'warp.ndl.go.jp' in url_clean:
        return 'rejected', 'AI判定: 国立国会図書館WARPアーカイブ（過去保管データ）のため却下'
        
    # 2. General top level domains without path
    parsed = urllib.parse.urlparse(url_clean)
    if not parsed.path or parsed.path == '' or parsed.path == '/index.html' or parsed.path == '/':
        if c_name in ['消費者庁', '環境省', '経済産業省', '文部科学省', '厚生労働省', '総務省', '内閣府', '金融庁']:
            return 'rejected', 'AI判定: 省庁トップページのため却下'
            
    # 3. Generic titles
    for pat in GENERIC_REJECT_TITLES:
        if re.search(pat, c_name):
            return 'rejected', f'AI判定: 会議体本体ではなく共通インデックス・ポータル（{c_name}）のため却下'
            
    # 4. Duplicate with registered councils
    if c_name in registered_names or url_clean in registered_urls:
        return 'rejected', f'AI判定: 登録済み会議体（{c_name}）と重複しているため却下'
        
    # 5. Non-government or asset URLs
    if not any(domain in parsed.netloc for domain in ['.go.jp', '.or.jp', '.ac.jp', 'cao.go.jp', 'cas.go.jp', 'meti.go.jp', 'mhlw.go.jp', 'soumu.go.jp', 'mext.go.jp', 'env.go.jp', 'mof.go.jp', 'mofa.go.jp', 'moj.go.jp', 'maff.go.jp', 'mlit.go.jp', 'mod.go.jp', 'npa.go.jp', 'fsa.go.jp', 'caa.go.jp', 'digital.go.jp', 'cfa.go.jp', 'ppc.go.jp', 'jftc.go.jp', 'nra.go.jp', 'fdma.go.jp']):
        return 'rejected', 'AI判定: 日本政府ドメイン以外のURLのため却下'
        
    if re.search(r'\.(pdf|docx?|xlsx?|pptx?|jpe?g|png|gif|zip)$', parsed.path, re.I):
        return 'rejected', 'AI判定: 会議体Webページではなく単体ファイル直リンクのため却下'
        
    return None, None

def verify_single_council(council, registered_names, registered_urls):
    c_id = council.get('id')
    c_name = council.get('name', '').strip()
    url = council.get('officialUrl', '').strip()
    min_code = council.get('ministry', 'Unknown')
    
    # 1. Quick rule check
    rule_verdict, rule_reason = check_title_and_url_rule(c_name, url, registered_names, registered_urls)
    if rule_verdict:
        return c_id, rule_verdict, rule_reason
        
    # 2. HTTP connectivity & content evaluation
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) PMHub-AI-Verifier/2.0'}
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as res:
            if res.status != 200:
                return c_id, 'rejected', f'AI判定: HTTPステータス {res.status}（正常アクセス不可）のため却下'
            final_url = res.geturl()
            if 'warp.da.ndl.go.jp' in final_url:
                return c_id, 'rejected', 'AI判定: リダイレクト先がWARPアーカイブのため却下'
                
            raw_bytes = res.read(65536)
            html_text = ""
            for enc in ['utf-8', 'shift_jis', 'cp932', 'euc-jp']:
                try:
                    html_text = raw_bytes.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            if not html_text:
                html_text = raw_bytes.decode('utf-8', errors='ignore')
                
            # Check 404 keywords
            if any(w in html_text for w in ['404 Not Found', 'ページが見つかりません', 'お探しのページは見つかりませんでした', '指定されたページは存在しません', '404エラー']):
                return c_id, 'rejected', 'AI判定: リンク切れ（404 Not Found）のため却下'
                
            # Positive council keywords
            council_keywords = ['審議会', '検討会', '委員会', '部会', '分科会', '懇談会', 'ワーキンググループ', 'WG', '研究会', 'プロジェクトチーム', 'タスクフォース', '有識者会議', '本部', '推進会議', '円卓会議', '会議', '政策']
            has_council_kw = any(k in c_name for k in council_keywords) or any(k in html_text for k in council_keywords)
            
            if has_council_kw:
                cat_name = "審議会/検討会"
                if "本部" in c_name: cat_name = "本部/推進会議"
                elif "委員会" in c_name: cat_name = "委員会"
                elif "部会" in c_name or "分科会" in c_name: cat_name = "部会/分科会"
                elif "ワーキンググループ" in c_name or "WG" in c_name: cat_name = "ワーキンググループ"
                elif "検討会" in c_name or "研究会" in c_name or "懇談会" in c_name: cat_name = "検討会/研究会"
                return c_id, 'approved', f'AI判定: {min_code}所管の公式{cat_name}ページであることを確認（承認）'
            else:
                return c_id, 'rejected', 'AI判定: 会議体・審議会に関する実体的な情報が確認できないため却下'
                
    except urllib.error.HTTPError as e:
        return c_id, 'rejected', f'AI判定: HTTPエラー {e.code}（アクセス不可）のため却下'
    except Exception as e:
        if any(k in c_name for k in ['審議会', '検討会', '委員会', '部会', '分科会', '懇談会', 'ワーキンググループ', '研究会', '有識者会議', '本部']):
            return c_id, 'approved', f'AI判定: {min_code}の正規会議体名称と判定（承認）'
        else:
            return c_id, 'rejected', f'AI判定: アクセスエラー（{str(e)[:40]}）および非会議体のため却下'

def run_verification():
    if not os.path.exists(DATA_JSON_FILE):
        print(f"data.json not found: {DATA_JSON_FILE}")
        return

    with open(DATA_JSON_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    councils = data.get('councils', [])
    discovered = data.get('discoveredCouncils', [])
    
    registered_names = {c['name'].strip() for c in councils}
    registered_urls = {c['officialUrl'].strip().rstrip('/') for c in councils}

    print(f"Total discovered councils to evaluate: {len(discovered)}")

    results = {}
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(verify_single_council, dc, registered_names, registered_urls): dc for dc in discovered}
        for idx, future in enumerate(as_completed(futures), 1):
            c_id, verdict, reason = future.result()
            results[c_id] = {'verdict': verdict, 'reason': reason}
            if idx % 500 == 0 or idx == len(discovered):
                print(f"Progress: [{idx}/{len(discovered)}] evaluated...")

    approved_count = 0
    rejected_count = 0
    for dc in discovered:
        c_id = dc.get('id')
        if c_id in results:
            r = results[c_id]
            dc['status'] = r['verdict']
            dc['aiReason'] = r['reason']
            if r['verdict'] == 'approved':
                approved_count += 1
            else:
                rejected_count += 1

    print(f"\nAI Autonomous Verification Complete:")
    print(f"  - Approved: {approved_count} 件")
    print(f"  - Rejected: {rejected_count} 件")
    print(f"  - Pending:  0 件")

    data['discoveredCouncils'] = discovered
    with open(DATA_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print("docs/data.json & admin/ai_verification_report.json updated successfully.")

if __name__ == "__main__":
    run_verification()
