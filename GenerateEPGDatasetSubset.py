#!/usr/bin/env python

import ariblib.constants
import jsonlines
import typer
import random
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
    if not data.title:
        return False
    return True

def get_weight(data: EPGDatasetSubset) -> float:
    start_time = datetime.fromisoformat(data.start_time)
    start_date = datetime(2019, 10, 1)  # 基準日を2019年10月1日に設定
    months_diff = (start_time.year - start_date.year) * 12 + start_time.month - start_date.month
    months_diff = max(months_diff, 0)  # months_diff が負の値になることを防ぐ
    weight = months_diff / 60 + 1  # 2019年10月を 1.0 、2024年3月を 2.0 とするための計算

    if data.major_genre_id == 0x3 and data.middle_genre_id == 0x0:  # 国内ドラマ
        weight *= 1.5  # 重みを 1.5 倍
    elif data.major_genre_id == 0x7 and data.middle_genre_id == 0x0:  # 国内アニメ
        weight *= 1.5  # 重みを 1.5 倍

    return weight


app = typer.Typer()

@app.command()
def main(
    dataset_path: Annotated[Path, typer.Option(help='データ元の JSONL データセットのパス。', exists=True, file_okay=True, dir_okay=False)] = Path('epg_dataset.jsonl'),
    subset_path: Annotated[Path, typer.Option(help='生成するデータセットのサブセットのパス。', dir_okay=False)] = Path('epg_dataset_subset.jsonl'),
    subset_size: Annotated[int, typer.Option(help='生成するデータセットのサブセットのサイズ')] = 5000,
):
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
            all_epg_data.append(data)
            if is_terrestrial(data.network_id):
                terrestrial_data.append(data)
            elif is_free_bs(data.network_id, data.service_id):
                free_bs_data.append(data)
            elif is_paid_bs_cs(data.network_id, data.service_id):
                paid_bs_cs_data.append(data)

    print(f'データセットに含まれる番組数: {all_epg_count}')
    print(f'重複を除いた番組数: {len(unique_titles)}')

    weighted_data = [(data, get_weight(data)) for data in all_epg_data]
    weighted_data.sort(key=lambda x: x[1], reverse=True)

    subsets: list[EPGDatasetSubset] = []
    initial_terrestrial_count = min(len(terrestrial_data), int(subset_size * 0.6))
    initial_free_bs_count = min(len(free_bs_data), int(subset_size * 0.3))
    initial_paid_bs_cs_count = min(len(paid_bs_cs_data), int(subset_size * 0.1))

    subsets.extend(random.sample(terrestrial_data, initial_terrestrial_count))
    subsets.extend(random.sample(free_bs_data, initial_free_bs_count))
    subsets.extend(random.sample(paid_bs_cs_data, initial_paid_bs_cs_count))

    # ジャンル別の件数を確認
    middle_genre_counts: defaultdict[tuple[int, int], int] = defaultdict(int)
    for data in subsets:
        middle_genre_counts[(data.major_genre_id, data.middle_genre_id)] += 1

    total_count = len(subsets)
    drama_count = middle_genre_counts[(0x3, 0x0)]
    anime_count = middle_genre_counts[(0x7, 0x0)]

    print(f'国内ドラマ: {drama_count} 件 ({drama_count / total_count * 100:.2f}%)')
    print(f'国内アニメ: {anime_count} 件 ({anime_count / total_count * 100:.2f}%)')

    required_drama_count = int(subset_size * 0.15)
    required_anime_count = int(subset_size * 0.15)

    if drama_count < required_drama_count or anime_count < required_anime_count:
        print('国内ドラマまたは国内アニメの件数が少ないため、再サンプリングを行います...')
        additional_drama_count = required_drama_count - drama_count
        additional_anime_count = required_anime_count - anime_count

        # 再サンプリング時にも割合を保持
        additional_terrestrial_data = [data for data in terrestrial_data if data.major_genre_id == 0x3 and data.middle_genre_id == 0x0 or data.major_genre_id == 0x7 and data.middle_genre_id == 0x0]
        additional_free_bs_data = [data for data in free_bs_data if data.major_genre_id == 0x3 and data.middle_genre_id == 0x0 or data.major_genre_id == 0x7 and data.middle_genre_id == 0x0]
        additional_paid_bs_cs_data = [data for data in paid_bs_cs_data if data.major_genre_id == 0x3 and data.middle_genre_id == 0x0 or data.major_genre_id == 0x7 and data.middle_genre_id == 0x0]

        subsets.extend(random.sample(additional_terrestrial_data, min(len(additional_terrestrial_data), int(additional_drama_count * 0.6 + additional_anime_count * 0.6))))
        subsets.extend(random.sample(additional_free_bs_data, min(len(additional_free_bs_data), int(additional_drama_count * 0.3 + additional_anime_count * 0.3))))
        subsets.extend(random.sample(additional_paid_bs_cs_data, min(len(additional_paid_bs_cs_data), int(additional_drama_count * 0.1 + additional_anime_count * 0.1))))

        # 総数が subset_size を超えないように調整
        if len(subsets) > subset_size:
            subsets = random.sample(subsets, subset_size)

    # ID 順にソート
    subsets.sort(key=lambda x: x.id)

    # 最終的なサブセットデータセットの割合を月ごと、チャンネル種別ごと、ジャンルごとに確認
    major_genre_counts = defaultdict(int)
    middle_genre_counts = defaultdict(int)
    channel_counts = defaultdict(int)
    year_counts = defaultdict(int)
    month_counts = defaultdict(int)
    for data in subsets:
        major_genre_counts[data.major_genre_id] += 1
        middle_genre_counts[(data.major_genre_id, data.middle_genre_id)] += 1
        if is_terrestrial(data.network_id):
            channel_counts['terrestrial'] += 1
        elif is_free_bs(data.network_id, data.service_id):
            channel_counts['free_bs'] += 1
        elif is_paid_bs_cs(data.network_id, data.service_id):
            channel_counts['paid_bs_cs'] += 1
        year_counts[datetime.fromisoformat(data.start_time).year] += 1
        month_counts[datetime.fromisoformat(data.start_time).strftime('%Y-%m')] += 1

    total_count = len(subsets)
    print(f'サブセットの総件数: {total_count}')

    # チャンネル種別ごとの割合を表示
    print(f'地上波: {channel_counts["terrestrial"]} 件 ({channel_counts["terrestrial"] / total_count * 100:.2f}%)')
    print(f'BS (無料放送): {channel_counts["free_bs"]} 件 ({channel_counts["free_bs"] / total_count * 100:.2f}%)')
    print(f'BS (有料放送) & CS: {channel_counts["paid_bs_cs"]} 件 ({channel_counts["paid_bs_cs"] / total_count * 100:.2f}%)')

    # 年ごとの割合を表示
    print('年ごとの割合:')
    for year, count in sorted(year_counts.items()):
        print(f'{year}: {count} 件 ({count / total_count * 100:.2f}%)')

    # 月ごとの割合を表示
    print('月ごとの割合:')
    for month, count in sorted(month_counts.items()):
        print(f'{month}: {count} 件 ({count / total_count * 100:.2f}%)')

    print('大分類ジャンルごとの割合:')
    for major_genre, count in sorted(major_genre_counts.items()):
        print(f'{ariblib.constants.CONTENT_TYPE[major_genre][0]}: {count} 件 ({count / total_count * 100:.2f}%)')

    print('中分類ジャンルごとの割合:')
    for genre, count in sorted(middle_genre_counts.items()):
        print(f'{ariblib.constants.CONTENT_TYPE[genre[0]][0]}/{ariblib.constants.CONTENT_TYPE[genre[0]][1][genre[1]]}: {count} 件 ({count / total_count * 100:.2f}%)')

    print(f'{subset_path} に書き込んでいます...')
    with jsonlines.open(subset_path, 'w') as writer:
        for subset in subsets:
            writer.write(subset.model_dump(mode='json'))


if __name__ == '__main__':
    app()
