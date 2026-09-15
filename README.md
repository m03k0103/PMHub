# 政策会議ウォッチ (Policy Meeting Hub / PMHub)

日本の政策会議・審議会・有識者会議の公開情報を、横断検索しやすい形で集約する静的Webポータルです。
フロントエンドは `docs/` 配下のみで完結し、管理用クローラーと運用ドキュメントは `admin/` / `design/` に分離しています。

## 機能概要

### 公開ポータル (`docs/`)
- 会議一覧を 2 モードで表示
	- 会議体別 (`BY_COUNCIL`)
	- 会議別タイムライン (`BY_DATE`)
- 横断検索（会議名・会議体名・要約・タグ・資料名・議題）
- 多軸フィルター（所管省庁 / 会議種別 / 資料種別 / 更新期間 / ウォッチ対象のみ）
- ウォッチリスト機能（`localStorage` 保存）
- 統計タブ（Chart.js）
- JSON / CSV エクスポート（CSVインジェクション対策・UTF-8 BOM 付き）
- ライト/ダークテーマ切替
- AI要約表示の Feature Flag（`pmhub_enable_ai_summary`）
- URLサニタイズ / HTMLエスケープによるXSS対策ユーティリティ

### 管理者ツール (`admin/`)
- `admin_dashboard.html`: 管理者向け統合ダッシュボード（会議体ディスカバリー、クローラー実行、データ管理）
- `server.py`: 管理ダッシュボード用ローカルサーバー（API、データ保存）
- `start.bat`: 管理サーバー＆ダッシュボード ワンクリック起動バッチ
- `crawler.py`: 政府サイトを巡回し、抽出結果を `docs/data.json` に直接反映
- `discover_councils.py`: 新規会議体を自動検出
- `apply_report.py`: 検証レポートを `docs/data.json` に適用
- `rejected_councils.json`: 却下・除外会議体リスト
- `agent_crawl_guide.md`: AIエージェント用 クロール・データ更新作業手順書

## ディレクトリ構成

```text
PMHub/
├── package.json
├── README.md
├── AGENTS.md
├── docs/
│   ├── index.html
│   ├── styles.css
│   ├── data.json
│   └── app.js
├── admin/
│   ├── admin_dashboard.html
│   ├── server.py
│   ├── start.bat
│   ├── agent_crawl_guide.md
│   ├── crawler.py
│   ├── discover_councils.py
│   ├── rejected_councils.json
│   └── apply_report.py
├── guide/
│   ├── admin_guide.md
│   ├── CRAWLER_ARCHITECTURE.md
│   └── RESOURCE_MAP.md
└── testing/
    ├── app.test.js
    ├── smoke_test.py
    ├── test_no_duplicate_meetings.py
    ├── test_crawler_regression.py
    └── test_js_runtime.js
```

## セットアップ

### 1) 依存関係のインストール

```bash
npm install
```

現在の `package.json` ではテスト補助に `jsdom` を利用しています。

### 2) 公開ポータルを起動

ビルドは不要です。`docs/` を静的配信してください。

```bash
cd docs
python -m http.server 8000
```

ブラウザで `http://localhost:8000` を開きます。

## テスト

本プロジェクトでは以下の自動テストスイートを提供しており、データ更新やコード修正時の品質を多層的に保証します。

### 1) 統合スモークテスト（推奨・全8大テスト一括実行）

```bash
python testing/smoke_test.py
```
- JS/HTML/Python/JSON の構文エラー検出・DOM 整合性検査（`HTMLParser` による div ネスト検査）
- 変更 URL 中心の疎通確認
- JS ユーティリティ単体テスト連携
- 会議品質・回次整合性・重複排除検証
- 会議体ID同期・除外リスト・完全整合性検証
- UI 主要コンテナ・管理ダッシュボード全5タブ構造検証
- クローラー手動保護（`manualLock`）回帰検証
- JavaScript 実行時クラッシュ（TDZ・全画面描画）検証

### 2) 個別テストスイート

- **JS ユーティリティ単体テスト**:
  ```bash
  node --test testing/app.test.js
  ```
  XSS 防止・URLサニタイズ、日付・年度計算関数の単体テスト。

- **会議品質・回次整合性・重複排除検証**:
  ```bash
  python testing/test_no_duplicate_meetings.py
  ```
  全会議データの重複ゼロ・回次整合性・命名規則の厳格検証。

- **クローラー手動データ保護回帰テスト**:
  ```bash
  python testing/test_crawler_regression.py
  ```
  `manualLock: true` データの上書き保護、重複排除の非破壊性、新規開催回の自動昇格を検証。

- **JavaScript 実行時クラッシュ・全画面描画検証**:
  ```bash
  node testing/test_js_runtime.js
  ```
  公開ポータルおよび管理コンソールの全5タブ描画時におけるクラッシュ・TDZを検証。

## データ更新フロー（運用）

1. 新規会議体ディスカバリー (オプション)

```bash
cd admin
python discover_councils.py
```

2. クローラー実行

```bash
cd admin
python crawler.py
```

3. クロール結果は `docs/data.json` に直接安全に反映・保存されます
4. `testing/smoke_test.py` と Node.js テストを実行
5. 問題なければコミット・公開

詳細は以下を参照してください。
- `guide/admin_guide.md`
- `guide/CRAWLER_ARCHITECTURE.md`
- `guide/RESOURCE_MAP.md`
- `AGENTS.md`
- `admin/agent_crawl_guide.md`

## 公開・セキュリティ方針

- Web公開対象は `docs/` のみ
- `admin/` は非公開領域として分離
- 外部リンクは `sanitizeUrl` を通す
- 描画文字列は `escapeHtml` を通す

## 補足

- データは `docs/data.json` 内の `councils` / `meetings` を参照して描画されます。
- 最終クロール時刻は `lastCrawlTime` を優先表示します。
