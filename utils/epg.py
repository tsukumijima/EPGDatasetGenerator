
import re
from typing import cast


# 変換マップ
__format_string_translation_map: dict[int, str] | None = None
__format_string_regex: re.Pattern[str] | None = None
__enclosed_characters_translation_map: dict[int, str] | None = None


def FormatString(string: str) -> str:
    """
    文字列に含まれる英数や記号を半角に置換し、一律な表現に整える
    https://github.com/tsukumijima/KonomiTV/blob/master/server/app/utils/TSInformation.py から移植

    Args:
        string (str): 文字列

    Returns:
        str: 置換した文字列
    """

    global __format_string_translation_map, __format_string_regex

    # 全角英数を半角英数に置換
    # ref: https://github.com/ikegami-yukino/jaconv/blob/master/jaconv/conv_table.py
    zenkaku_table = '０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ'
    hankaku_table = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
    merged_table = dict(zip(list(zenkaku_table), list(hankaku_table)))

    # 全角記号を半角記号に置換
    symbol_zenkaku_table = '＂＃＄％＆＇（）＋，－．／：；＜＝＞［＼］＾＿｀｛｜｝　'
    symbol_hankaku_table = '"#$%&\'()+,-./:;<=>[\\]^_`{|} '
    merged_table.update(zip(list(symbol_zenkaku_table), list(symbol_hankaku_table)))
    merged_table.update({
        # 一部の半角記号を全角に置換
        # 主に見栄え的な問題（全角の方が字面が良い）
        '!': '！',
        '?': '？',
        '*': '＊',
        '~': '～',
        # シャープ → ハッシュ
        '♯': '#',
        # 波ダッシュ → 全角チルダ
        ## EDCB は ～ を全角チルダとして扱っているため、KonomiTV でもそのように統一する
        ## TODO: 番組検索を実装する際は検索文字列の波ダッシュを全角チルダに置換する下処理が必要
        ## ref: https://qiita.com/kasei-san/items/3ce2249f0a1c1af1cbd2
        '〜': '～',
    })

    # 置換を実行
    if __format_string_translation_map is None:
        __format_string_translation_map = str.maketrans(merged_table)
    result = string.translate(__format_string_translation_map)

    # 逆に代替の文字表現に置換された ARIB 外字を Unicode に置換するテーブル
    ## 主に EDCB (EpgDataCap3_Unicode.dll 不使用) 環境向けの処理
    ## EDCB は通常 Shift-JIS で表現できない文字をサロゲートペア範囲外の文字も含めてすべて代替の文字表現に変換するが、今回の用途では都合が悪い
    ## そこで、逆変換可能 (明確に区別可能な) な文字列表現をすべて対応する Unicode 文字に置換する
    ## 英数字を半角に変換した後に適応するのでキー英数字は半角になっている
    ## KonomiTV では見栄えの関係で変換していない文字もすべて置換する
    ## ちなみに EpgDataCap3_Unicode.dll 不使用状態で保存された過去 EPG データはどうも文字列をデコードされた状態で保存されているようで、
    ## 残念ながら後から EpgDataCap3_Unicode.dll に差し替えても Unicode では返ってこない…
    ## ref: https://github.com/xtne6f/EDCB/blob/work-plus-s-230526/EpgDataCap3/EpgDataCap3/ARIB8CharDecode.cpp#L1324-L1614
    __format_string_regex_table = {
        '[HV]': '\U0001f14a',
        '[SD]': '\U0001f14c',
        '[P]': '\U0001f13f',
        '[W]': '\U0001f146',
        '[MV]': '\U0001f14b',
        '[手]': '\U0001f210',
        '[字]': '\U0001f211',
        '[双]': '\U0001f212',
        '[デ]': '\U0001f213',
        '[S]': '\U0001f142',
        '[二]': '\U0001f214',
        '[多]': '\U0001f215',
        '[解]': '\U0001f216',
        '[SS]': '\U0001f14d',
        '[B]': '\U0001f131',
        '[N]': '\U0001f13d',
        '[天]': '\U0001f217',
        '[交]': '\U0001f218',
        '[映]': '\U0001f219',
        '[無]': '\U0001f21a',
        '[料]': '\U0001f21b',
        '[・]': '⚿',
        '[前]': '\U0001f21c',
        '[後]': '\U0001f21d',
        '[再]': '\U0001f21e',
        '[新]': '\U0001f21f',
        '[初]': '\U0001f220',
        '[終]': '\U0001f221',
        '[生]': '\U0001f222',
        '[販]': '\U0001f223',
        '[声]': '\U0001f224',
        '[吹]': '\U0001f225',
        '[PPV]': '\U0001f14e',
        '(秘)': '㊙',
        '[ほか]': '\U0001f200',
        'm^2': 'm²',
        'm^3': 'm³',
        'cm^2': 'cm²',
        'cm^3': 'cm³',
        'km^2': 'km²',
        '[社]': '㈳',
        '[財]': '㈶',
        '[有]': '㈲',
        '[株]': '㈱',
        '[代]': '㈹',
        '(問)': '㉄',
        '^2': '²',
        '^3': '³',
        '(箏)': '㉇',
        '(〒)': '〶',
        '()()': '⚾',
    }

    # 正規表現で置換
    if __format_string_regex is None:
        __format_string_regex = re.compile("|".join(map(re.escape, __format_string_regex_table.keys())))
    result = __format_string_regex.sub(lambda match: cast(dict[str, str], __format_string_regex_table)[match.group(0)], result)  # type: ignore

    # CRLF を LF に置換
    result = result.replace('\r\n', '\n')

    # 置換した文字列を返す
    return result


