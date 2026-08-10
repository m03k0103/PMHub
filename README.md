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
- `crawler.py`: 政府サイトを巡回し、抽出結果を `scraped_councils_output.json` に出力
- `discover_councils.py`: 新規会議体を自動検出し、`discovered_councils.json` に出力
- `sync_crawler_data.py`: クローラーの出力結果を `docs/data.js` に自動同期・構文検証
- `agent_initial_verifier.py`: クロール/データ反映前後の検証補助
- `scraping_rules.json`: クロール抽出ルール定義
- `discovery_keywords.json`: 新規会議体発見用の検索キーワード定義
- `admin_dashboard.html`: 管理者向け統合ダッシュボード（会議体ディスカバリー、クローラー実行、データ管理）

## ディレクトリ構成

```text
PMHub/
├── package.json
├── README.md
├── docs/
│   ├── index.html
│   ├── styles.css
│   ├── data.js
│   └── app.js
├── admin/
│   ├── admin_dashboard.html
│   ├── admin_guide.md
│   ├── agent_crawl_guide.md
│   ├── agent_initial_verifier.py
│   ├── crawler.py
│   ├── discover_councils.py
│   ├── discovered_councils.json
│   ├── discovery_keywords.json
│   ├── scraped_councils_output.json
│   ├── scraping_rules.json
│   └── sync_crawler_data.py
├── design/
│   ├── CRAWLER_ARCHITECTURE.md
│   └── RESOURCE_MAP.md
└── testing/
    ├── app.test.js
    ├── smoke_test.py
    └── test_escapeHtml.js
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

### Node.js テスト

```bash
node --test testing/app.test.js
node testing/test_escapeHtml.js
```

### Python スモークテスト

```bash
python testing/smoke_test.py
```

`smoke_test.py` では主に以下を確認します。
- JS/Python の構文エラー検出
- 変更URL中心の疎通確認
- データ同期整合性チェック

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

3. 生成された `admin/scraped_councils_output.json` を確認
4. `admin/sync_crawler_data.py` を実行し `docs/data.js` に自動反映・検証
5. `testing/smoke_test.py` と Node.js テストを実行
6. 問題なければ公開

詳細は以下を参照してください。
- `admin/admin_guide.md`
- `admin/agent_crawl_guide.md`
- `design/CRAWLER_ARCHITECTURE.md`
- `design/RESOURCE_MAP.md`

## 公開・セキュリティ方針

- Web公開対象は `docs/` のみ
- `admin/` は非公開領域として分離
- 外部リンクは `sanitizeUrl` を通す
- 描画文字列は `escapeHtml` を通す

## 補足

- データは `docs/data.js` 内の `COUNCILS` / `MEETINGS` を参照して描画されます。
- 最終クロール時刻は `LAST_CRAWL_TIME` を優先表示します。
