# 政策会議ウォッチ (PM-HUB) リソースファイル役割説明・管理構成図

本ドキュメントは「政策会議ウォッチ (PM-HUB)」における各リソースファイルの役割、セキュリティ・権限区分（**一般公開用** / **管理者向け**）、およびディレクトリ構成について説明するものです。

---

## 📁 ディレクトリ構造概観

```
PMHub/
├── docs/                        # 【一般公開用】エンドユーザー向けポータルWebアプリケーション
│   ├── index.html               # 公開ポータルメインHTML構造・UIレイアウト
│   ├── styles.css               # 全21省庁対応デザインシステム・CSSスタイル
│   ├── data.json                # 審議会・会議配布資料データベース (構造化JSON)
│   └── app.js                   # フロントエンドSPAロジック (検索・フィルター・エクスポート・要約ON/OFF)
│
├── admin/                       # 【管理者向け】データ自動更新・システム運用管理ツール
│   ├── admin_dashboard.html     # 管理者向け統合ダッシュボード（ディスカバリー・クロール実行・データ検証UI）
│   ├── server.py                # 管理サーバー（API・データ保存・クローラー連携）
│   ├── start.bat                # 管理サーバー＆ダッシュボード ワンクリック起動バッチ
│   ├── crawler.py               # 政府Webサイト自動巡回・PDF解析Pythonクローラー
│   ├── discover_councils.py     # 新規会議体自動検出スクリプト（ディスカバリーエンジン）
│   ├── apply_report.py          # 検証レポート適用スクリプト
│   ├── agent_crawl_guide.md     # AIエージェント用 クロール・データ更新作業手順書
│   ├── rejected_councils.json   # 却下・クロール除外会議体リスト
│   └── scraped_councils_output.json # クローラー最新自動取得ログ・抽出JSONデータ
│
├── testing/                     # 【テスト用リソース】自動スモークテスト・単体テスト
│   ├── smoke_test.py            # 自動スモークテストスイート（構文・リンク・ID同期・タブ検証）
│   ├── test_escapeHtml.js       # セキュリティユーティリティ単体テストスクリプト
│   ├── test_no_duplicate_meetings.py # 会議重複・データ整合性テスト
│   └── app.test.js              # フロントエンドロジックユニットテスト
│
├── guide/                       # 【人間用ドキュメント】マニュアル・アーキテクチャ・役割説明書
│   ├── admin_guide.md           # 管理者用 運用マニュアル・Cron/タスクスケジューラ設定ガイド
│   ├── CRAWLER_ARCHITECTURE.md  # クローラーの仕組み・技術アーキテクチャ仕様書
│   └── RESOURCE_MAP.md          # 本ファイル (リソースファイル役割構成書)
│
├── AGENTS.md                    # AIエージェント向け 開発行動規範・品質ルール
└── README.md                    # プロジェクト総合ガイド・クイックスタート
```

---

## 🌐 1. 一般公開用リソース (`docs/`)

一般国民・報道関係者（記者）・研究者等のエンドユーザーがWebブラウザで直接閲覧・利用する静的・動的リソース群です。サーバー側の動的コード実行を必要とせず、高いセキュリティと高速性を確保します。

