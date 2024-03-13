#!/usr/bin/env python

import ariblib.constants
import jsonlines
import random
import typer
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel
from typing import Annotated


class EPGDatasetSubset(BaseModel):
    id: str
    network_id: int
    service_id: int
    transport_stream_id: int
    event_id: int
    start_time: str
    duration: int
    title: str
    title_without_symbols: str
    description: str
    description_without_symbols: str
    major_genre_id: int
    middle_genre_id: int
    weight: float = 1.0  # 内部でのみ使用


def is_terrestrial(network_id: int) -> bool:
    return 0x7880 <= network_id <= 0x7FE8

def is_free_bs(network_id: int, service_id: int) -> bool:
    return network_id == 0x0004 and not (191 <= service_id <= 209 or 234 <= service_id <= 256)

def is_paid_bs_cs(network_id: int, service_id: int) -> bool:
    return (network_id == 0x0006 or network_id == 0x0007) or (network_id == 0x0004 and (191 <= service_id <= 209 or 234 <= service_id <= 256))

def meets_condition(data: EPGDatasetSubset) -> bool:
    # ref: https://github.com/youzaka/ariblib/blob/master/ariblib/constants.py
    # ショッピング番組は除外
    if data.major_genre_id == 0x2 and data.middle_genre_id == 0x4:
        return False
    # ジャンルIDが不明な番組は除外
    if data.major_genre_id >= 0xC:
        return False
    # ジャンル自体が EPG データに含まれていない場合は除外
    if data.major_genre_id == -1 or data.middle_genre_id == -1:
        return False
    # タイトルが空文字列の番組は除外
    if data.title.strip() == '':
        return False
    return True

