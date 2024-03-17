#!/usr/bin/env python

import gradio
import jsonlines
import typer
from pathlib import Path
from typing import Annotated

from utils.constants import EPGDatasetSubset


app = typer.Typer()

@app.command()
def main(
    subset_path: Annotated[Path, typer.Option(help='アノテーションを付加するデータセットのサブセットのパス。', dir_okay=False)] = Path('epg_dataset_subset.jsonl'),
    start_index: Annotated[int, typer.Option(help='アノテーションを開始するインデックス。', show_default=True)] = 0,
):
    """
    EPG データセットのサブセットにシリーズタイトル・話数・サブタイトルのアノテーションを付加するための Web UI ツール。

    アノテーション方針:
    - シリーズタイトル: 連続して放送されている番組のシリーズタイトルを入力
    - 話数: 話数が番組情報に含まれている場合のみ入力、複数話ある場合は ・ (中点) で区切る
      - 表現は極力変更してはならない (「第1話」とあるなら 1 に正規化せずにそのまま入力すること)
      - 番組概要に含まれている話数の方が詳細な場合は、番組概要の方の話数表現を採用する
    - サブタイトル: サブタイトルが番組情報に含まれている場合のみ入力、複数話ある場合は ／ (全角スラッシュ) で区切る
      - 基本鉤括弧は除去すべきだが、墨付きカッコで囲まれている場合のみそのまま入力すること
      - サブタイトルが番組概要に含まれている場合は、番組概要の方のサブタイトル表現を採用する
    """

    if not subset_path.exists():
        print(f'ファイル {subset_path} は存在しません。')
        return

    typer.echo('=' * 80)
    print('ロード中...')
    subsets: list[EPGDatasetSubset] = []
    with jsonlines.open(subset_path, 'r') as reader:
        for obj in reader:
            subsets.append(EPGDatasetSubset.model_validate(obj))
    print(f'ロード完了: {len(subsets)} 件')
    typer.echo('=' * 80)

    # 現在処理中の EPG データサブセットのインデックス
    current_index = start_index

    def OnClick(
        id: str,
        title: str,
        description: str,
        series_title: str,
        episode_number: str,
        subtitle: str,
    ) -> tuple[gradio.Textbox, gradio.Textbox, gradio.Textbox, gradio.Textbox, gradio.Textbox, gradio.Textbox]:
        """ 確定ボタンが押されたときの処理 """

        nonlocal current_index, subsets

        # 初期画面から「確定」を押して実行されたイベントなので、保存処理は実行しない
        if id == '確定ボタンを押して、データセット作成を開始してください。':
            typer.echo('=' * 80)
            typer.echo('Selection of segment files has started.')
            typer.echo('=' * 80)

        # サブセットのアノテーションを更新
        elif current_index < len(subsets):

            # サブセットのアノテーションを更新
            subsets[current_index].series_title = series_title.strip()
            subsets[current_index].episode_number = episode_number.strip()
            if subsets[current_index].episode_number == '':
                subsets[current_index].episode_number = None
            subsets[current_index].subtitle = subtitle.strip()
            if subsets[current_index].subtitle == '':
                subsets[current_index].subtitle = None

            print(f'番組タイトル: {subsets[current_index].title_without_symbols}')
            print(f'番組概要: {subsets[current_index].description_without_symbols}')
            typer.echo('-' * 80)
            print(f'シリーズタイトル: {subsets[current_index].series_title}')
            print(f'話数: {subsets[current_index].episode_number} / サブタイトル: {subsets[current_index].subtitle}')
            typer.echo('-' * 80)
            print(f'残りデータ数: {len(subsets) - current_index - 1}')
            typer.echo('=' * 80)

            # ファイルに保存
            with jsonlines.open(subset_path, 'w', flush=True) as writer:
                for subset in subsets:
                        writer.write(subset.model_dump(mode='json'))

            # 次の処理対象のファイルのインデックスに進める
            current_index += 1

        # 次の処理対象のファイルがない場合は終了
        if current_index >= len(subsets):
            typer.echo('=' * 80)
            typer.echo('All files processed.')
            typer.echo('=' * 80)
            return (
                gradio.Textbox(value='アノテーションをすべて完了しました！プロセスを終了してください。', label='ID (読み取り専用)', interactive=False),
                gradio.Textbox(value='', label='番組タイトル (読み取り専用)', interactive=False),
                gradio.Textbox(value='', label='番組概要 (読み取り専用)', interactive=False),
                gradio.Textbox(value='', label='シリーズタイトル', interactive=True),
                gradio.Textbox(value='', label='話数 (該当情報がない場合は空欄)', interactive=True),
                gradio.Textbox(value='', label='サブタイトル (該当情報がない場合は空欄)', interactive=True),
            )

        # UI を更新
        return (
            gradio.Textbox(value=subsets[current_index].id, label='ID (読み取り専用)', interactive=False),
            gradio.Textbox(value=subsets[current_index].title_without_symbols, label='番組タイトル (読み取り専用)', interactive=False),
            gradio.Textbox(value=subsets[current_index].description_without_symbols, label='番組概要 (読み取り専用)', interactive=False),
            gradio.Textbox(value=subsets[current_index].title_without_symbols, label='シリーズタイトル', interactive=True),
            gradio.Textbox(value=subsets[current_index].title_without_symbols, label='話数 (該当情報がない場合は空欄)', interactive=True),
            gradio.Textbox(value=subsets[current_index].title_without_symbols, label='サブタイトル (該当情報がない場合は空欄)', interactive=True),
        )

    # Gradio UI の定義と起動
    with gradio.Blocks(css='.gradio-container { max-width: 768px !important; }') as gui:
        with gradio.Column():
            gradio.Markdown("""
                # EPG データセットサブセットアノテーションツール
                Tab キー / Shift + Tab キー を押すと、フォームやボタン間で素早くフォーカスを移動できます。
            """)
            id_box = gradio.Textbox(value='確定ボタンを押して、データセット作成を開始してください。', label='ID (読み取り専用)', interactive=False)
            title_box = gradio.Textbox(value='', label='番組タイトル (読み取り専用)', interactive=False)
            description_box = gradio.Textbox(value='', label='番組概要 (読み取り専用)', interactive=False)
            series_title_box = gradio.Textbox(value='', label='シリーズタイトル', interactive=True)
            episode_number_box = gradio.Textbox(value='', label='話数 (該当情報がない場合は空欄)', interactive=True)
            subtitle_box = gradio.Textbox(value='', label='サブタイトル (該当情報がない場合は空欄)', interactive=True)
            with gradio.Row():
                confirm_button = gradio.Button('確定', variant='primary')
                confirm_button.click(
                    fn = OnClick,
                    inputs = [
                        id_box,
                        title_box,
                        description_box,
                        series_title_box,
                        episode_number_box,
                        subtitle_box,
                    ],
                    outputs = [
                        id_box,
                        title_box,
                        description_box,
                        series_title_box,
                        episode_number_box,
                        subtitle_box,
                    ],
                )

        # 0.0.0.0:7860 で Gradio UI を起動
        gui.launch(server_name='0.0.0.0', server_port=7860)


if __name__ == '__main__':
    app()
