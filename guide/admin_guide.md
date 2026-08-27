# 政策会議ウォッチ (PM-HUB) 管理者向け運用マニュアル

本マニュアルは、「政策会議ウォッチ (PM-HUB)」の保守運用者・システム管理者向けに、データの自動巡回（クローリング）、データの反映、および各種設定の管理方法について記載したドキュメントです。

---

## 🛠️ 管理者ツールの構成 (`admin/`)

| ファイル | 説明 |
| :--- | :--- |
| [admin_dashboard.html](file:///d:/dev/PMHub/admin/admin_dashboard.html) | 管理者向け統合ダッシュボード（会議体ディスカバリー、クローラー即時実行UI、データ管理・承認UI） |
| [server.py](file:///d:/dev/PMHub/admin/server.py) | ローカル管理サーバー（API・データ保存・クローラー連携） |
| [start.bat](file:///d:/dev/PMHub/admin/start.bat) | 管理サーバー＆ダッシュボード ワンクリック起動スクリプト |
| [crawler.py](file:///d:/dev/PMHub/admin/crawler.py) | 政府Webサイトを巡回し、`docs/data.json` を直接更新するPythonスクリプト |
| [discover_councils.py](file:///d:/dev/PMHub/admin/discover_councils.py) | 新規会議体を自動検出するディスカバリーエンジン |
| [apply_report.py](file:///d:/dev/PMHub/admin/apply_report.py) | 管理者ダッシュボードからの検証レポートを `docs/data.json` に適用するスクリプト |
| [rejected_councils.json](file:///d:/dev/PMHub/admin/rejected_councils.json) | 却下・クロール除外会議体リスト（隔離データ） |
| [admin_guide.md](file:///d:/dev/PMHub/guide/admin_guide.md) | 本運用マニュアル |

---

## 🔄 定期自動更新（バッチクローリング）の設定

### 1. 手動でのクローラー実行
管理者端末のターミナルにて、以下のコマンドを実行します：

```bash
cd d:\dev\PMHub\admin
python crawler.py
```

実行後、`docs/data.json` 内の会議データ（`meetings`）および各会議体のクロール成否（`crawlStatus`）、最終実行日時（`lastCrawlTime`）が直接更新されます。

### 2. Windows タスクスケジューラによる自動化（例: 毎日午前6時実行）

1. **タスクの作成**: 「タスク スケジューラ」を開き、「基本タスクの作成」を選択。
2. **トリガー**: 「毎日」 ➔ `06:00:00`
3. **操作**: 「プログラムの開始」
   - プログラム: `python` (または `python.exe` のフルパス)
   - 引数の追加: `crawler.py`
   - 開始: `D:\dev\PMHub\admin`

---

## 🔒 セキュリティとデータソース一元化方針

1. **Web公開範囲**:
   - 一般公開するWebサーバー（Nginx / Apache / Cloudflare Pages / AWS S3等）のドキュメントルートには、**`docs/` ディレクトリ配下のみ**を公開設定してください。
   - `admin/` ディレクトリはWebアクセス不能な非公開領域として隔離します。

2. **データソース一元化と却下会議体の分離管理フロー**:
   - **唯一のデータソース (`docs/data.json`)**: 会議体マスター、開催回・配布資料、スクレイピング設定、ディスカバリーキーワード設定、クローラー設定はすべて `docs/data.json` に一元管理されます。
   - **クローラー巡回結果**: クローラーの実行結果は中間ファイルを経由せず、直接 `docs/data.json` へ安全に反映・保存されます。
   - **却下会議体**: 管理者コンソールで却下された会議体は `docs/data.json` から削除され、`admin/rejected_councils.json` に移動・隔離されます。クローラー巡回および公開ポータルから完全に除外されます。
   - 更新後は必ず `python testing/smoke_test.py` を実行してデータの整合性を確認します。