def RemoveSymbols(string: str) -> str:
    """
    文字列から囲み文字・記号・番組枠名などのノイズを除去する

    Args:
        string (str): 文字列

    Returns:
        str: 記号を除去した文字列
    """

    global __enclosed_characters_translation_map

    # 番組表で使用される囲み文字の置換テーブル
    ## ref: https://note.nkmk.me/python-chr-ord-unicode-code-point/
    ## ref: https://github.com/l3tnun/EPGStation/blob/v2.6.17/src/util/StrUtil.ts#L7-L46
    ## ref: https://github.com/xtne6f/EDCB/blob/work-plus-s-230526/EpgDataCap3/EpgDataCap3/ARIB8CharDecode.cpp#L1324-L1614
    enclosed_characters_table = {
        '\U0001f14a': '[HV]',
        '\U0001f14c': '[SD]',
        '\U0001f13f': '[P]',
        '\U0001f146': '[W]',
        '\U0001f14b': '[MV]',
        '\U0001f210': '[手]',
        '\U0001f211': '[字]',
        '\U0001f212': '[双]',
        '\U0001f213': '[デ]',
        '\U0001f142': '[S]',
        '\U0001f214': '[二]',
        '\U0001f215': '[多]',
        '\U0001f216': '[解]',
        '\U0001f14d': '[SS]',
        '\U0001f131': '[B]',
        '\U0001f13d': '[N]',
        '\U0001f217': '[天]',
        '\U0001f218': '[交]',
        '\U0001f219': '[映]',
        '\U0001f21a': '[無]',
        '\U0001f21b': '[料]',
        '\U0001f21c': '[前]',
        '\U0001f21d': '[後]',
        '⚿': '[・]',
        '\U0001f21e': '[再]',
        '\U0001f21f': '[新]',
        '\U0001f220': '[初]',
        '\U0001f221': '[終]',
        '\U0001f222': '[生]',
        '\U0001f223': '[販]',
        '\U0001f224': '[声]',
        '\U0001f225': '[吹]',
        '\U0001f14e': '[PPV]',
    }

    # Unicode の囲み文字を大かっこで囲った文字に置換する
    # この後の処理で大かっこで囲まれた文字を削除するためのもの
    if __enclosed_characters_translation_map is None:
        __enclosed_characters_translation_map = str.maketrans(enclosed_characters_table)
    result = string.translate(__enclosed_characters_translation_map)

    # [字] [再] などの囲み文字を半角スペースに正規表現で置換する
    # 本来 ARIB 外字である記号の一覧
    # ref: https://ja.wikipedia.org/wiki/%E7%95%AA%E7%B5%84%E8%A1%A8
    # ref: https://github.com/xtne6f/EDCB/blob/work-plus-s/EpgDataCap3/EpgDataCap3/ARIB8CharDecode.cpp#L1319
    mark = ('新|終|再|交|映|手|声|多|副|字|文|CC|OP|二|S|B|SS|無|無料|'
        'C|S1|S2|S3|MV|双|デ|D|N|W|P|H|HV|SD|天|解|料|前|後初|生|販|吹|PPV|'
        '演|移|他|収|・|英|韓|中|字/日|字/日英|3D|2K|4K|8K|5.1|7.1|22.2|60P|120P|d|HC|HDR|SHV|UHD|VOD|配|初')
    pattern1 = re.compile(r'\((二|字|字幕|再|再放送|吹|吹替|無料|無料放送)\)', re.IGNORECASE)  # 通常の括弧で囲まれている記号
    pattern2 = re.compile(r'\[(' + mark + r')\]', re.IGNORECASE)
    pattern3 = re.compile(r'【(' + mark + r')】', re.IGNORECASE)
    result = pattern1.sub(' ', result)
    result = pattern2.sub(' ', result)
    result = pattern3.sub(' ', result)

    # 前後の半角スペースを削除する
    result = result.strip()

    # 番組枠名などのノイズを削除する
    ## 正規表現でゴリ押し執念の削除を実行………
    ## かなり悩ましかったが、「(字幕版)」はあくまでそういう版であることを示す情報なので削除しないことにした (「【日本語字幕版】」も同様)
    result = re.sub(r'※2K放送', '', result)
    result = re.sub(r'※字幕スーパー', '', result)
    result = re.sub(r'<(HD|SD)>', '', result)
    result = re.sub(r'<字幕>', '', result)
    result = re.sub(r'<字幕スーパー>', '', result)
    result = re.sub(r'<字幕・レターボックスサイズ>', '', result)
    result = re.sub(r'<字幕スーパー・レターボックスサイズ>', '', result)
    result = re.sub(r'<レターボックスサイズ>', '', result)
    result = re.sub(r'<ノーカット字幕>', '', result)
    result = re.sub(r'<(初放送|TV初放送|地上波初放送)>', '', result)
    result = re.sub(r'〔字幕〕', '', result)
    result = re.sub(r'〔字幕スーパー〕', '', result)
    result = re.sub(r'【字幕】', '', result)
    result = re.sub(r'【字幕スーパー】', '', result)
    result = re.sub(r'【無料】', '', result)
    result = re.sub(r'【KNTV】', '', result)
    result = re.sub(r'【中】', '', result)
    result = re.sub(r'【韓】', '', result)
    result = re.sub(r'【リクエスト】', '', result)
    result = re.sub(r'【解説放送】', '', result)
    result = re.sub(r'<独占>', '', result)
    result = re.sub(r'【独占】', '', result)
    result = re.sub(r'<独占放送>', '', result)
    result = re.sub(r'【独占放送】', '', result)
    result = re.sub(r'【最新作】', '', result)
    result = re.sub(r'【歌詞入り】', '', result)
    result = re.sub(r'【.{0,8}ドラマ】', '', result)
    result = re.sub(r'【ドラマ.{0,8}】', '', result)
    result = re.sub(r'【.{0,8}夜ドラ.{0,8}】', '', result)
    result = re.sub(r'【.{0,8}昼ドラ.{0,8}】', '', result)
    result = re.sub(r'【.{0,8}時代劇.{0,8}】', '', result)
    result = re.sub(r'【.{0,8}一挙.{0,8}】', '', result)
    result = re.sub(r'【.*?日本初.*?】', '', result)
    result = re.sub(r'【.*?初放送.*?】', '', result)
    result = re.sub(r'<.*?一挙.*?>', '', result)
    result = re.sub(r'^TV初(★|☆|◆|◇)', '', result)
    result = re.sub(r'^\[(録|映画|バラエティ|旅バラエティ|釣り|プロレス|ゴルフ|プロ野球|高校野球|ゴルフ|テニス|モーター|モータースポーツ|卓球|ラグビー|ボウリング|バレーボール|アメリカンフットボール)\]', '', result)
    result = re.sub(r'^特: ', '', result)
    result = re.sub(r'^アニメ ', '', result)
    result = re.sub(r'^アニメ・', '', result)
    result = re.sub(r'^アニメ「(?P<title>.*?)」', r'\g<title> ', result)
    result = re.sub(r'^アニメ『(?P<title>.*?)』', r'\g<title> ', result)
    result = re.sub(r'^アニメ\d{1,2}・', '', result)
    result = re.sub(r'^アニメ\d{1,2}', '', result)
    result = re.sub(r'^テレビアニメ ', '', result)
    result = re.sub(r'^テレビアニメ・', '', result)
    result = re.sub(r'^テレビアニメ「(?P<title>.*?)」', r'\g<title> ', result)
    result = re.sub(r'^テレビアニメ『(?P<title>.*?)』', r'\g<title> ', result)
    result = re.sub(r'^TVアニメ ', '', result)
    result = re.sub(r'^TVアニメ・', '', result)
    result = re.sub(r'^TVアニメ「(?P<title>.*?)」', r'\g<title> ', result)
    result = re.sub(r'^TVアニメ『(?P<title>.*?)』', r'\g<title> ', result)
    result = re.sub(r'^ドラマ ', '', result)
    result = re.sub(r'^ドラマ・', '', result)
    result = re.sub(r'^ドラマ「(?P<title>.*?)」', r'\g<title> ', result)
    result = re.sub(r'^ドラマ『(?P<title>.*?)』', r'\g<title> ', result)
    result = re.sub(r'^ドラマシリーズ ', '', result)
    result = re.sub(r'^ドラマシリーズ・', '', result)
    result = re.sub(r'^ドラマシリーズ「(?P<title>.*?)」', r'\g<title> ', result)
    result = re.sub(r'^ドラマシリーズ『(?P<title>.*?)』', r'\g<title> ', result)
    result = re.sub(r'^大河ドラマ「(?P<title>.*?)」', r'\g<title> ', result)
    result = re.sub(r'^大河ドラマ『(?P<title>.*?)』', r'\g<title> ', result)
    result = re.sub(r'^【連続テレビ小説】', '連続テレビ小説 ', result)
    result = re.sub(r'【(朝|昼|夕|夕方|夜)アンコール】', '', result)
    result = re.sub(r'【(あさ|ひる|よる)ドラ】', '', result)
    result = re.sub(r'【(あさ|ひる|よる)ドラアンコール】', '', result)
    result = re.sub(r'^ドラマ\d{1,2}・', '', result)
    result = re.sub(r'^ドラマ\d{1,2}', '', result)
    result = re.sub(r'^ドラマ(\+|パラビ|Paravi|NEXT|プレミア\d{1,2}|チューズ！|ホリック！|ストリーム) ', '', result)
    result = re.sub(r'^ドラマ(\+|パラビ|Paravi|NEXT|プレミア\d{1,2}|チューズ！|ホリック！|ストリーム)・', '', result)
    result = re.sub(r'^ドラマ(\+|パラビ|Paravi|NEXT|プレミア\d{1,2}|チューズ！|ホリック！|ストリーム)「(?P<title>.*?)」', r'\g<title> ', result)
    result = re.sub(r'^ドラマ(\+|パラビ|Paravi|NEXT|プレミア\d{1,2}|チューズ！|ホリック！|ストリーム)『(?P<title>.*?)』', r'\g<title> ', result)
    result = re.sub(r'^ドラマ(\+|パラビ|Paravi|NEXT|プレミア\d{1,2}|チューズ！|ホリック！|ストリーム)', '', result)
    result = re.sub(r'<BSフジ.*?>', '', result)
    result = re.sub(r'<フジバラナイト (SAT|SUN|MON|TUE|WED|THU|FRI)>', '', result)
    result = re.sub(r'<(月|火|水|木|金|土|日)(曜PLUS|曜ACTION|曜NEXT|曜RISE)！>', '', result)
    result = re.sub(r'<(名作ドラマ劇場|午後の名作ドラマ劇場|ブレイクマンデー\d{1,2}|フジテレビからの！|サンデーMIDNIGHT)>', '', result)
    result = re.sub(r'<(月|火|水|木|金|土|日)(ドラ|ドラ★イレブン|曜劇場|曜ドラマ|曜ナイトドラマ)>', '', result)
    result = re.sub(r'^オトナの(月|火|水|木|金|土|日)ドラ', '', result)
    result = re.sub(r'^(月|火|水|木|金|土|日)(ドラ|曜劇場|曜ドラマ|曜ドラマDEEP|曜ナイトドラマ) ', '', result)
    result = re.sub(r'^(月|火|水|木|金|土|日)(ドラ|曜劇場|曜ドラマ|曜ドラマDEEP|曜ナイトドラマ)・', '', result)
    result = re.sub(r'^(月|火|水|木|金|土|日)(ドラ|曜劇場|曜ドラマ|曜ドラマDEEP|曜ナイトドラマ)「(?P<title>.*?)」', r'\g<title> ', result)
    result = re.sub(r'^(月|火|水|木|金|土|日)(ドラ|曜劇場|曜ドラマ|曜ドラマDEEP|曜ナイトドラマ)『(?P<title>.*?)』', r'\g<title> ', result)
    result = re.sub(r'^(月|火|水|木|金|土|日)(ドラ|曜劇場|曜ドラマ|曜ドラマDEEP|曜ナイトドラマ)\d{1,2}・', '', result)
    result = re.sub(r'^(月|火|水|木|金|土|日)(ドラ|曜劇場|曜ドラマ|曜ドラマDEEP|曜ナイトドラマ)\d{1,2}', '', result)
    result = re.sub(r'^(月|火|水|木|金|土|日)(ドラ|曜劇場|曜ドラマ|曜ドラマDEEP|曜ナイトドラマ)', '', result)
    result = re.sub(r'^(真夜中ドラマ|シンドラ|ドラマL|Zドラマ|よるおびドラマ) ', '', result)
    result = re.sub(r'^(真夜中ドラマ|シンドラ|ドラマL|Zドラマ|よるおびドラマ)・', '', result)
    result = re.sub(r'^(真夜中ドラマ|シンドラ|ドラマL|Zドラマ|よるおびドラマ)「(?P<title>.*?)」', r'\g<title> ', result)
    result = re.sub(r'^(真夜中ドラマ|シンドラ|ドラマL|Zドラマ|よるおびドラマ)『(?P<title>.*?)』', r'\g<title> ', result)
    result = re.sub(r'^(真夜中ドラマ|シンドラ|ドラマL|Zドラマ|よるおびドラマ)', '', result)
    result = re.sub(r'^連続ドラマW', '', result)
    result = re.sub(r'(★|☆|◆|◇)ドラマイズム】', '】', result)
    result = re.sub(r'<韓ドラ>', '', result)
    result = re.sub(r'【韓ドラ】', '', result)
    result = re.sub(r'^韓ドラ ', '', result)
    result = re.sub(r'^韓ドラ・', '', result)
    result = re.sub(r'^韓ドラ「(?P<title>.*?)」', r'\g<title> ', result)
    result = re.sub(r'^韓ドラ『(?P<title>.*?)』', r'\g<title> ', result)
    result = re.sub(r'^(台湾|タイ)ドラマ ', '', result)
    result = re.sub(r'^(台湾|タイ)ドラマ・', '', result)
    result = re.sub(r'^(台湾|タイ)ドラマ「(?P<title>.*?)」', r'\g<title> ', result)
    result = re.sub(r'^(台湾|タイ)ドラマ『(?P<title>.*?)』', r'\g<title> ', result)
    result = re.sub(r'^韓(★|☆|◆|◇)', '', result)
    result = re.sub(r'^韓ドラ(★|☆|◆|◇)', '', result)
    result = re.sub(r'^華(★|☆|◆|◇)', '', result)
    result = re.sub(r'^華ドラ(★|☆|◆|◇)', '', result)
    result = re.sub(r'^(中国|中華|韓国|韓ドラ)時代劇(★|☆|◆|◇)', '', result)
    result = re.sub(r'^(韓流プレミア|韓流朝ドラ\d{1,2}) ', '', result)
    result = re.sub(r'^韓流プレミア・', '', result)
    result = re.sub(r'^韓流プレミア「(?P<title>.*?)」', r'\g<title> ', result)
    result = re.sub(r'^韓流プレミア『(?P<title>.*?)』', r'\g<title> ', result)
    result = re.sub(r'^(中|韓)(国|国BL|国歴史|流|流BL)ドラマ ', '', result)
    result = re.sub(r'^(中|韓)(国|国BL|国歴史|流|流BL)ドラマ・', '', result)
    result = re.sub(r'^(中|韓)(国|国BL|国歴史|流|流BL)ドラマ「(?P<title>.*?)」', r'\g<title> ', result)
    result = re.sub(r'^(中|韓)(国|国BL|国歴史|流|流BL)ドラマ『(?P<title>.*?)』', r'\g<title> ', result)
    result = re.sub(r'^(中|韓)(国|国BL|国歴史|流|流BL)ドラマ【(?P<title>.*?)】', r'\g<title> ', result)
    result = re.sub(r'<時代劇.*?>', '', result)
    result = re.sub(r'\([0-9][0-9][0-9]ch(時代劇|中国ドラマ|韓国ドラマ)\)', '', result)
    result = re.sub(r'【時代劇】', '', result)
    result = re.sub(r'^時代劇 ', '', result)
    result = re.sub(r'^時代劇・', '', result)
    result = re.sub(r'^時代劇「(?P<title>.*?)」', r'\g<title> ', result)
    result = re.sub(r'^時代劇『(?P<title>.*?)』', r'\g<title> ', result)
    result = re.sub(r'^(中|韓)(国|流|国ファンタジー)時代劇 ', '', result)
    result = re.sub(r'^(中|韓)(国|流|国ファンタジー)時代劇・', '', result)
    result = re.sub(r'^(中|韓)(国|流|国ファンタジー)時代劇「(?P<title>.*?)」', r'\g<title> ', result)
    result = re.sub(r'^(中|韓)(国|流|国ファンタジー)時代劇『(?P<title>.*?)』', r'\g<title> ', result)
    result = re.sub(r'^(月|火|水|木|金|土|日)[0-9]「(?P<title>.*?)」', r'\g<title> ', result)
    result = re.sub(r'^(月|火|水|木|金|土|日)[0-9]『(?P<title>.*?)』', r'\g<title> ', result)
    result = re.sub(r'^アニメA ', '', result)
    result = re.sub(r'^アニメA・', '', result)
    result = re.sub(r'<アニメギルド>', '', result)
    result = re.sub(r'<(M|T|W)ナイト>', '', result)
    result = re.sub(r'<ノイタミナ>', '', result)
    result = re.sub(r'<\+Ultra>', '', result)
    result = re.sub(r'<B8station>', '', result)
    result = re.sub(r'AnichU', '', result)
    result = re.sub(r'FRIDAY ANIME NIGHT', '', result)
    result = re.sub(r'^(月|火|水|木|金|土|日)曜アニメ・水もん ', '', result)
    result = re.sub(r'【(アニメ|アニメシャワー|アニメ特区|アニメイズム|スーパーアニメイズム|ヌマニメーション|ANiMAZiNG！！！|ANiMAZiNG2！！！)】', '', result)
    result = re.sub(r'アニメイズム$', '', result)
    result = re.sub(r'^・', '', result)

    # 前後の半角スペースを削除する
    result = result.strip()

    # 連続する半角スペースを 1 つにする
    result = re.sub(r'[ \t]+', ' ', result)

    # 置換した文字列を返す
    return result
