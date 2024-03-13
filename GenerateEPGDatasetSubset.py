#!/usr/bin/env python

import ariblib.constants
import gc
import pandas as pd
import typer
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any


def is_terrestrial(network_id: int) -> bool:
    return 0x7880 <= network_id <= 0x7FE8

def is_free_bs(network_id: int, service_id: int) -> bool:
    return network_id == 0x0004 and not (191 <= service_id <= 209 or 234 <= service_id <= 256)

def is_paid_bs_cs(network_id: int, service_id: int) -> bool:
    return (network_id == 0x0006 or network_id == 0x0007) or (network_id == 0x0004 and (191 <= service_id <= 209 or 234 <= service_id <= 256))

def get_weight(data: dict[str, Any]) -> float:
    start_time = datetime.fromisoformat(data['start_time'])
    start_date = datetime(2019, 10, 1)  # 基準日を2019年10月1日に設定
    months_diff = (start_time.year - start_date.year) * 12 + start_time.month - start_date.month
    months_diff = max(months_diff, 0)  # months_diff が負の値になることを防ぐ
    weight = months_diff / 60 + 1  # 2019年10月を 1.0 、2024年3月を 2.0 とするための計算

    if data['major_genre_id'] == 0x3 and data['middle_genre_id'] == 0x0:  # 国内ドラマ
        weight *= 1.5  # 重みを 1.5 倍
    elif data['major_genre_id'] == 0x7 and data['middle_genre_id'] == 0x0:  # 国内アニメ
        weight *= 1.5  # 重みを 1.5 倍

    return weight


app = typer.Typer()