| ファイルパス | 区分 | 対象ユーザー | 主な役割・機能 |
| :--- | :--- | :--- | :--- |
| [docs/index.html](file:///d:/dev/PMHub/docs/index.html) | 一般公開 | 全ユーザー | サイト全体のDOM構造、レスポンシブヘッダー、検索・フィルターバー、タイムライン表示領域、審議会ディレクトリ、アナリティクス、ウォッチリスト、詳細ダイアログのUI定義。 |
| [docs/styles.css](file:///d:/dev/PMHub/docs/styles.css) | 一般公開 | 全ユーザー | 全21省庁・内閣官房の固有カラーバッジ、ダーク/ライト表示モード、ガラスモルフィズムUI、レスポンシブデザイン、開催日ハイライトバッジのスタイリング。 |
| [docs/data.json](file:///d:/dev/PMHub/docs/data.json) | 一般公開 | 全ユーザー | 全21省庁および内閣官房・内閣府の審議会・会議配布資料メタデータ（会議名、開催日、200 OK実存PDF直リンク、アジェンダ、タグ）の公開用データベース。 |
| [docs/app.js](file:///d:/dev/PMHub/docs/app.js) | 一般公開 | 全ユーザー | リアルタイムキーワード検索、省庁・種別多次元フィルター、ソート、Chart.js統計グラフ描画、マイウォッチリスト管理、Excel対応UTF-8 BOM付CSV/JSONデータ一括出力、AI要約 Feature Flag（ON/OFF切替）。 |

---

## ⚙️ 2. 管理者向けリソース (`admin/`)

システム運用者・管理者が政府Webサイトからの最新審議会情報の定期クローリング、データベース更新、およびシステム監視を行うためのバックエンドツール・スクリプト群です。一般ユーザーには非公開の領域として分離・管理されます。

| ファイルパス | 区分 | 対象ユーザー | 主な役割・機能 |
| :--- | :--- | :--- | :--- |
| [admin/admin_dashboard.html](file:///d:/dev/PMHub/admin/admin_dashboard.html) | 管理者用 | システム運用者 | タブ切り替え式統合ダッシュボード。新規会議体の検証（承認・却下）、Webクローラーの即時UI実行、AI要約 Feature Flag (ON/OFF) 切り替えなど。 |
| [admin/server.py](file:///d:/dev/PMHub/admin/server.py) | 管理者用 | システム運用者 | 管理ダッシュボード用ローカルサーバー（API、データ永続化、クローラー進捗通知）。 |
| [admin/start.bat](file:///d:/dev/PMHub/admin/start.bat) | 管理者用 | システム運用者 | 管理サーバーとダッシュボードをワンクリックで起動するWindowsバッチファイル。 |
| [admin/crawler.py](file:///d:/dev/PMHub/admin/crawler.py) | 管理者用 | システム運用者 | 政府Webサイトを自動訪問し、開催日・PDF直リンクを抽出するPythonクローラー。 |
| [admin/discover_councils.py](file:///d:/dev/PMHub/admin/discover_councils.py) | 管理者用 | システム運用者 | 各省庁の審議会等一覧ページを巡回し、新規の審議会等を自動検出するスクリプト。 |
| [admin/scraped_councils_output.json](file:///d:/dev/PMHub/admin/scraped_councils_output.json) | 管理者用 | システム運用者 | `crawler.py` の実行によってリアルタイム生成されるパース結果データ。 |
| [admin/rejected_councils.json](file:///d:/dev/PMHub/admin/rejected_councils.json) | 管理者用 | システム運用者 | 管理者によって却下・クロール除外された会議体リスト。 |
| [admin/apply_report.py](file:///d:/dev/PMHub/admin/apply_report.py) | 管理者用 | システム運用者 | 検証レポートの内容を `docs/data.json` に安全に適用するスクリプト。 |
| [admin/agent_crawl_guide.md](file:///d:/dev/PMHub/admin/agent_crawl_guide.md) | エージェント用 | AIエージェント | AIエージェント専用のクロール・データ更新作業標準手順書。 |

---

## 📖 3. 人間用ドキュメント (`guide/` / Root)

| ファイルパス | 区分 | 主な内容 |
| :--- | :--- | :--- |
| [guide/admin_guide.md](file:///d:/dev/PMHub/guide/admin_guide.md) | 人間用 | 定期自動巡回（Windowsタスクスケジューラ / Linux Cron）の構築手順、管理者ツールの運用マニュアル。 |
| [guide/RESOURCE_MAP.md](file:///d:/dev/PMHub/guide/RESOURCE_MAP.md) | 人間用 | 各リソースファイルの役割・権限区分・ディレクトリ構成の全容説明書（本ドキュメント）。 |
| [guide/CRAWLER_ARCHITECTURE.md](file:///d:/dev/PMHub/guide/CRAWLER_ARCHITECTURE.md) | 人間用 | Webクローラーの動作原理、HTTPリクエスト・文字コード判定・和暦/西暦正規表現抽出・絶対URL復元ロジックの詳細仕様書。 |
| [AGENTS.md](file:///d:/dev/PMHub/AGENTS.md) | エージェント用 | AIエージェント（Antigravity）向け行動規範、Plan作成ルール、自動テスト実行義務規程。 |
| [README.md](file:///d:/dev/PMHub/README.md) | 全般 | プロジェクトの全体目的、全21省庁＋内閣官房のカバー範囲、起動方法、機能一覧。 |

---

## 🔒 セキュリティおよび保守運用ガイドライン

1. **アクセス制限とファイル分離**:
   - `docs/` ディレクトリ配下のファイルのみを Web サーバー（Nginx / Apache / S3 等）のドキュメントルートとして公開します。
   - `admin/` ディレクトリはWeb非公開領域とし、サーバー内部のバッチ処理（Cron等）または管理者用ローカル環境でのみ実行します。

2. **データ同期フロー**:
   - 管理者環境で `admin/crawler.py` を実行 ➔ `admin/scraped_councils_output.json` を生成 ➔ 内容を検証の上、`docs/data.json` へ反映して公開します。
