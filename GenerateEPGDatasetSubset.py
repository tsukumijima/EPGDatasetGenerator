#!/usr/bin/env python

import jsonlines
import typer
import random
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
    # ジャンル ID が不明な番組は除外
    if data.major_genre_id >= 0xC:
        return False
    # タイトルが空文字列の番組は除外
    if not data.title:
        return False
    return True


app = typer.Typer()

@app.command()
def main(
    dataset_path: Annotated[Path, typer.Option(help='データ元の JSONL データセットのパス。', exists=True, file_okay=True, dir_okay=False)] = Path('epg_dataset.jsonl'),
    subset_path: Annotated[Path, typer.Option(help='生成するデータセットのサブセットのパス。', dir_okay=False)] = Path('epg_dataset_subset.jsonl'),
    subset_size: Annotated[int, typer.Option(help='生成するデータセットのサブセットのサイズ')] = 5000,
):
    # 既にファイルが存在している場合は終了
    if subset_path.exists():
        print(f'ファイル {subset_path} は既に存在しています。')
        return

    all_epg_count: int = 0
    terrestrial_data: list[EPGDatasetSubset] = []
    free_bs_data: list[EPGDatasetSubset] = []
    paid_bs_cs_data: list[EPGDatasetSubset] = []
    unique_titles = set()

    with jsonlines.open(dataset_path, 'r') as reader:
        for obj in reader:
            data = EPGDatasetSubset.model_validate(obj)
            all_epg_count += 1
            if not meets_condition(data):
                continue
            title_desc_key = (data.title, data.description)
            if title_desc_key in unique_titles:
                continue
            print(f'Processing: {data.id}')
            unique_titles.add(title_desc_key)
            if is_terrestrial(data.network_id):
                terrestrial_data.append(data)
            elif is_free_bs(data.network_id, data.service_id):
                free_bs_data.append(data)
            elif is_paid_bs_cs(data.network_id, data.service_id):
                paid_bs_cs_data.append(data)

    print(f'データセットに含まれる番組数: {all_epg_count}')

    # 地デジ: 60% / BS (無料放送): 30% / BS (有料放送) & CS: 10% の割合でランダムにサンプリング
    subsets: list[EPGDatasetSubset] = []
    subsets.extend(random.sample(terrestrial_data, int(subset_size * 0.6)))
    subsets.extend(random.sample(free_bs_data, int(subset_size * 0.3)))
    subsets.extend(random.sample(paid_bs_cs_data, int(subset_size * 0.1)))

    # ID でソート
    ## ID は最初が番組開始時刻になっているため、ソートすることで自動的に時系列になる
    subsets.sort(key=lambda x: x.id)

    print(f'{subset_path} に書き込んでいます...')
    with jsonlines.open(subset_path, 'w') as writer:
        for subset in subsets:
            writer.write(subset.model_dump(mode='json'))


if __name__ == '__main__':
    app()
