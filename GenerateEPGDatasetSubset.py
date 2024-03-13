#!/usr/bin/env python

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
    if data.major_genre_id == 0x2 and data.middle_genre_id == 0x4:  # ショッピング番組は除外
        return False
    if data.major_genre_id >= 0xC:  # ジャンルIDが不明な番組は除外
        return False
    if not data.title:  # タイトルが空文字列の番組は除外
        return False
    return True

def get_weight(data: EPGDatasetSubset) -> float:
    start_time = datetime.fromisoformat(data.start_time)
    start_year = start_time.year
    weight = (start_year - 2019) / 5 + 1  # 2019年を1.0、2024年を2.0とする

    if data.major_genre_id == 0x3 and data.middle_genre_id == 0x0:  # 国内ドラマ
        weight *= 1.5  # 重みを1.5倍
    elif data.major_genre_id == 0x7 and data.middle_genre_id == 0x0:  # 国内アニメ
        weight *= 1.5  # 重みを1.5倍

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

    all_epg_data: list[EPGDatasetSubset] = []
    terrestrial_data: list[EPGDatasetSubset] = []
    free_bs_data: list[EPGDatasetSubset] = []
    paid_bs_cs_data: list[EPGDatasetSubset] = []
    unique_titles = set()

    with jsonlines.open(dataset_path, 'r') as reader:
        for obj in reader:
            data = EPGDatasetSubset.model_validate(obj)
            if not meets_condition(data):
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

    print(f'データセットに含まれる番組数: {len(all_epg_data)}')
    print(f'重複を除いた番組数: {len(unique_titles)}')

    weighted_data = [(data, get_weight(data)) for data in all_epg_data]
    weighted_data.sort(key=lambda x: x[1], reverse=True)

    subsets: list[EPGDatasetSubset] = []
    subsets.extend(random.sample(terrestrial_data, int(subset_size * 0.6)))
    subsets.extend(random.sample(free_bs_data, int(subset_size * 0.3)))
    subsets.extend(random.sample(paid_bs_cs_data, int(subset_size * 0.1)))

    # ジャンル別の件数を確認
    genre_counts: defaultdict[tuple[int, int], int] = defaultdict(int)
    for data in subsets:
        genre_counts[(data.major_genre_id, data.middle_genre_id)] += 1

    total_count = len(subsets)
    drama_count = genre_counts[(0x3, 0x0)]
    anime_count = genre_counts[(0x7, 0x0)]

    print(f'国内ドラマ: {drama_count} 件 ({drama_count / total_count * 100:.2f}%)')
    print(f'国内アニメ: {anime_count} 件 ({anime_count / total_count * 100:.2f}%)')

    if drama_count < subset_size * 0.15 or anime_count < subset_size * 0.15:
        print('国内ドラマまたは国内アニメの件数が少ないため、再サンプリングを行います...')
        drama_data = [data for data in all_epg_data if data.major_genre_id == 0x3 and data.middle_genre_id == 0x0]
        anime_data = [data for data in all_epg_data if data.major_genre_id == 0x7 and data.middle_genre_id == 0x0]

        while drama_count < subset_size * 0.15:
            subsets.append(random.choice(drama_data))
            drama_count += 1

        while anime_count < subset_size * 0.15:
            subsets.append(random.choice(anime_data))
            anime_count += 1

    print(f'{subset_path} に書き込んでいます...')
    with jsonlines.open(subset_path, 'w') as writer:
        for subset in subsets:
            writer.write(subset.model_dump(mode='json'))


if __name__ == '__main__':
    app()
