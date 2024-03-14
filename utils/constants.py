
from datetime import datetime
from pydantic import BaseModel

from utils.edcb import EventInfo


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
    major_genre_id: int
    middle_genre_id: int
    raw: EventInfo


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
    # ここから下は後で自動 or 人力で追加するフィールド
    series_title: str = ''
    episode_number: str | None = None
    subtitle: str | None = None

class EPGDatasetSubsetInternal(EPGDatasetSubset):
    weight: float = 1.0  # 内部でのみ使用
