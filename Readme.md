
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

## Usage

EpgDatasetGenerator は3つのツールに分かれています。

## 01-GenerateEPGDataset.py

```bash
> poetry run ./01-GenerateEPGDataset.py --help

 Usage: 01-GenerateEPGDataset.py [OPTIONS]

 EDCB (EpgTimerSrv) に保存されている過去の EPG データを期間やネットワーク ID を指定して抽出し、JSONL 形式のデータセットを生成する。

╭─ Options ────────────────────────────────────────────────────────────────────────────────────────╮
│ --dataset-path               PATH                              保存先の JSONL ファイルのパス。   │
│                                                                [default: epg_dataset.jsonl]      │
│ --edcb-host                  TEXT                              ネットワーク接続する EDCB         │
│                                                                のホスト名。                      │
│                                                                [default: 127.0.0.1]              │
│ --start-date                 [%Y-%m-%d|%Y-%m-%dT%H:%M:%S|%Y-%  過去 EPG データの取得開始日時     │
│                              m-%d %H:%M:%S]                    (UTC+9) 。                        │
│                                                                [default: 2024-03-17              │
│                                                                07:18:43.622855]                  │
│ --end-date                   [%Y-%m-%d|%Y-%m-%dT%H:%M:%S|%Y-%  過去 EPG データの取得終了日時     │
│                              m-%d %H:%M:%S]                    (UTC+9)。                         │
│                                                                [default: 2024-03-18              │
│                                                                07:18:43.622865]                  │
│ --include-network-ids        INTEGER                           取得対象のネットワーク ID         │
│                                                                のリスト。                        │
│                                                                [default: 4, 6, 7, 32736, 32737,  │
│                                                                32738, 32741, 32739, 32742,       │
│                                                                32740, 32391]                     │
│ --install-completion                                           Install completion for the        │
│                                                                current shell.                    │
│ --show-completion                                              Show completion for the current   │
│                                                                shell, to copy it or customize    │
│                                                                the installation.                 │
│ --help                                                         Show this message and exit.       │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## 02-GenerateEPGDatasetSubset.py

```bash
> poetry run ./02-GenerateEPGDatasetSubset.py --help

 Usage: 02-GenerateEPGDatasetSubset.py [OPTIONS]

 JSONL 形式の EPG データセットのサブセットを期間やサイズを指定して生成する。
 動作ロジック:
 - 地上波: 65%、BS (無料放送): 25%、BS (有料放送) + CS: 10% とする
 - 重複している番組は除外する
 - ショッピング番組は除外する
 - 不明なジャンル ID の番組は除外する
 - ジャンル自体が EPG データに含まれていない番組は除外する
 - タイトルが空文字列の番組は除外する
 - 重み付けされたデータを適切にサンプリングして、subset_size で指定されたサイズのサブセットを生成する
 - 大元の JSONL データの各行には "raw" という EDCB から取得した生データの辞書が含まれているが、サブセットでは利用しないので除外する
 - 最終的に ID でソートされた JSONL データが生成される

╭─ Options ────────────────────────────────────────────────────────────────────────────────────────╮
│ --dataset-path              FILE                              データ元の JSONL                   │
│                                                               データセットのパス。               │
│                                                               [default: epg_dataset.jsonl]       │
│ --subset-path               FILE                              生成するデータセットのサブセット … │
│                                                               [default:                          │
│                                                               epg_dataset_subset.jsonl]          │
│ --subset-size               INTEGER                           生成するデータセットのサブセット … │
│                                                               [default: 5000]                    │
│ --start-date                [%Y-%m-%d|%Y-%m-%dT%H:%M:%S|%Y-%  サブセットとして抽出する番組範囲 … │
│                             m-%d %H:%M:%S]                    [default: None]                    │
│ --end-date                  [%Y-%m-%d|%Y-%m-%dT%H:%M:%S|%Y-%  サブセットとして抽出する番組範囲 … │
│                             m-%d %H:%M:%S]                    [default: None]                    │
│ --install-completion                                          Install completion for the current │
│                                                               shell.                             │
│ --show-completion                                             Show completion for the current    │
│                                                               shell, to copy it or customize the │
│                                                               installation.                      │
│ --help                                                        Show this message and exit.        │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## 03-AnnotateEPGDatasetSubset.py

```bash
> poetry run ./03-AnnotateEPGDatasetSubset.py --help

 Usage: 03-AnnotateEPGDatasetSubset.py [OPTIONS]

 EPG データセットのサブセットにシリーズタイトル・話数・サブタイトルのアノテーションを付加するための Web UI ツール。
 アノテーション方針:
 - シリーズタイトル: 連続して放送されている番組のシリーズタイトルを入力
 - 話数: 話数が番組情報に含まれている場合のみ入力、複数話ある場合は ・ (中点) で区切る
   - 表現は極力変更してはならない (「第1話」とあるなら 1 に正規化せずにそのまま入力すること)
   - 番組概要に含まれている話数の方が詳細な場合は、番組概要の方の話数表現を採用する
 - サブタイトル: サブタイトルが番組情報に含まれている場合のみ入力、複数話ある場合は ／ (全角スラッシュ) で区切る
   - 基本鉤括弧は除去すべきだが、墨付きカッコで囲まれている場合のみそのまま入力すること
   - サブタイトルが番組概要に含まれている場合は、番組概要の方のサブタイトル表現を採用する

╭─ Options ────────────────────────────────────────────────────────────────────────────────────────╮
│ --subset-path               FILE     アノテーションを付加するデータセットのサブセットのパス。    │
│                                      [default: epg_dataset_subset.jsonl]                         │
│ --start-index               INTEGER  アノテーションを開始するインデックス。 [default: 0]         │
│ --install-completion                 Install completion for the current shell.                   │
│ --show-completion                    Show completion for the current shell, to copy it or        │
│                                      customize the installation.                                 │
│ --help                               Show this message and exit.                                 │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## License

[MIT License](License.txt)