def get_weight(data: EPGDatasetSubset) -> float:

    # 新しい番組ほど重みを大きくする
    start_time = datetime.fromisoformat(data.start_time)
    start_date = datetime(2019, 10, 1)  # 基準日を2019年10月1日に設定
    months_diff = (start_time.year - start_date.year) * 12 + start_time.month - start_date.month
    months_diff = max(months_diff, 0)  # months_diff が負の値になることを防ぐ
    weight = months_diff / 60 + 1  # 2019年10月を 1.0 、2024年3月を 2.0 とするための計算

    # 下記は実際の割合に基づいてサブセット化用の重みを調整している
    ## 定時ニュース: 基本録画されないので重みを減らす
    if data.major_genre_id == 0x0 and data.middle_genre_id == 0x0:
        weight *= 0.4
    ## 国内アニメ: 重要なジャンルなので重みを大きくする
    elif data.major_genre_id == 0x7 and data.middle_genre_id == 0x0:
        weight *= 1.8
    ## 国内ドラマ: 重要なジャンルなので重みを大きくする
    elif data.major_genre_id == 0x3 and data.middle_genre_id == 0x0:
        weight *= 1.8
    ## 海外ドラマ: 多すぎるので減らす
    elif data.major_genre_id == 0x3 and data.middle_genre_id == 0x1:
        weight *= 0.35
    ## 映画: 数が少ない割に重要なジャンルなので重みを大きくする
    elif data.major_genre_id == 0x6:
        weight *= 3.0

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
    - 地上波: 60%、BS (無料放送): 30%、BS (有料放送) + CS: 10% とする
    - 重複している番組は除外する
    - ショッピング番組は除外する
    - 不明なジャンル ID の番組は除外する
    - ジャンル自体が EPG データに含まれていない番組は除外する
    - タイトルが空文字列の番組は除外する
    - 重み付けされたデータを適切にサンプリングして、subset_size で指定されたサイズのサブセットを生成する
    - 大元の JSONL データの各行には "raw" という EDCB から取得した生データの辞書が含まれているが、サブセットでは利用しないので除外する
    - 最終的に ID でソートされた JSONL データが生成される
    """

    TERRESTRIAL_PERCENTAGE = 0.6
    FREE_BS_PERCENTAGE = 0.3
    PAID_BS_CS_PERCENTAGE = 0.1

    if subset_path.exists():
        print(f'ファイル {subset_path} は既に存在しています。')
        return

    all_epg_count = 0  # 重複している番組も含めた全データセットの件数
    all_epg_data: list[EPGDatasetSubset] = []
    terrestrial_data: list[EPGDatasetSubset] = []
    free_bs_data: list[EPGDatasetSubset] = []
    paid_bs_cs_data: list[EPGDatasetSubset] = []
    unique_titles = set()

    with jsonlines.open(dataset_path, 'r') as reader:
        for obj in reader:
            all_epg_count += 1
            data = EPGDatasetSubset.model_validate(obj)
            if meets_condition(data) is False:
                continue
            title_desc_key = (data.title, data.description)
            if title_desc_key in unique_titles:
                continue
            print(f'Processing: {data.id}')
            unique_titles.add(title_desc_key)
            data.weight = get_weight(data)
            all_epg_data.append(data)
            if is_terrestrial(data.network_id):
                terrestrial_data.append(data)
            elif is_free_bs(data.network_id, data.service_id):
                free_bs_data.append(data)
            elif is_paid_bs_cs(data.network_id, data.service_id):
                paid_bs_cs_data.append(data)

    print('-' * 80)
    print(f'データセットに含まれる番組数: {all_epg_count}')
    print(f'重複を除いた番組数: {len(unique_titles)}')

    def sample_data(data_list: list[EPGDatasetSubset], target_size: int) -> list[EPGDatasetSubset]:
        if len(data_list) == 0:
            return []
        total_weight = sum(data.weight for data in data_list)
        return random.choices(data_list, weights=[data.weight / total_weight for data in data_list], k=target_size)

    subset_size_terrestrial = int(subset_size * TERRESTRIAL_PERCENTAGE)
    subset_size_free_bs = int(subset_size * FREE_BS_PERCENTAGE)
    subset_size_paid_bs_cs = int(subset_size * PAID_BS_CS_PERCENTAGE)

    subsets: list[EPGDatasetSubset] = []
    subsets += sample_data(terrestrial_data, subset_size_terrestrial)
    subsets += sample_data(free_bs_data, subset_size_free_bs)
    subsets += sample_data(paid_bs_cs_data, subset_size_paid_bs_cs)

    # ID でソート
    subsets.sort(key=lambda x: x.id)

    # 最終的なサブセットデータセットの割合を月ごと、チャンネル種別ごと、ジャンルごとに確認
    channel_counts = defaultdict(int)
    year_counts = defaultdict(int)
    month_counts = defaultdict(int)
    major_genre_counts = defaultdict(int)
    middle_genre_counts = defaultdict(int)
    for data in subsets:
        if is_terrestrial(data.network_id):
            channel_counts['terrestrial'] += 1
        elif is_free_bs(data.network_id, data.service_id):
            channel_counts['free_bs'] += 1
        elif is_paid_bs_cs(data.network_id, data.service_id):
            channel_counts['paid_bs_cs'] += 1
        year_counts[datetime.fromisoformat(data.start_time).year] += 1
        month_counts[datetime.fromisoformat(data.start_time).strftime('%Y-%m')] += 1
        major_genre_counts[data.major_genre_id] += 1
        middle_genre_counts[(data.major_genre_id, data.middle_genre_id)] += 1

    total_count = len(subsets)
    print('-' * 80)
    print(f'サブセットの総件数: {total_count}')

    # チャンネル種別ごとの割合を表示
    print('-' * 80)
    print(f'地上波: {channel_counts["terrestrial"]: >8} 件 ({channel_counts["terrestrial"] / total_count * 100:.2f}%)')
    print(f'BS (無料放送): {channel_counts["free_bs"]: >8} 件 ({channel_counts["free_bs"] / total_count * 100:.2f}%)')
    print(f'BS (有料放送) & CS: {channel_counts["paid_bs_cs"]: >8} 件 ({channel_counts["paid_bs_cs"] / total_count * 100:.2f}%)')

    # 年ごとの割合を表示
    print('-' * 80)
    print('年ごとの割合:')
    for year, count in sorted(year_counts.items()):
        print(f'  {year}: {count: >8} 件 ({count / total_count * 100:.2f}%)')

    # 月ごとの割合を表示
    print('-' * 80)
    print('月ごとの割合:')
    for month, count in sorted(month_counts.items()):
        print(f'  {month}: {count: >8} 件 ({count / total_count * 100:.2f}%)')

    print('-' * 80)
    print('大分類ジャンルごとの割合:')
    for major_genre, count in sorted(major_genre_counts.items()):
        print(f'  {ariblib.constants.CONTENT_TYPE[major_genre][0]}: {count: >8} 件 ({count / total_count * 100:.2f}%)')

    print('-' * 80)
    print('中分類ジャンルごとの割合:')
    for genre, count in sorted(middle_genre_counts.items()):
        print(f'  {ariblib.constants.CONTENT_TYPE[genre[0]][0]} - {ariblib.constants.CONTENT_TYPE[genre[0]][1][genre[1]]}: {count: >8} 件 ({count / total_count * 100:.2f}%)')

    print('-' * 80)
    print(f'{subset_path} に書き込んでいます...')
    with jsonlines.open(subset_path, 'w') as writer:
        for subset in subsets:
            writer.write(subset.model_dump(mode='json', exclude={'weight'}))

if __name__ == '__main__':
    app()