@app.command()
def main(
    dataset_path: Annotated[Path, typer.Option(help='データ元の JSONL データセットのパス。', exists=True, file_okay=True, dir_okay=False)] = Path('epg_dataset.jsonl'),
    subset_path: Annotated[Path, typer.Option(help='生成するデータセットのサブセットのパス。', dir_okay=False)] = Path('epg_dataset_subset.jsonl'),
    subset_size: Annotated[int, typer.Option(help='生成するデータセットのサブセットのサイズ')] = 5000,
    chunk_size: Annotated[int, typer.Option(help='チャンクサイズ')] = 1000000,
):
    """
    要件：
    - 地上波放送の番組を 60%、BS (無料放送) の番組を 30%、BS (有料放送) & CS の番組を 10% とする
    - 重複している番組は除外する
    - ショッピング番組は除外する
    - 不明なジャンル ID の番組は除外する
    - ジャンル自体が EPG データに含まれていない番組は除外する
    - タイトルが空文字列の番組は除外する
    - 重み付けされたデータを適切にサンプリングして、subset_size で指定されたサイズのサブセットを生成する
    - 大元の JSONL データの各行には "raw" という EDCB から取得した生データの辞書が含まれているが、サブセットでは利用しないので除外する
    """

    TERRESTRIAL_PERCENTAGE = 0.6
    FREE_BS_PERCENTAGE = 0.3
    PAID_BS_CS_PERCENTAGE = 0.1

    if subset_path.exists():
        print(f'ファイル {subset_path} は既に存在しています。')
        return

    print(f'データセット {dataset_path} を読み込んでいます...')
    reader = pd.read_json(dataset_path, lines=True, chunksize=chunk_size, dtype={
        'id': 'str',
        'network_id': 'int16',
        'service_id': 'int16',
        'transport_stream_id': 'int16',
        'event_id': 'int16',
        'start_time': 'str',
        'duration': 'int32',
        'title': 'str',
        'title_without_symbols': 'str',
        'description': 'str',
        'description_without_symbols': 'str',
        'major_genre_id': 'int8',
        'middle_genre_id': 'int8',
    })
    print(f'データセット {dataset_path} を読み込みました。')

    terrestrial_chunks = []
    free_bs_chunks = []
    paid_bs_cs_chunks = []

    for chunk_idx, chunk in enumerate(reader, start=1):
        print(f'Processing chunk {chunk_idx}...')

        chunk = chunk[[
            'id',
            'network_id',
            'service_id',
            'transport_stream_id',
            'event_id',
            'start_time',
            'duration',
            'title',
            'title_without_symbols',
            'description',
            'description_without_symbols',
            'major_genre_id',
            'middle_genre_id',
        ]]
        chunk = chunk.dropna(subset=['title'])
        chunk.loc[chunk['major_genre_id'] == -1, ['major_genre_id', 'middle_genre_id']] = [None, None]
        chunk = chunk.drop_duplicates(subset=['title', 'description'])

        chunk['channel_type'] = chunk.apply(lambda x: 'terrestrial' if is_terrestrial(x['network_id']) else (
            'free_bs' if is_free_bs(x['network_id'], x['service_id']) else (
                'paid_bs_cs' if is_paid_bs_cs(x['network_id'], x['service_id']) else 'unknown'
            )
        ), axis=1)

        chunk['weight'] = chunk.apply(lambda x: get_weight(x), axis=1)

        terrestrial_chunk = chunk[chunk['channel_type'] == 'terrestrial'].sample(frac=TERRESTRIAL_PERCENTAGE, weights='weight', replace=False)
        free_bs_chunk = chunk[chunk['channel_type'] == 'free_bs'].sample(frac=FREE_BS_PERCENTAGE, weights='weight', replace=False)
        paid_bs_cs_chunk = chunk[chunk['channel_type'] == 'paid_bs_cs'].sample(frac=PAID_BS_CS_PERCENTAGE, weights='weight', replace=False)

        terrestrial_chunks.append(terrestrial_chunk)
        free_bs_chunks.append(free_bs_chunk)
        paid_bs_cs_chunks.append(paid_bs_cs_chunk)

        del chunk, terrestrial_chunk, free_bs_chunk, paid_bs_cs_chunk
        gc.collect()

    subsets_df = pd.concat(terrestrial_chunks + free_bs_chunks + paid_bs_cs_chunks, ignore_index=True)
    subsets_df = subsets_df.sample(frac=1).reset_index(drop=True)

    total_count = len(subsets_df)
    print(f'サブセットデータセットのサイズ: {total_count} 件')
    channel_counts = subsets_df['channel_type'].value_counts()
    year_counts = subsets_df['start_time'].apply(lambda x: datetime.fromisoformat(x).year).value_counts()
    month_counts = subsets_df['start_time'].apply(lambda x: datetime.fromisoformat(x).strftime('%Y-%m')).value_counts()
    major_genre_counts = subsets_df['major_genre_id'].value_counts()
    middle_genre_counts = subsets_df.groupby(['major_genre_id', 'middle_genre_id']).size()

    print('チャンネル種別ごとの割合:')
    for channel_type, count in channel_counts.items():
        print(f'{channel_type}: {count / total_count * 100:.2f}% ({count} 件)')

    print('年ごとの割合:')
    for year, count in year_counts.items():
        print(f'{year}: {count / total_count * 100:.2f}% ({count} 件)')

    print('月ごとの割合:')
    for month, count in month_counts.items():
        print(f'{month}: {count / total_count * 100:.2f}% ({count} 件)')

    print('大分類ジャンルごとの割合:')
    for major_genre, count in major_genre_counts.items():
        if major_genre is not None:
            print(f'{ariblib.constants.CONTENT_TYPE[major_genre][0]}: {count / total_count * 100:.2f}% ({count} 件)')

    print('中分類ジャンルごとの割合:')
    for (major_genre, middle_genre), count in middle_genre_counts.items():
        if major_genre is not None and middle_genre is not None:
            print(f'{ariblib.constants.CONTENT_TYPE[major_genre][0]}/{ariblib.constants.CONTENT_TYPE[major_genre][1][middle_genre]}: {count / total_count * 100:.2f}% ({count} 件)')

    print(f'{subset_path} に書き込んでいます...')
    subsets_df.to_json(subset_path, orient='records', lines=True)


if __name__ == '__main__':
    app()
