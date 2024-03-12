
import typer
from datetime import datetime, timedelta
from pydantic import BaseModel
from typing import Annotated

from utils.edcb import CtrlCmdUtil, EDCBUtil, EventInfo
from utils.epg import FormatString


class EPGDataset(BaseModel):
    id: str
    network_id: int
    service_id: int
    transport_stream_id: int
    event_id: int
    title: str
    description: str
    start_time: datetime
    duration: int
    raw: EventInfo


app = typer.Typer()

@app.command()
def main(
    edcb_host: Annotated[str, typer.Option(help='ネットワーク接続する EDCB のホスト名。')] = '127.0.0.1',
    start_date: Annotated[datetime, typer.Option(help='過去 EPG データの取得開始日時。')] = datetime.now() - timedelta(days=1),
    end_date: Annotated[datetime, typer.Option(help='過去 EPG データの取得終了日時。')] = datetime.now(),
):

    # CtrlCmdUtil インスタンスを生成
    edcb = CtrlCmdUtil()
    edcb.setNWSetting(edcb_host, 4510)
    edcb.setConnectTimeOutSec(60)  # かなり時間かかることも見据えて長めに設定




if __name__ == '__main__':
    app()
