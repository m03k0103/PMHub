# 政策会議ウォッチ (PM-HUB) - AIエージェント クロール・データ更新標準作業手順書 (Agent Crawl Guide)

本書は、AIエージェント（Antigravity Agent）が政府各府省庁の審議会・政策会議ウェブサイトをクロールし、`docs/data.json` およびスクレイピングルールを更新・保守する際に必ず参照し遵守すべき作業手順書です。

---

## 1. クロール・データ更新の基本原則 (Core Mandates)

1. **データ構造の整合性確保**: `docs/data.json` の `councils` および `meetings` 配列のデータ構造・JSON構文エラー（SyntaxError）を100%防止する。
2. **回数表記の明確化**: 会議タイトルは原則「最新会合」などの汎用表記を避け、「`第X回`」または「`令和Y年第Z回`」と具体回数を明記する。
3. **資料データの末端取得**: 会議資料は中間ページリンクではなく、各回の「提出資料」「配付資料」ページを辿り、末端のPDF/HTMLリンクを直接取得して `materials` 配列に登録する。
4. **非公表資料の完全記録**: 一次ソースページ内に【非公表】・【非公開】として掲載されている資料も漏れなく `materials` 配列に記録し、閲覧者に存在を示す。
5. **却下・除外対象会議体の再追加防止**: ユーザー指示により却下された会議体（`admin/rejected_councils.json` に登録された会議体）はクロール対象から完全に除外し、`data.json` へ復元・再追加しない。
6. **同一資料リンクの重複防止**: 同一会議体内で複数開催回にわたって同じ資料URLが誤って紐付かないよう、過去の開催回との重複を検知・排除する。

---

## 2. クロール実行手順 (Step-by-Step Procedure)

### Step 1: ルール定義の事前確認 (`docs/data.json` 内 `scrapingRules`)
クロール対象会議体のID（例: `cao-contents_kyogikai-25`）に対応するルール定義を確認します。
* `encoding`: ページの文字コード（`utf-8` / `shift_jis` / `cp932` / `euc-jp`）
* `subpage_discovery_pattern`: 個別開催回の発見正規表現
* `detect_private_materials`: 非公表資料の自動検出フラグ（`true` / `false`）
* `private_doc_keyword`: 非公表の判定キーワード（`非公表` / `非公開`）

### Step 2: 一次ソースおよび個別サブページの巡回・パース
1. トップページまたは `kaisai.html` にアクセスし、最新の開催回リンク（`daiX/gijishidai.html` 等）を取得する。
2. 文字コード不整合による文字化けを防止するため、HTTPレスポンスのエンコーディング自動判定を適切に行う。
3. 2段階ネスト構造（サブページ内に配付資料PDFが配置されている形式）の場合、個別サブページまで到達してパースする。

### Step 3: 開催情報および資料リストの抽出フォーマット
抽出オブジェクトの構成規則：
* **開催日 (`date`)**: 和暦（令和・平成）から西暦 `YYYY/MM/DD` 形式へ変換。
* **公開資料 (`PDF`/`HTML`)**:
  ```json
  { "name": "資料1: ◯◯について (PDF / 229KB)", "type": "PDF", "size": "229 KB", "url": "https://...", "isMinutes": false }
  ```
* **非公表資料 (`NON_PUBLIC`)**:
  ```json
  { "name": "資料2: ◯◯省提出資料【非公表】", "type": "HTML", "size": "非公表", "url": "https://.../subpage.html", "isMinutes": false }
  ```

### Step 4: `docs/data.json` の安全な更新規則
クローラー（`crawler.py`）が生成した `scraped_councils_output.json` のデータを `docs/data.json` へ反映させる際、手動での追記ミスを避けるため、同期スクリプトまたは管理者ダッシュボード経由で安全に反映します。
* 会議体（`councils`）は 1レコード集約を維持し、「第X回」などの回次を会議体名に含めない。
* 各開催回（`meetings`）は親の `councilId` に正確に紐付ける。

### Step 5: スクレイピングルール (`scrapingRules`) への同期
新規会議体の追加やサイト構造の変更があった場合、`docs/data.json` の `scrapingRules` キーに対象会議体の最新ルールを保存する。

---

## 3. クロール・データ更新後の検証

クロール完了およびデータ更新後は、必ず以下の検証スクリプトを実行し、重複や欠損がないことを確認します。

```bash
# 会議体重複・開催回重複・資料重複の完全検証
python testing/test_no_duplicate_meetings.py

# 総合スモークテスト（構文・データ整合性テスト）
python testing/smoke_test.py
```

