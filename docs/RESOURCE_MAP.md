# 政策会議ウォッチ (PM-HUB) リソースファイル役割説明・管理構成図

本ドキュメントは「政策会議ウォッチ (PM-HUB)」における各リソースファイルの役割、セキュリティ・権限区分（**一般公開用** / **管理者向け**）、およびディレクトリ構成について説明するものです。

---

## 📁 ディレクトリ構造概観

```
PMHub/
├── public/                      # 【一般公開用】エンドユーザー向けポータルWebアプリケーション
│   ├── index.html               # 公開ポータルメインHTML構造・UIレイアウト
│   ├── styles.css               # 全21省庁対応デザインシステム・CSSスタイル
│   ├── data.js                  # 審議会・会議配布資料データベース (構造化オブジェクト)
│   └── app.js                   # フロントエンドSPAロジック (検索・フィルター・エクスポート・要約ON/OFF)
│
├── admin/                       # 【管理者向け】データ自動更新・システム運用管理ツール
│   ├── crawler.py               # 政府Webサイト自動巡回・PDF解析Pythonクローラー
│   ├── scraped_councils_output.json # クローラー最新自動取得ログ・抽出JSONデータ
│   └── admin_guide.md           # 管理者用 運用マニュアル・Cron/タスクスケジューラ設定ガイド
│
├── testing/                     # 【テスト用リソース】自動スモークテスト・単体テスト
│   ├── smoke_test.py            # 自動スモークテストスイート（構文・リンク・ID同期検証）
│   ├── test_escapeHtml.js       # セキュリティユーティリティ単体テストスクリプト
│   └── app.test.js              # フロントエンドロジックユニットテスト
│
├── docs/                        # 【全般ドキュメント】プロジェクト構成・役割説明書
│   └── RESOURCE_MAP.md          # 本ファイル (リソースファイル役割構成書)
│
└── README.md                    # プロジェクト総合ガイド・クイックスタート
```

---

## 🌐 1. 一般公開用リソース (`public/`)

一般国民・報道関係者（記者）・研究者等のエンドユーザーがWebブラウザで直接閲覧・利用する静的・動的リソース群です。サーバー側の動的コード実行を必要とせず、高いセキュリティと高速性を確保します。

| ファイルパス | 区分 | 対象ユーザー | 主な役割・機能 |
| :--- | :--- | :--- | :--- |
| [public/index.html](file:///d:/dev/PMHub/public/index.html) | 一般公開 | 全ユーザー | サイト全体のDOM構造、レスポンシブヘッダー、検索・フィルターバー、タイムライン表示領域、審議会ディレクトリ、アナリティクス、ウォッチリスト、詳細ダイアログのUI定義。 |
| [public/styles.css](file:///d:/dev/PMHub/public/styles.css) | 一般公開 | 全ユーザー | 全21省庁・内閣官房の固有カラーバッジ、ダーク/ライト表示モード、ガラスモルフィズムUI、レスポンシブデザイン、開催日ハイライトバッジのスタイリング。 |
| [public/data.js](file:///d:/dev/PMHub/public/data.js) | 一般公開 | 全ユーザー | 全21省庁および内閣官房・内閣府の審議会・会議配布資料メタデータ（会議名、開催日、200 OK実存PDF直リンク、アジェンダ、タグ）の公開用インデックスデータ。 |
| [public/app.js](file:///d:/dev/PMHub/public/app.js) | 一般公開 | 全ユーザー | リアルタイムキーワード検索、省庁・種別多次元フィルター、ソート、Chart.js統計グラフ描画、マイウォッチリスト管理、Excel対応UTF-8 BOM付CSV/JSONデータ一括出力、AI要約 Feature Flag（ON/OFF切替）。 |

---

## ⚙️ 2. 管理者向けリソース (`admin/`)

システム運用者・管理者が政府Webサイトからの最新審議会情報の定期クローリング、データベース更新、およびシステム監視を行うためのバックエンドツール・スクリプト群です。一般ユーザーには非公開の領域として分離・管理されます。

| ファイルパス | 区分 | 対象ユーザー | 主な役割・機能 |
| :--- | :--- | :--- | :--- |
| [admin/admin_dashboard.html](file:///d:/dev/PMHub/admin/admin_dashboard.html) | 管理者用 | システム運用者 | 管理者用コントロールパネル。Webクローラーの即時UI実行、AI要約 Feature Flag (ON/OFF) 切り替え、JSONパースログの確認。 |
| [admin/crawler.py](file:///d:/dev/PMHub/admin/crawler.py) | 管理者用 | システム運用者 | 内閣官房（全世代型社会保障構築会議、社会保障国民会議、中東情勢関係閣僚会議）や内閣府（人工知能戦略本部）等の政府Webサイトを自動訪問し、開催日・PDF直リンクを抽出するPythonスクリプト。 |
| [admin/scraped_councils_output.json](file:///d:/dev/PMHub/admin/scraped_councils_output.json) | 管理者用 | システム運用者 | `crawler.py` の実行によってリアルタイム生成されるパース結果データ。各Webページの取得ステータス (200 OK)、タイトル、PDF件数、抽出日付が保存されます。 |
| [admin/admin_guide.md](file:///d:/dev/PMHub/admin/admin_guide.md) | 管理者用 | システム運用者 | 定期自動巡回（Windowsタスクスケジューラ / Linux Cron）の構築手順、エラーハンドリング、新規審議会の追加方法を記載した運用仕様書。 |

---

## 📖 3. 総合ドキュメント (`docs/` / Root)

| ファイルパス | 区分 | 主な内容 |
| :--- | :--- | :--- |
| [docs/RESOURCE_MAP.md](file:///d:/dev/PMHub/docs/RESOURCE_MAP.md) | 全般 | 各リソースファイルの役割・権限区分・ディレクトリ構成の全容説明書（本ドキュメント）。 |
| [docs/CRAWLER_ARCHITECTURE.md](file:///d:/dev/PMHub/docs/CRAWLER_ARCHITECTURE.md) | 全般 | Webクローラーの動作原理、HTTPリクエスト・文字コード判定・和暦/西暦正規表現抽出・絶対URL復元ロジックの詳細仕様書。 |
| [README.md](file:///d:/dev/PMHub/README.md) | 全般 | プロジェクトの全体目的、全21省庁＋内閣官房のカバー範囲、起動方法、機能一覧。 |

---

## 🔒 セキュリティおよび保守運用ガイドライン

1. **アクセス制限とファイル分離**:
   - `public/` ディレクトリ配下のファイルのみを Web サーバー（Nginx / Apache / S3 等）のドキュメントルートとして公開します。
   - `admin/` ディレクトリはWeb非公開領域とし、サーバー内部のバッチ処理（Cron等）または管理者用ローカル環境でのみ実行します。

2. **データ同期フロー**:
   - 管理者環境で `admin/crawler.py` を実行 ➔ `admin/scraped_councils_output.json` を生成 ➔ 内容を検証の上、`public/data.js` へ反映して公開します。
