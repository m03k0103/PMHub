# 政策会議ウォッチ (PM-HUB) - AIエージェント クロール実行標準作業手順書 (Agent Crawl Guide)

本書は、AIエージェント（Antigravity Agent）が政府各府省庁の審議会・政策会議ウェブサイトをクロールし、`docs/data.js` および `admin/scraping_rules.json` を更新・保守する際に必ず参照し遵守すべき標準手順書です。

---

## 1. 目的と基本規則 (Core Mandates)

1. **データ構造の整合性確保**: `docs/data.js` の `COUNCILS` および `MEETINGS` 配列のデータ構造・構文エラー（SyntaxError）を100%防止する。
2. **回数表記の明確化**: 会議タイトルは原則「最新会合」などの汎用表記を避け、「`第X回`」または「`令和Y年第Z回`」と具体回数を明記する。
3. **非公表資料の完全記録**: 一次ソースページ内に【非公表】・【非公開】として掲載されている資料も漏れなく `materials` 配列に記録し、閲覧者に存在を示す。
4. **除外対象会議体の再追加防止**: ユーザー指示により除外された会議体（`cas-honbu_setti-8`: 緊急災害対策本部、`cas-pages-4`: 大雪に関する関係閣僚会議 等）はクロール対象から完全に除外し、`data.js` へ復元・再追加しない。
5. **検証スクリプトの完全通過**: 更新後は必ず `python admin/agent_initial_verifier.py` を実行し、構文・リンク疎通・ID同期を合格させる。

---

## 2. クロール実行 6ステップ手順 (Step-by-Step Procedure)

### Step 1: ルールファイルの事前確認 (`admin/scraping_rules.json`)
クロール対象会議体のID（例: `cao-contents_kyogikai-25`）に対応するルール定義を確認します。
* `encoding`: ページの文字コード（`utf-8` / `shift_jis` / `cp932`）
* `subpage_discovery_pattern`: 個別開催回の発見正規表現
* `detect_private_materials`: 非公表資料の自動検出フラグ（`true` / `false`）
* `private_doc_keyword`: 非公表の判定キーワード（`非公表` / `非公開`）

### Step 2: 一次ソースおよび個別サブページの巡回・パース
1. トップページまたは `kaisai.html` にアクセスし、最新の開催回リンク（`daiX/gijishidai.html` 等）を取得する。
2. 文字コード不整合による文字化けを防止するため、HTTPレスポンスのエンコーディング処理を適切に行う。
3. 2段階ネスト構造（サブページ内に配付資料PDFが配置されている形式）の場合、個別サブページまで到達してパースする。

### Step 3: 開催情報および資料リストの抽出しきい値
抽出オブジェクトの構成規則：
* **開催日 (`date`)**: 和暦（令和・平成）から西暦 `YYYY/MM/DD` 形式へ変換。
* **公開資料 (`PDF`/`HTML`)**:
  ```javascript
  { name: '資料1: ◯◯について (PDF / 229KB)', type: 'PDF', size: '229 KB', url: 'https://...', isMinutes: false }
  ```
* **非公表資料 (`NON_PUBLIC`)**:
  ```javascript
  { name: '資料2: ◯◯省提出資料【非公表】', type: 'HTML', size: '非公表', url: 'https://.../subpage.html', isMinutes: false }
  ```

### Step 4: `docs/data.js` の安全な更新規則 (CRITICAL)
`docs/data.js` 編集時の禁止事項およびフォーマット規定：
1. **オブジェクトキーはアンクォート (Unquoted)**:
   * 正: `councilId: '...'`, `officialUrl: '...'`
   * 誤: `'councilId': '...'`
2. **文字列値はシングルクォート (Single Quotes)**:
   * 正: `title: '第2回 コンテンツ産業官民協議会'`
3. **文字列内の生改行（`\n`）絶対禁止**:
   * 資料名や概要が複数行にわたる場合、必ず1行の文字列へ結合・整形する。
4. **波括弧・角括弧の数と深度の一致**:
   * 置換時の残骸（孤立した `},` や `]`）を残さない。

### Step 5: `admin/scraping_rules.json` への同期
新規会議体の追加やサイト構造の変更があった場合、AIルール生成ロジックにより `scraping_rules.json` の該当エントリーを最新状態に更新・保存する。

### Step 6: テスト＆検証スクリプトの実行 (`Pre-Flight Check`)
ターミナルより以下の検証スクリプトを実行し、エラーが 0件 であることを確認する：
```bash
python admin/agent_initial_verifier.py
```

---

## 3. トラブルシューティング＆再発防止チェックリスト

* **現象: Web画面でデータが表示されなくなった**
  1. `python admin/agent_initial_verifier.py` を実行。
  2. `validate_data_js()` の出力ログを確認：
     * `Brace count mismatch` -> 波括弧 `{` `}` の不一致（孤立した `},` の消し忘れ）。
     * `Unescaped single quote string imbalance` -> 文字列内の生改行または単一引用符のエスケープ漏れ。
  3. `scratch/validate_js_ast.py` および `scratch/find_exact_brace_error.py` を使用して該当行番号を即座に特定・修正する。

---
**本ガイドラインは次回以降のクロール・データ更新作業時にエージェントが自動参照して実行すること。**
