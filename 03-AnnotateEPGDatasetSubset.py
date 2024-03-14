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
    subset_path: Annotated[Path, typer.Option(help='データセットのサブセットのパス。', dir_okay=False)] = Path('epg_dataset_subset.jsonl'),
    annotated_subset_path: Annotated[Path, typer.Option(help='アノテーション追加後のデータセットのサブセットのパス。')] = Path('epg_dataset_subset_annotated.jsonl'),
):
    if not subset_path.exists():
        print(f'ファイル {subset_path} は存在しません。')
        return
    if annotated_subset_path.exists():
        print(f'ファイル {annotated_subset_path} は既に存在しています。')
        return

    typer.echo('=' * 80)
    print('ロード中...')
    subsets: list[EPGDatasetSubset] = []
    with jsonlines.open(subset_path, 'r') as reader:
        for obj in reader:
            subsets.append(EPGDatasetSubset.model_validate(obj))
    print(f'ロード完了: {len(subsets)} 件')
    typer.echo('=' * 80)

    with jsonlines.open(annotated_subset_path, 'w', flush=True) as writer:

        # 現在処理中の EPG データサブセットのインデックス
        current_index = 0

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
                subset = subsets[current_index]
                subset.series_title = series_title.strip()
                subset.episode_number = episode_number.strip()
                if subset.episode_number == '':
                    subset.episode_number = None
                subset.subtitle = subtitle.strip()
                if subset.subtitle == '':
                    subset.subtitle = None
                writer.write(subset.model_dump(mode='json'))

                print(f'番組タイトル: {subset.title_without_symbols}')
                print(f'番組概要: {subset.description_without_symbols}')
                typer.echo('-' * 80)
                print(f'シリーズタイトル: {subset.series_title}')
                print(f'話数: {subset.episode_number} / サブタイトル: {subset.subtitle}')
                typer.echo('-' * 80)
                print(f'残りデータ数: {len(subsets) - current_index - 1}')
                typer.echo('=' * 80)

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
