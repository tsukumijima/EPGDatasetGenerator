#!/usr/bin/env python

import jsonlines
import typer
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


app = typer.Typer()

@app.command()
def main(
    dataset_path: Annotated[Path, typer.Option(help='データ元の JSONL データセットのパス。', exists=True, file_okay=True, dir_okay=False)] = Path('epg_dataset.jsonl'),
    subset_size: Annotated[int, typer.Option(help='生成するデータセットのサブセットのサイズ')] = 3000,
):
    pass


if __name__ == '__main__':
    app()
