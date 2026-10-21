# 浜松市オープンデータの自動掲載

## 処理

`collect_open_data.py` は浜松市イベントCSVを取得し、開催年・有効な日付・会場・一意の行IDを検証。
開催中・今後の情報を保存し、AIを使わず出典の事実から本文を構成します。
不明な料金・設備条件は補いません。CC BY 4.0の出典を記載します。
開催時刻や休館日等の注意事項は本文に保存します。期間内に毎日開催とは限りません。
CSVの中止・延期告知は保留します。日付や会場が欠けた行は自動掲載しません。

`open_data_publication` に出典行・取得日時・元文書のSHA256・掲載内容のSHA256を保存。
`publication_gate.py` は7日以内の取得記録と掲載内容が一致したものだけを公開します。
手動で保護・非掲載にしたものは同一性を照合して自動追加・更新を避けます。
正常取得した一覧からなくなった行の自動掲載許可は解除します。DBは削除しません。
空・壊れた・有効行ゼロの一覧は処理を失敗させ、既存DBを変更しません。
取得失敗時は確認日を更新しません。取得後7日以内の情報は掲載対象に残り得ます。
再生成・再配信が失敗すると、サーバーには前の静的ページが残るためActionsの成否確認が必要です。

## 運用

既存ファイルに更新を適用し、GitHub Actionsの「Collect Municipal Open Data and Publish」を実行。
mainへ反映後、日本時間毎日03:00にも実行します。AI用APIキーは不要です。
既存のHTTPS/FTP配信設定を使います。03:30の「Publish Reviewed Information」は掲載期限の見直し用として残します。
今回は浜松市の1情報源のみ。観光サイトのHTML巡回・AIリライトは日次の経路から外しました。
以前の「最大20件」のAI処理に代わり、有効な自治体データ全件を同期します。

実行：

```sh
python collect_open_data.py --backup /path/to/new-backup.db --report /path/to/report.json
python publication_gate.py --backup /path/to/another-new-backup.db
python generate_site.py
```

公開処理は既存ワークフローが行います。DBと生成HTMLの保存・配信の両方が成功したかをActionsで確認してください。
レポートと取り込み前DBはActionsのcollection-report成果物に保存します。

## 検証範囲（2026-10-21）

2026-10-18取得の保存CSVを一時DBで再生し469件を処理、再実行で重複しないことを確認。
保存CSVを本番DBへ追加していません。この件数は現在のデータ件数を保証しません。
最新CSV取得はこの環境の接続エラー（ProxyError）で未完了。
実サーバーへの配信・公開後の確認も未実施です。
公開判定を含む自動テストは tests/test_open_data_publication.py 等を参照。
