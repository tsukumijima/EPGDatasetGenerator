#!/usr/bin/env python

import asyncio
import jsonlines
import time
import typer
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated

from utils.constants import EPGDataset
from utils.edcb import CtrlCmdUtil, EDCBUtil, ServiceEventInfo
from utils.epg import FormatString, RemoveSymbols


DEFAULT_INCLUDE_NETWORK_IDS = [
    0x0004,  # BS
    0x0006,  # CS1
    0x0007,  # CS2
    32736,   # NHK総合1・東京
    32737,   # NHKEテレ1東京
    32738,   # 日テレ
    32741,   # テレビ朝日
    32739,   # TBS
    32742,   # テレビ東京
    32740,   # フジテレビ
    32391,   # TOKYO MX
]

app = typer.Typer()

@app.command()
def main(
    dataset_path: Annotated[Path, typer.Option(help='保存先の JSONL ファイルのパス。')] = Path('epg_dataset.jsonl'),
    edcb_host: Annotated[str, typer.Option(help='ネットワーク接続する EDCB のホスト名。')] = '127.0.0.1',
    start_date: Annotated[datetime, typer.Option(help='過去 EPG データの取得開始日時 (UTC+9) 。')] = datetime.now() - timedelta(days=1),
    end_date: Annotated[datetime, typer.Option(help='過去 EPG データの取得終了日時 (UTC+9)。')] = datetime.now(),
    include_network_ids: Annotated[list[int], typer.Option(help='取得対象のネットワーク ID のリスト。', show_default=True)] = DEFAULT_INCLUDE_NETWORK_IDS,
):
    # 既にファイルが存在している場合は終了
    if dataset_path.exists():
        print(f'ファイル {dataset_path} は既に存在しています。')
        return

    start_time = time.time()

    # tzinfo が None ならば JST に変換
    ## この時入力値は常に UTC+9 なので、astimezone() ではなく replace を使う
    if start_date.tzinfo is None:
        start_date = start_date.replace(tzinfo=CtrlCmdUtil.TZ)
    if end_date.tzinfo is None:
        end_date = end_date.replace(tzinfo=CtrlCmdUtil.TZ)
    print(f'過去 EPG データの取得開始日時: {start_date}')
    print(f'過去 EPG データの取得終了日時: {end_date}')

    # CtrlCmdUtil インスタンスを生成
    edcb = CtrlCmdUtil()
    edcb.setNWSetting(edcb_host, 4510)
    edcb.setConnectTimeOutSec(60)  # かなり時間かかることも見据えて長めに設定

    # 重複する番組を除外するためのセット
    unique_set = set()

    # 古い日付から EPG データを随時 JSONL ファイルに保存
    with jsonlines.open(dataset_path, mode='w') as writer:

        # 1 週間ごとに EDCB から過去の EPG データを取得
        ## sendEnumPgArc は 1 回のリクエストで取得できるデータ量に制限があるため、1 週間ごとに取得する
        current_start_date = start_date
        while current_start_date < end_date:
            current_end_date = current_start_date + timedelta(weeks=1)
            if current_end_date > end_date:
                current_end_date = end_date

            print(f'取得期間: {current_start_date} ~ {current_end_date}')
            service_event_info_list: list[ServiceEventInfo] = []

            # EDCB から指定期間の EPG データを取得
            result: list[ServiceEventInfo] | None = asyncio.run(edcb.sendEnumPgArc([
                # 絞り込み対象のネットワーク ID・トランスポートストリーム ID・サービス ID に掛けるビットマスク (?????)
                ## よく分かってないけどとりあえずこれで全番組が対象になる
                0xffffffffffff,
                # 絞り込み対象のネットワーク ID・トランスポートストリーム ID・サービス ID
                ## (network_id << 32 | transport_stream_id << 16 | service_id) の形式で指定しなければならないらしい
                ## よく分かってないけどとりあえずこれで全番組が対象になる
                0xffffffffffff,
                # 絞り込み対象の番組開始時刻の最小値
                EDCBUtil.datetimeToFileTime(current_start_date, tz=CtrlCmdUtil.TZ),
                # 絞り込み対象の番組開始時刻の最大値 (自分自身を含まず、番組「開始」時刻が指定した時刻より前の番組が対象になる)
                # たとえば 11:00:00 ならば 10:59:59 までの番組が対象になるし、11:00:01 ならば 11:00:00 までの番組が対象になる
                EDCBUtil.datetimeToFileTime(current_end_date, tz=CtrlCmdUtil.TZ),
            ]))
            if result is None:
                print('Warning: 過去 EPG データの取得に失敗しました。')
            else:
                service_event_info_list.extend(result)

            # もし「現在処理中の」取得終了日時が現在時刻よりも未来の場合、別の API を使って現在時刻以降の EPG データを取得
            if current_end_date > datetime.now(tz=CtrlCmdUtil.TZ):
                print('取得終了日時が現在時刻よりも未来なので、現在時刻以降の EPG データも取得します。')
                result: list[ServiceEventInfo] | None = asyncio.run(edcb.sendEnumPgInfoEx([
                    # 絞り込み対象のネットワーク ID・トランスポートストリーム ID・サービス ID に掛けるビットマスク (?????)
                    ## よく分かってないけどとりあえずこれで全番組が対象になる
                    0xffffffffffff,
                    # 絞り込み対象のネットワーク ID・トランスポートストリーム ID・サービス ID
                    ## (network_id << 32 | transport_stream_id << 16 | service_id) の形式で指定しなければならないらしい
                    ## よく分かってないけどとりあえずこれで全番組が対象になる
                    0xffffffffffff,
                    # 絞り込み対象の番組開始時刻の最小値
                    EDCBUtil.datetimeToFileTime(current_start_date, tz=CtrlCmdUtil.TZ),
                    # 絞り込み対象の番組開始時刻の最大値 (自分自身を含まず、番組「開始」時刻が指定した時刻より前の番組が対象になる)
                    # たとえば 11:00:00 ならば 10:59:59 までの番組が対象になるし、11:00:01 ならば 11:00:00 までの番組が対象になる
                    EDCBUtil.datetimeToFileTime(current_end_date, tz=CtrlCmdUtil.TZ),
                ]))
                if result is None:
                    print('Warning: 将来 EPG データの取得に失敗しました。')
                else:
                    service_event_info_list.extend(result)

            # EPG データを整形
            dataset_list: list[EPGDataset] = []
            for service_event_info in service_event_info_list:
                for event_info in service_event_info['event_list']:
                    assert 'start_time' in event_info
                    assert 'duration_sec' in event_info

                    # デジタルTVサービスのみを対象にする
                    ## ワンセグや独立データ放送は収集対象外
                    if service_event_info['service_info']['service_type'] != 0x01:
                        continue

                    # 指定したネットワーク ID のみを対象にする
                    if event_info['onid'] not in include_network_ids:
                        continue

                    # もし short_info がなければ使い物にならんのでスキップ
                    if 'short_info' not in event_info:
                        continue

                    # ID: 202301011230-NID32736-SID01024-EID00535 のフォーマット
                    # 最初に番組開始時刻を付けて完全な一意性を担保する
                    epg_id = f"{event_info['start_time'].strftime('%Y%m%d%H%M')}-NID{event_info['onid']:05d}-SID{event_info['sid']:05d}-EID{event_info['eid']:05d}"

                    # 万が一 ID が重複する番組があれば除外
                    ## EDCB の仕様に不備がなければ基本的にないはず
                    if epg_id in unique_set:
                        print(f'Skip: {epg_id}')
                        continue
                    unique_set.add(epg_id)

                    # 番組タイトルと番組概要を半角に変換
                    title = FormatString(event_info['short_info']['event_name'])
                    description = FormatString(event_info['short_info']['text_char'])

                    # ジャンルの ID を取得
                    ## 複数のジャンルが存在する場合、最初のジャンルのみを取得
                    major_genre_id = -1
                    middle_genre_id = -1
                    if 'content_info' in event_info and len(event_info['content_info']['nibble_list']) >= 1:
                        major_genre_id = event_info['content_info']['nibble_list'][0]['content_nibble'] >> 8
                        middle_genre_id = event_info['content_info']['nibble_list'][0]['content_nibble'] & 0xf

                    dataset_list.append(EPGDataset(
                        id = epg_id,
                        network_id = event_info['onid'],
                        service_id = event_info['sid'],
                        transport_stream_id = event_info['tsid'],
                        event_id = event_info['eid'],
                        title = title,
                        title_without_symbols = RemoveSymbols(title),
                        description = description,
                        description_without_symbols = RemoveSymbols(description),
                        start_time = event_info['start_time'],
                        duration = event_info['duration_sec'],
                        major_genre_id = major_genre_id,
                        middle_genre_id = middle_genre_id,
                        raw = event_info,
                    ))

            # ID 順にソート
            dataset_list.sort(key=lambda x: x.id)  # type: ignore

            # JSONL ファイルに保存
            for dataset in dataset_list:
                print(f'Add: {dataset.id}')
                writer.write(dataset.model_dump(mode='json'))

            # 次のループのために開始日時を更新
            current_start_date = current_end_date

    elapsed_time = time.time() - start_time
    print(f'処理時間: {elapsed_time:.2f} 秒')


if __name__ == '__main__':
    app()
