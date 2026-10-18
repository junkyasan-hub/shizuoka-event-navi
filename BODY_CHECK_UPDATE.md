# 本文の確認で一部だけ保留する修正版

## 反映手順

ZIPを展開し、次の2ファイルをGitHubのmainで置き換えてください。

1. ai_rewriter.py
2. collect_events.py

本文確認機能・手動編集機能の導入時に使った event_verification.py、event_sources.py、manual_events.py も依存ファイルとして同梱しました。GitHub側に未配置の場合は追加してください。events.dbやdistをこのZIPで置き換える必要はありません。ワークフローの変更やAPIキーの再登録も不要です。

まず Actions → Check Event Collection → Run workflow を実行します。これは一時DBを使うため公開サイトは変更しません。

- 一部だけ保留: 成功終了し、Summaryはpartial。確認済み分だけ一時DBに保存されます。
- 全件保留: 失敗終了。レポートで本文・出典・引用のどこに問題があるか確認します。
- API通信失敗・確認応答全体の不正: 全件停止。確認を省略して公開はしません。

内容を確認後、通常の Automatic Event Data Collection… を実行してください。こちらは確認済みのイベントを実際に保存・公開します。

## レポートの確認箇所

実行結果下部のArtifacts → collection-report をダウンロードします。

- body_passed / body_held: 本文確認の通過数 / 保留数
- body_results: 確認対象全件。bodyが生成文、source_factsが収集元の情報、gemini_reviewがAI判定と引用です。
- body_issues: 保留イベントだけの同じ詳細。issuesに引用未記載・該当フィールドなし・出典と引用不一致などの理由があります。
- verification_diagnostics: API確認失敗や応答全体が不正な場合の診断情報。確認に渡した本文・出典と、形式不正時の応答本文を含みます。

既存の掲載済みイベントの再確認と自動削除しない方針は維持しています。Geminiが書式どおり返すよう指示を明確化しましたが、引用の不一致を無視する変更は行っていません。手動入力は別経路です。

ローカルでは模擬APIによる41件のテストが成功しています。本番Geminiへの通信は、この環境にはAPIキーがないため未実施です。旧レポートには不足していた本文・引用は、次回実行以降のレポートから確認できます。
