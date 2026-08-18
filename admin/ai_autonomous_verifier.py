import sys
import os
import json
import time
import urllib.request
import urllib.error
import re
import io
from bs4 import BeautifulSoup
import google.generativeai as genai

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


# Setup paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_JSON_FILE = os.path.abspath(os.path.join(BASE_DIR, "..", "docs", "data.json"))

# Configure Gemini API
API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    print("WARNING: GEMINI_API_KEY environment variable is not set.")
    print("Please set it before running this script.")
else:
    genai.configure(api_key=API_KEY)

# Use Gemini 1.5 Flash for fast/cheap classification
try:
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
except Exception as e:
    print(f"Failed to initialize Gemini model: {e}")
    model = None

def fetch_html(url, timeout=10):
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) PMHub-Crawler/1.0'}
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            html = response.read()
            # Try to decode safely
            charset = response.headers.get_content_charset()
            if charset:
                return html.decode(charset, errors='replace')
            else:
                for enc in ['utf-8', 'shift_jis', 'cp932', 'euc-jp']:
                    try:
                        return html.decode(enc)
                    except UnicodeDecodeError:
                        continue
                return html.decode('utf-8', errors='replace')
    except Exception as e:
        print(f"  [Fetch Error] {url}: {e}")
        return None

def extract_content_snippet(html):
    if not html:
        return ""
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Extract title
    title = soup.title.string.strip() if soup.title and soup.title.string else "No Title"
    
    # Extract meta description
    meta_desc = ""
    meta_tag = soup.find('meta', attrs={'name': 'description'})
    if meta_tag and meta_tag.get('content'):
        meta_desc = meta_tag['content'].strip()
        
    # Extract headers
    headers = []
    for h in soup.find_all(['h1', 'h2', 'h3']):
        h_text = h.get_text(separator=' ', strip=True)
        if h_text:
            headers.append(h_text)
            
    # Extract body text (first 2000 chars to save tokens)
    body = soup.find('body')
    body_text = body.get_text(separator=' ', strip=True) if body else ""
    body_text = re.sub(r'\s+', ' ', body_text)[:2000]
    
    snippet = f"Title: {title}\n"
    if meta_desc:
        snippet += f"Description: {meta_desc}\n"
    snippet += f"Headers: {' | '.join(headers[:5])}\n"
    snippet += f"Body Snippet: {body_text}\n"
    
    return snippet

def analyze_with_ai(url, snippet):
    if not model:
        return {"verdict": "pending", "reason": "AI model not initialized"}
        
    prompt = f"""
以下のWebページの抜粋情報を読み、このページが「日本政府の審議会、有識者会議、検討会、政策会議」などの公式ページ（またはその一覧・議事録ページ）であるか判定してください。
もし404エラーページ、単なるPDFファイル、移転のお知らせ、または全く無関係なページであれば却下してください。

URL: {url}

ページ情報抜粋:
{snippet}

必ず以下のJSON形式でのみ出力してください（Markdownの```json などのタグは含めないでください）。
{{
  "verdict": "approved" または "rejected",
  "reason": "判定の短い理由（日本語で50文字程度）"
}}
"""
    try:
        response = model.generate_content(prompt)
        result_text = response.text.strip()
        # Remove potential markdown code blocks
        if result_text.startswith("```json"):
            result_text = result_text[7:]
        if result_text.startswith("```"):
            result_text = result_text[3:]
        if result_text.endswith("```"):
            result_text = result_text[:-3]
            
        result_text = result_text.strip()
        data = json.loads(result_text)
        
        # Validate structure
        if "verdict" in data and "reason" in data:
            if data["verdict"] not in ["approved", "rejected"]:
                data["verdict"] = "rejected"
            return data
        else:
            return {"verdict": "rejected", "reason": "AI returned malformed JSON structure"}
            
    except Exception as e:
        print(f"  [AI Error] {e}")
        return {"verdict": "pending", "reason": f"AI error: {e}"}

def run_verification(limit=50):
    if not os.path.exists(DATA_JSON_FILE):
        print(f"data.json not found: {DATA_JSON_FILE}")
        return

    with open(DATA_JSON_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    discovered_councils = data.get("discoveredCouncils", [])
                
    count = 0
    for council in discovered_councils:
        c_id = council.get("id")
        url = council.get("officialUrl")
        status = council.get("status", "pending")
        
        if not c_id or not url:
            continue
            
        # Skip already verified
        if status in ["approved", "rejected"]:
            continue
            
        print(f"Verifying [{count+1}/{limit}]: {council.get('name')} ({url})")
        
        # Step 1: Fetch
        html = fetch_html(url)
        if not html:
            council["status"] = "rejected"
            council["aiReason"] = "Fetch failed or timeout"
            save_reports(data)
            count += 1
            if count >= limit:
                break
            time.sleep(1)
            continue
            
        # Step 2: Extract
        snippet = extract_content_snippet(html)
        
        # Step 3: AI Eval
        ai_result = analyze_with_ai(url, snippet)
        print(f"  -> Verdict: {ai_result.get('verdict')}, Reason: {ai_result.get('reason')}")
        
        council["status"] = ai_result.get('verdict', 'pending')
        council["aiReason"] = ai_result.get('reason', '')
        save_reports(data)
        
        count += 1
        if count >= limit:
            break
            
        time.sleep(2) # Rate limiting
        
    print(f"Processed {count} items. Done.")

def save_reports(data):
    with open(DATA_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    import argparse
    parser = argparse.ArgumentParser(description="AI Autonomous Verifier")
    parser.add_argument("--limit", type=int, default=50, help="Max number of items to verify in this run")
    args = parser.parse_args()
    
    run_verification(limit=args.limit)
