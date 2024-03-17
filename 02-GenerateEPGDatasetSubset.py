#!/usr/bin/env python

import ariblib.constants
import jsonlines
import random
import time
import typer
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Annotated, Union

from utils.constants import EPGDatasetSubset, EPGDatasetSubsetInternal
from utils.edcb import CtrlCmdUtil


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
        weight *= 0.7
    ## スポーツ: 地上波で放送されるもののみ若干重みを大きくする
    elif data.major_genre_id == 0x1 and is_terrestrial(data.network_id):
        weight *= 1.5
    ## 国内ドラマ: 放送数がそう多くない割に重要なジャンルなので重みを大きくする (地上波のみ)
    elif data.major_genre_id == 0x3 and data.middle_genre_id == 0x0 and is_terrestrial(data.network_id):
        # 朝4時〜17時に放送される主婦向けの再放送や昼ドラを除いて適用する
        if not (4 <= start_time.hour <= 17):
            weight *= 3.2
    ## 地上波以外 (無料BSなど) の国内ドラマ: 過去の高齢者向け刑事ドラマ系が多すぎるので減らす
    elif data.major_genre_id == 0x3 and data.middle_genre_id == 0x0 and not is_terrestrial(data.network_id):
        weight *= 0.25
    ## 海外ドラマ: 高齢者しか見ない割に多すぎるので全体的に減らす
    elif data.major_genre_id == 0x3 and data.middle_genre_id == 0x1:
        weight *= 0.25
    ## バラエティ: 地上波で放送されるもののみ若干重みを大きくする
    elif data.major_genre_id == 0x5 and is_terrestrial(data.network_id):
        weight *= 1.1
    ## 映画: 数が少ない割に重要なジャンルなので重みを大きくする (地上波、無料BSのみ)
    elif data.major_genre_id == 0x6 and (is_terrestrial(data.network_id) or is_free_bs(data.network_id, data.service_id)):
        weight *= 2.2
        # 特にアニメ映画は少ない割に重要なので重みをさらに大きくする
        if data.middle_genre_id == 0x2:
            weight *= 1.7
    ## 国内アニメ: 重要なジャンルなので重みを大きくする (地上波、無料BSのみ)
    elif data.major_genre_id == 0x7 and data.middle_genre_id == 0x0 and (is_terrestrial(data.network_id) or is_free_bs(data.network_id, data.service_id)):
        # 朝4時〜20時に放送されるアニメを除いて適用する (つまり深夜アニメのみ)
        if not (4 <= start_time.hour <= 20):
            weight *= 2.2
    ## ドキュメンタリー・教養: 地上波で放送されるもののみ若干重みを大きくする
    elif data.major_genre_id == 0x8 and is_terrestrial(data.network_id):
        weight *= 1.1
    ## 趣味・教育: 見る人が少ないので若干減らす
    elif data.major_genre_id == 0xA:
        weight *= 0.8
    ## AT-X のアニメ: 例外的に少し重みを大きくする
    elif data.network_id == 0x0007 and data.service_id == 333 and data.major_genre_id == 0x7:
        weight *= 1.3

    return weight


app = typer.Typer()

