# 新規会議体追加ルール

## 必須ワークフロー

新規会議体を `docs/data.js` の `COUNCILS` / `MEETINGS` に追加する際は、以下のワークフローに従うこと。

### 1. 追加時に `isNew: true` フラグを付与

新規追加する会議体オブジェクトには必ず `isNew: true` プロパティを設定する。

```javascript
{
  id: 'xxx-new-council-999',
  name: '新規会議体名',
  ministry: 'CAS',
  category: 'COUNCIL',
  // ...
  isNew: true,  // ← 必須
}
```

### 2. 管理者検証ページでレビュー

追加後、`admin/verify_new_councils.html` にアクセスし、管理者が以下を検証する。

- 会議体トップページURLの正確性
- 個別会議ページURLの正確性
- 資料リンクの疎通確認
- カテゴリ・省庁の妥当性

### 3. 承認とエクスポート

管理者が承認したのち「📥 承認済みをJSONエクスポート」ボタンでレポートを出力する。
- エクスポートされるのは**承認済みの会議体のみ**
- エクスポート後、承認済みの会議体は検証リストから自動的に消える（localStorage で永続化）
- レポート JSON の `corrections` 配列に含まれるURL修正を AI Agent が `docs/data.js` に反映する

### 4. AI Agent によるURL修正の適用

エクスポートされた `verification_report_YYYY-MM-DD.json` を AI Agent に渡すと、`corrections` 配列の各エントリが `docs/data.js` に適用される。

```json
{
  "action": "update_field",
  "target": "COUNCILS",
  "targetId": "xxx-new-council-999",
  "field": "officialUrl",
  "oldValue": "https://old-url...",
  "newValue": "https://correct-url..."
}
```

## 禁止事項

- `isNew: true` を付けずに会議体を追加してはならない
- 検証ページを経由せずに新規会議体を本番反映してはならない
- 管理者の承認なしにURL修正を適用してはならない
