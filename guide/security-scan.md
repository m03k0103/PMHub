# PMHub セキュリティスキャン (OWASP ZAP DAST)

本プロジェクトでは、GitHub Actions (`.github/workflows/zap-dast.yml`) により OWASP ZAP (`ghcr.io/zaproxy/zaproxy:stable`) を用いた動的脆弱性スキャン（DAST）を自動実行しています。

## 1. CI/CD パイプライン仕様

| 項目 | 設定内容 |
| :--- | :--- |
| **PR / `main` プッシュ時** | `zap-baseline.py`（パッシブスキャン中心・高速チェック） |
| **定期実行（毎週日曜 04:00 JST）/ 手動実行 (`full`)** | `zap-full-scan.py`（アクティブスキャンを含む詳細チェック） |
| **CI 対象サーバー** | `http://127.0.0.1:8001/index.html`（CI 環境内で一時起動するローカルサーバーのみ） |
| **失敗基準** | **High** (`riskcode == 3`) 検出時のみ CI 失敗 (`exit 1`)。Medium / Low は警告出力のみ |
| **レポート保管** | Artifact `zap-scan-report`（HTML / JSON / Markdown）＋ Job Summary ＋ PR コメント |

> **安全制約**: `.zap/evaluate_zap_report.py --validate-target` により、`127.0.0.1` / `localhost` / `host.docker.internal` 以外の外部 URL や本番 URL へのスキャンは実行前に拒否されます。

## 2. ローカル環境での再現手順

Docker Desktop / Docker Engine がインストールされている環境で、ローカルサーバーを起動してからスキャンを実行してください。

### ステップ 1: ローカルサーバー起動（別ターミナル）

```bash
python3 -m http.server 8001 --directory docs --bind 127.0.0.1
```

### ステップ 2: ZAP ベースラインスキャン実行

**Bash / Git Bash / WSL の場合:**
```bash
./scripts/run-zap-scan.sh baseline
```

**Windows PowerShell の場合:**
```powershell
.\scripts\run-zap-scan.ps1 -ScanMode baseline
```

**Docker ワンライナーで直接実行する場合:**
```bash
mkdir -p .zap/reports && cp .zap/rules.tsv .zap/reports/rules.tsv
docker run --rm --add-host=host.docker.internal:host-gateway \
  -v "$(pwd)/.zap/reports:/zap/wrk/:rw" \
  ghcr.io/zaproxy/zaproxy:stable \
  zap-baseline.py -t http://host.docker.internal:8001/index.html \
  -c rules.tsv -J report_json.json -w report_md.md -r report_html.html -I
```

スキャン完了後、`.zap/reports/report_html.html` および `.zap/reports/summary.md` に結果が出力されます。

## 3. ルールチューニング方法 (`.zap/rules.tsv`)

誤検知（False Positive）やテスト環境特有の無害なヘッダー警告を調整する場合は、`.zap/rules.tsv` を編集します。

- 形式は **必ず TAB (`\t`) 区切り**（`<plugin_id>\t<IGNORE|WARN|FAIL|OUTOFSCOPE>\t(<説明またはURL正規表現>)`）を使用してください。
- 例: 特定ルールを無効化する場合:
  ```tsv
  10038	IGNORE	(Content Security Policy Header Not Set - managed by CDN)
  ```
- 詳細な共通仕様は `D:\dev\Orchestration\docs\security-scan.md` を参照してください。

## 4. Drop 148 (`Track [Security-DAST]`) 適用セキュリティ強化およびルール判断根拠

公開ポータル（`docs/index.html` / `docs/app.js`）に対して以下の多層防御を実施した上で、CI ローカルサーバー（`python3 -m http.server`）固有または外部動的 CSS 仕様上のアラートを整理しています。

### 4-1. 実コードにおけるセキュリティ対策
1. **外部 CDN スクリプトのバージョン固定 & SRI (`90003` 対応)**:
   - Chart.js を `https://cdn.jsdelivr.net/npm/chart.js@4.4.8/dist/chart.umd.min.js` にバージョン固定し、`integrity="sha384-..."` および `crossorigin="anonymous"` を付与。
2. **Content Security Policy `<meta>` 配備 & インラインスクリプト排除 (`10038` 対応)**:
   - `docs/index.html` の `<head>` に `<meta http-equiv="Content-Security-Policy" ...>` を配備（`default-src 'self'`, `script-src 'self' https://cdn.jsdelivr.net`, `object-src 'none'`, `base-uri 'self'`, `form-action 'self'`）。
   - `script-src` での `'unsafe-inline'` を不要化するため、テーマ初期設定スクリプトおよびすべてのインラインイベント属性（`onclick` / `onchange` / `onkeydown`）を `docs/app.js` 側の `addEventListener` / イベント委譲へ移行。
3. **統合テスト（ケース3）による回帰防止**:
   - `testing/test_js_runtime.js` にて CSP・SRI・インライン `<script>` / `on*=` ゼロ・`.zap/rules.tsv` TAB 区切り整合性を自動検査。

### 4-2. `.zap/rules.tsv` ルール調整の根拠

| Plugin ID | 設定 | 対象 / 要因 | 判断根拠 |
| :---: | :---: | :--- | :--- |
| `10036` | `IGNORE` | `Server: SimpleHTTP/0.6 Python/...` | CI 用ローカルサーバー固有のヘッダーであり本番（GitHub Pages）とは無関係なため除外 |
| `10017` | `IGNORE` | `cdn.jsdelivr.net` (`chart.js`) | バージョン固定および SHA-384 SRI で改ざん検知を担保済みの信頼 CDN のため除外 |
| `90003` | `IGNORE` | Google Fonts CSS (`fonts.googleapis.com`) | Google Fonts はアクセス元 User-Agent に応じて動的 CSS を返すため固定 SRI ハッシュが付与不可（JS CDN の SRI はケース3テストで常時強制） |
| `10015`, `10020`, `10021`, `10035`, `10038`, `10063`, `90004` | `WARN` | HTTP レスポンスヘッダー未設定系 | 静的ファイル・`python3 -m http.server` 環境では HTTP ヘッダー（`X-Frame-Options`, `frame-ancestors`, `X-Content-Type-Options` 等）を付与できないため警告扱いで可視化維持（CSP は HTML `<meta>` で担保） |