@app.command()
def main(
    dataset_path: Annotated[Path, typer.Option(help='データ元の JSONL データセットのパス。', exists=True, file_okay=True, dir_okay=False)] = Path('epg_dataset.jsonl'),
    subset_path: Annotated[Path, typer.Option(help='生成するデータセットのサブセットのパス。', dir_okay=False)] = Path('epg_dataset_subset.jsonl'),
    subset_size: Annotated[int, typer.Option(help='生成するデータセットのサブセットのサイズ')] = 5000,
    start_date: Annotated[Union[datetime, None], typer.Option(help='サブセットとして抽出する番組範囲の開始日時。')] = None,
    end_date: Annotated[Union[datetime, None], typer.Option(help='サブセットとして抽出する番組範囲の終了日時。')] = None,
):
    """
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
    """

    TERRESTRIAL_PERCENTAGE = 0.65
    FREE_BS_PERCENTAGE = 0.25
    PAID_BS_CS_PERCENTAGE = 0.10

    if subset_path.exists():
        print(f'ファイル {subset_path} は既に存在しています。')
        return

    # tzinfo が None ならば JST に変換
    ## この時入力値は常に UTC+9 なので、astimezone() ではなく replace を使う
    if start_date is not None and start_date.tzinfo is None:
        start_date = start_date.replace(tzinfo=CtrlCmdUtil.TZ)
    if end_date is not None and end_date.tzinfo is None:
        end_date = end_date.replace(tzinfo=CtrlCmdUtil.TZ)
    print(f'サブセットとして抽出する番組範囲の開始日時: {start_date}')
    print(f'サブセットとして抽出する番組範囲の終了日時: {end_date}')

    start_time = time.time()

    all_epg_count = 0  # 重複している番組も含めた全データセットの件数
    all_epg_data: list[EPGDatasetSubsetInternal] = []
    terrestrial_data: list[EPGDatasetSubsetInternal] = []
    free_bs_data: list[EPGDatasetSubsetInternal] = []
    paid_bs_cs_data: list[EPGDatasetSubsetInternal] = []
    unique_keys = set()

    with jsonlines.open(dataset_path, 'r') as reader:
        for obj in reader:
            all_epg_count += 1
            data = EPGDatasetSubsetInternal.model_validate(obj)
            if meets_condition(data) is False:
                print(f'Skipping (condition not met): {data.id}')
                continue
            if start_date is not None and datetime.fromisoformat(data.start_time) < start_date:
                print(f'Skipping (before start date): {data.id}')
                continue
            if end_date is not None and datetime.fromisoformat(data.start_time) > end_date:
                print(f'Skipping (after end date): {data.id}')
                continue
            # 一意キーを作成
            unique_key = (data.title, data.description)
            if unique_key in unique_keys:
                print(f'Skipping (duplicate): {data.id}')
                continue
            unique_keys.add(unique_key)
            print(f'Processing: {data.id}')
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
    print(f'重複を除いた番組数: {len(unique_keys)}')

    def sample_data(data_list: list[EPGDatasetSubsetInternal], target_size: int) -> list[EPGDatasetSubsetInternal]:
        sampled_data = []
        selected_indices = set()
        data_list_length = len(data_list)
        for _ in range(target_size):
            if len(selected_indices) >= data_list_length:  # すべての要素が選択された場合、ループを抜ける
                break
            # 選択されていない要素の重みの合計を計算
            available_weights = [data.weight if index not in selected_indices else 0 for index, data in enumerate(data_list)]
            total_weight = sum(available_weights)
            if total_weight == 0:  # すべての要素の重みが0になった場合、ループを抜ける
                break
            # 重みに基づいて要素をランダムに選択
            chosen_index = random.choices(range(data_list_length), weights=available_weights, k=1)[0]
            selected_indices.add(chosen_index)
            sampled_data.append(data_list[chosen_index])
        return sampled_data

    subset_size_terrestrial = int(subset_size * TERRESTRIAL_PERCENTAGE)
    subset_size_free_bs = int(subset_size * FREE_BS_PERCENTAGE)
    subset_size_paid_bs_cs = int(subset_size * PAID_BS_CS_PERCENTAGE)

    subsets: list[EPGDatasetSubsetInternal] = []
    subsets += sample_data(terrestrial_data, subset_size_terrestrial)
    subsets += sample_data(free_bs_data, subset_size_free_bs)
    subsets += sample_data(paid_bs_cs_data, subset_size_paid_bs_cs)

    # ID でソート
    subsets.sort(key=lambda x: x.id)

    # 万が一 ID が重複している場合は警告を出して当該番組を除外
    unique_ids = set()
    for subset in subsets:
        if subset.id in unique_ids:
            print(f'Warning: ID が重複しています: {subset.id}')
            subsets.remove(subset)
        unique_ids.add(subset.id)

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
    print(f'地上波: {channel_counts["terrestrial"]: >4} 件 ({channel_counts["terrestrial"] / total_count * 100:.2f}%)')
    print(f'BS (無料放送): {channel_counts["free_bs"]: >4} 件 ({channel_counts["free_bs"] / total_count * 100:.2f}%)')
    print(f'BS (有料放送) & CS: {channel_counts["paid_bs_cs"]: >4} 件 ({channel_counts["paid_bs_cs"] / total_count * 100:.2f}%)')

    # 年ごとの割合を表示
    print('-' * 80)
    print('年ごとの割合:')
    for year, count in sorted(year_counts.items()):
        print(f'  {year}: {count: >4} 件 ({count / total_count * 100:.2f}%)')

    # 月ごとの割合を表示
    print('-' * 80)
    print('月ごとの割合:')
    for month, count in sorted(month_counts.items()):
        print(f'  {month}: {count: >4} 件 ({count / total_count * 100:.2f}%)')

    print('-' * 80)
    print('大分類ジャンルごとの割合:')
    for major_genre, count in sorted(major_genre_counts.items()):
        print(f'  {ariblib.constants.CONTENT_TYPE[major_genre][0]}: {count: >4} 件 ({count / total_count * 100:.2f}%)')

    print('-' * 80)
    print('中分類ジャンルごとの割合:')
    for genre, count in sorted(middle_genre_counts.items()):
        print(f'  {ariblib.constants.CONTENT_TYPE[genre[0]][0]} - {ariblib.constants.CONTENT_TYPE[genre[0]][1][genre[1]]}: {count: >4} 件 ({count / total_count * 100:.2f}%)')

    print('-' * 80)
    print(f'{subset_path} に書き込んでいます...')
    with jsonlines.open(subset_path, 'w') as writer:
        for subset in subsets:
            writer.write(subset.model_dump(mode='json', exclude={'weight'}))  # weight は出力しない

    elapsed_time = time.time() - start_time
    print(f'処理時間: {elapsed_time:.2f} 秒')
    print('-' * 80)

if __name__ == '__main__':
    app()
