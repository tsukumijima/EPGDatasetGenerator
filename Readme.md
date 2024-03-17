
# EPGDatasetGenerator

手元の [EDCB](https://github.com/xtne6f/EDCB) (EpgTimerSrv) に保存されている過去の EPG データ (一部は将来の EPG データ) を抽出し、機械学習向けデータセットとして保存・加工するツール群です。  
番組情報データセットは JSONL (JSON Lines) 形式で保存されます。

## Requirements

- Python 3.11 + Poetry
- EDCB (EpgTimerSrv) がローカルネットワーク上の PC で稼働している
- EDCB は xtne6f 版 or その派生の近年のバージョンのものを使用している
- 事前に EDCB (EpgTimerSrv) の設定で EpgTimerNW (ネットワーク接続機能: ポート 4510) が有効になっている
- 事前に EDCB (EpgTimerSrv) の設定で過去の EPG データを全期間 (∞) 保存するように設定してある
- `EDCB\Setting\EpgArc2\` フォルダに過去の EPG データ (*.dat) が保存されている

## License

[MIT License](License.txt)
