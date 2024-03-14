#!/usr/bin/env python

import jsonlines
import time
import typer
from pathlib import Path
from typing import Annotated

from .GenerateEPGDatasetSubset import EPGDatasetSubset


def generate_annotations(subset: EPGDatasetSubset) -> EPGDatasetSubset:
    """ Gemini 1.5 Pro によるアノテーション自動生成 """

    return subset


app = typer.Typer()

@app.command()
def main(
    subset_path: Annotated[Path, typer.Option(help='アノテーションを自動生成・追加するデータセットのサブセットのパス。', dir_okay=False)] = Path('epg_dataset_subset.jsonl'),
):
    if not subset_path.exists():
        print(f'ファイル {subset_path} は存在しません。')
        return

    start_time = time.time()

    print('-' * 80)
    modified_subsets: list[EPGDatasetSubset] = []
    with jsonlines.open(subset_path, 'r') as reader:
        for obj in reader:
            subset = EPGDatasetSubset.model_validate(obj)
            print(f'{subset.id} のアノテーションを自動生成しています...')
            print(f'番組名:   {subset.title}')
            print(f'番組概要: {subset.description}')
            modified_subset = generate_annotations(subset)
            print(f'{subset.id} のアノテーションを自動生成しました。')
            print(f'シリーズタイトル: {modified_subset.series_title}')
            print(f'話数: {modified_subset.episode_number} / サブタイトル: {modified_subset.subtitle}')
            modified_subsets.append(modified_subset)
            print('-' * 80)

    print('-' * 80)
    print(f'{subset_path} に書き込んでいます...')
    with jsonlines.open(subset_path, 'w') as writer:
        for subset in modified_subsets:
            writer.write(subset.model_dump(mode='json'))

    elapsed_time = time.time() - start_time
    print(f'処理時間: {elapsed_time:.2f} 秒')
    print('-' * 80)

if __name__ == '__main__':
    app()
