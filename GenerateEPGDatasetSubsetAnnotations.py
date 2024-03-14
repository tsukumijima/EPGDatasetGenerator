#!/usr/bin/env python

import google.generativeai as genai
import json
import os
import jsonlines
import time
import typer
from dotenv import load_dotenv
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Annotated

from GenerateEPGDatasetSubset import EPGDatasetSubset


class LLMRequest(BaseModel):
    title: str = Field(..., description='当該番組のタイトル。')
    description: str = Field(..., description='当該番組の概要。')

class LLMResponse(BaseModel):
    series_title: str = Field(..., description='当該番組のシリーズタイトル。')
    episode_number: str | None = Field(None, description='当該番組の話数 (番組情報に話数情報が存在しない場合は null)。')
    subtitle: str | None = Field(None, description='当該番組のサブタイトル (番組情報にサブタイトル情報が存在しない場合は null)。')

def generate_annotations(subset: EPGDatasetSubset) -> EPGDatasetSubset:
    """ Gemini 1.0 Pro によるアノテーション自動生成 """

    # プロンプトに埋め込む用の JSON スキーマを生成
    # ref: https://zenn.dev/tellernovel_inc/articles/7c99563fad1319
    json_schema = json.dumps(LLMResponse.model_json_schema(), ensure_ascii=False, separators=(",", ":"))

    # API キーの設定
    load_dotenv()
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    genai.configure(api_key=GEMINI_API_KEY)

    gemini_pro = genai.GenerativeModel(
        model_name = 'models/gemini-1.0-pro-latest',
        generation_config = genai.types.GenerationConfig(
            temperature = 0.0,  # 決定論的な出力を得るために 0.0 に設定
        ),
    )
    chat = gemini_pro.start_chat(history=[
        {
            'role': 'user',
            'parts': [{
                'text': LLMRequest(
                    title = 'かぐや様は告らせたい-ウルトラロマンティック- #6',
                    description = '#6「生徒会は進みたい」「白銀御行は告らせたい②」「白銀御行は告らせたい③」',
                ).model_dump_json(),
            }],
        },
        {
            'role': 'model',
            'parts': [{
                'text': LLMResponse(
                    series_title = 'かぐや様は告らせたい-ウルトラロマンティック-',
                    episode_number = '#6',
                    subtitle = '「生徒会は進みたい」「白銀御行は告らせたい②」「白銀御行は告らせたい③」',
                ).model_dump_json(),
            }],
        },
    ])
    response = chat.send_message(LLMRequest(
        title = subset.title,
        description = subset.description,
    ).model_dump_json())
    print(response)

    return subset


app = typer.Typer()

@app.command()
def main(
    subset_path: Annotated[Path, typer.Option(help='アノテーションを自動生成・追加するデータセットのサブセットのパス。', dir_okay=False)] = Path('epg_dataset_subset.jsonl'),
):
    if not subset_path.exists():
        print(f'ファイル {subset_path} は存在しません。')
        return

    generate_annotations(EPGDatasetSubset.model_validate_json('{"id": "202110230153-NID32742-SID01072-EID27730", "network_id": 32742, "service_id": 1072, "transport_stream_id": 32742, "event_id": 27730, "start_time": "2021-10-23T01:53:00+09:00", "duration": 1800, "title": "大正オトメ御伽話「黒百合ノ娘」", "title_without_symbols": "大正オトメ御伽話「黒百合ノ娘」", "description": "珠彦の屋敷に妹の珠子がやってきた。その振る舞いに困惑する珠彦だが、夕月はどうにか打ち解けようとする。", "description_without_symbols": "珠彦の屋敷に妹の珠子がやってきた。その振る舞いに困惑する珠彦だが、夕月はどうにか打ち解けようとする。", "major_genre_id": 7, "middle_genre_id": 0, "series_title": "", "episode_number": null, "subtitle": null}'))
    return

    start_time = time.time()

    print('-' * 80)
    modified_subsets: list[EPGDatasetSubset] = []
    with jsonlines.open(subset_path, 'r') as reader:
        for obj in reader:
            subset = EPGDatasetSubset.model_validate(obj)
            print(f'{subset.id} のアノテーションを自動生成しています...')
            print(f'番組名:   {subset.title}')
            print(f'番組概要: {subset.description}')
            modified_subset = generate_annotations(subset)
            print(f'{subset.id} のアノテーションを自動生成しました。')
            print(f'シリーズタイトル: {modified_subset.series_title}')
            print(f'話数: {modified_subset.episode_number} / サブタイトル: {modified_subset.subtitle}')
            modified_subsets.append(modified_subset)
            print('-' * 80)

    print('-' * 80)
    print(f'{subset_path} に書き込んでいます...')
    with jsonlines.open(subset_path, 'w') as writer:
        for subset in modified_subsets:
            writer.write(subset.model_dump(mode='json'))

    elapsed_time = time.time() - start_time
    print(f'処理時間: {elapsed_time:.2f} 秒')
    print('-' * 80)

if __name__ == '__main__':
    app()
