#!/usr/bin/env python

import asyncio
import jsonlines
import typer
from datetime import datetime, timedelta
from pydantic import BaseModel
from typing import Annotated

from utils.edcb import CtrlCmdUtil, EDCBUtil, EventInfo, ServiceEventInfo
from utils.epg import FormatString, RemoveSymbols


class EPGDataset(BaseModel):
    id: str
    network_id: int
    service_id: int
    transport_stream_id: int
    event_id: int
    start_time: datetime
    duration: int
    title: str
    title_without_symbols: str
    description: str
    description_without_symbols: str
    raw: EventInfo


app = typer.Typer()

@app.command()
def main(
    edcb_host: Annotated[str, typer.Option(help='ネットワーク接続する EDCB のホスト名。')] = '127.0.0.1',
    start_date: Annotated[datetime, typer.Option(help='過去 EPG データの取得開始日時 (UTC+9) 。')] = datetime.now() - timedelta(days=1),
    end_date: Annotated[datetime, typer.Option(help='過去 EPG データの取得終了日時 (UTC+9 )。')] = datetime.now(),
):
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

    # 古い日付から EPG データを随時 JSONL ファイルに保存
    with jsonlines.open('epg_dataset.jsonl', mode='w') as writer:

        # 1 週間ごとに EDCB から過去の EPG データを取得
        ## sendEnumPgArc は 1 回のリクエストで取得できるデータ量に制限があるため、1 週間ごとに取得する
        start = start_date
        while start < end_date:
            end = start + timedelta(weeks=1)
            if end > end_date:
                end = end_date

            print(f'取得期間: {start} ~ {end}')

            # EDCB から指定期間の EPG データを取得
            service_event_info_list: list[ServiceEventInfo] | None = asyncio.run(edcb.sendEnumPgArc([
                # 絞り込み対象のネットワーク ID・トランスポートストリーム ID・サービス ID に掛けるビットマスク (?????)
                ## よく分かってないけどとりあえずこれで全番組が対象になる
                0xffffffffffff,
                # 絞り込み対象のネットワーク ID・トランスポートストリーム ID・サービス ID
                ## (network_id << 32 | transport_stream_id << 16 | service_id) の形式で指定しなければならないらしい
                ## よく分かってないけどとりあえずこれで全番組が対象になる
                0xffffffffffff,
                # 絞り込み対象の番組開始時刻の最小値
                EDCBUtil.datetimeToFileTime(start, tz=CtrlCmdUtil.TZ),
                # 絞り込み対象の番組開始時刻の最大値 (自分自身を含まず、番組「開始」時刻が指定した時刻より前の番組が対象になる)
                # たとえば 11:00:00 ならば 10:59:59 までの番組が対象になるし、11:00:01 ならば 11:00:00 までの番組が対象になる
                EDCBUtil.datetimeToFileTime(end, tz=CtrlCmdUtil.TZ),
            ]))
            if service_event_info_list is None:
                print('過去 EPG データの取得に失敗しました。')
                return

            # EPG データを整形
            dataset_list: list[EPGDataset] = []
            for service_event_info in service_event_info_list:
                for event_info in service_event_info['event_list']:
                    assert 'start_time' in event_info
                    assert 'duration_sec' in event_info

                    # もし short_info がなければ使い物にならんのでスキップ
                    if 'short_info' not in event_info:
                        continue

                    # ID: 202301011230-NID32736-SID01024-EID00535 のフォーマット
                    # 最初に番組開始時刻を付けて完全な一意性を担保する
                    epg_id = f"{event_info['start_time'].strftime('%Y%m%d%H%M')}-NID{event_info['onid']:05d}-SID{event_info['sid']:05d}-EID{event_info['eid']:05d}"

                    # 番組タイトルと番組概要を半角に変換
                    title = FormatString(event_info['short_info']['event_name'])
                    description = FormatString(event_info['short_info']['text_char'])

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
                        raw = event_info,
                    ))

            # ID 順にソート
            dataset_list.sort(key=lambda x: x.id)  # type: ignore

            # JSONL ファイルに保存
            for dataset in dataset_list:
                print(f'Add: {dataset.id}')
                writer.write(dataset.model_dump(mode='json'))

            # 次のループのために開始日時を更新
            start = end + timedelta(seconds=1)


if __name__ == '__main__':
    app()
