#!/usr/bin/env python3
"""Build the kanji data files used by the flashcard app.

The app itself is plain HTML/CSS/JS with no dependencies. This script is only a
build tool: it downloads the upstream data sources once (into ``.cache/``) and
emits the plain JavaScript data files under ``js/data/``.

Data sources
------------
* KANJIDIC2 (EDRDG) - readings, English meanings and stroke counts.
  CC BY-SA 4.0, https://www.edrdg.org/wiki/KANJIDIC_Project.html
* Jonathan Waller's JLPT kanji levels, as packaged by OpenJLPT - N5..N1
  membership and kanji frequency. CC BY-SA 4.0, https://github.com/evanclan/OpenJLPT
* Wikipedia "List of jōyō kanji" - the 2136 Jōyō characters in the order of the
  official 常用漢字表 (sorted by on'yomi), plus the elementary school grade of
  each character. CC BY-SA 4.0.
* Kanji Kentei (漢検) grade lists, published by hoffmannjp/kanken-json (MIT) -
  used to split the 1110 secondary school Jōyō kanji across school years 7-12,
  since the Ministry of Education publishes no per-year table for secondary
  school.
* Tatoeba example sentences with furigana, CC BY 2.0 FR,
  https://tatoeba.org - short Japanese sentences, preferring the Tanaka Corpus
  (textbook sentences) that Tatoeba also publishes as jpn_indices.
* JMdict / EDICT (EDRDG), CC BY-SA 4.0, https://www.edrdg.org/wiki/JMdict_Project.html
  - used as a fallback for the few kanji that appear in no Tatoeba sentence.
* janome (LGPL) for word segmentation, so the example sentences can be spaced
  out for learners. Optional: without it the examples are still generated, just
  without the word spacing.

Run with:  python3 build-data.py
"""

from __future__ import annotations

import bz2
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / ".cache"
OUT_DATA = ROOT / "js" / "data"

KANJIDIC2_URL = "https://raw.githubusercontent.com/WordBrewery/kanjidic2-json/master/kanjidic2.json"
KANKEN_URL = "https://raw.githubusercontent.com/hoffmannjp/kanken-json/main/kanken.json"
WIKIPEDIA_URL = "https://en.wikipedia.org/w/index.php?title={title}&action=raw"
OPENJLPT_URL = "https://raw.githubusercontent.com/evanclan/OpenJLPT/main/data/json/kanji/{level}.json"
TATOEBA_URL = "https://downloads.tatoeba.org/exports/per_language/jpn/{name}.tsv.bz2"
JMDICT_URL = "https://github.com/scriptin/jmdict-simplified/releases/download/3.6.2%2B20260921173324/jmdict-eng-3.6.2%2B20260921173324.json.tgz"
CC_BY_SA_URL = "https://creativecommons.org/licenses/by-sa/4.0/legalcode.txt"
CC_BY_FR_URL = "https://creativecommons.org/licenses/by/2.0/fr/legalcode"

JOYO_TITLE = "List of_jōyō_kanji"
JOYO_TOTAL = 2136

# School year -> Kanji Kentei level, plus the half of that level to use
# (0 = the whole level). Years 1-6 are the official 学年別漢字配当表 characters and
# are cross-checked against the elementary grades in the Jōyō table. Years 7-8
# are the two junior high Kanken levels; the senior high Kanken levels are long,
# so "pre-2" covers years 9-10 and "2" covers years 11-12, each split in half.
SCHOOL_YEARS = [
    (1, "10", 0),
    (2, "9", 0),
    (3, "8", 0),
    (4, "7", 0),
    (5, "6", 0),
    (6, "5", 0),
    (7, "4", 0),
    (8, "3", 0),
    (9, "pre-2", 1),
    (10, "pre-2", 2),
    (11, "2", 1),
    (12, "2", 2),
]

JLPT_LEVELS = ["n5", "n4", "n3", "n2", "n1"]

# The Kanken lists repeat a few kanji in their kyūjitai spelling next to the
# shinjitai one (剝/剥, 塡/填, 頰/頬). Normalise to the shinjitai form.
FORM_EQUIVALENTS = {"\U00020b9f": "叱", "剝": "剥", "塡": "填", "頰": "頬"}
KYUJITAI_FORMS = ["剝", "塡", "頰"]

# KANJIDIC glosses that only describe a dictionary radical index and are noise
# for a learner.
MEANING_NOISE = re.compile(r"radical \(no\.\s*\d+\)")

# ---------------------------------------------------------------- kana tables
#
# The kana follow the official gojūon (五十音) table. Each row below gives the
# hiragana, the katakana, the Hepburn reading of the five vowels
# (a, i, u, e, o - the y row only has a, u and o) and a short note about the
# sound the row represents.
GOJUON = [
    ("", "あいうえお", "アイウエオ", "a i u e o", "vowel"),
    ("k", "かきくけこ", "カキクケコ", "ka ki ku ke ko", "voiceless velar stop (k)"),
    ("g", "がぎぐげご", "ガギグゲゴ", "ga gi gu ge go", "voiced velar stop (g), the dakuten of the k row"),
    ("s", "さしすせそ", "サシスセソ", "sa shi su se so", "voiceless alveolar fricative (s, sh)"),
    ("z", "ざじずぜぞ", "ザジズゼゾ", "za ji zu ze zo", "voiced alveolar fricative (z, j), the dakuten of the s row"),
    ("t", "たちつてと", "タチツテト", "ta chi tsu te to", "voiceless alveolar stop (t, ch, ts)"),
    ("d", "だぢづでど", "ダヂヅデド", "da ji zu de do", "voiced alveolar stop (d, j, zu), the dakuten of the t row"),
    ("n", "なにぬねの", "ナニヌネノ", "na ni nu ne no", "nasal (n)"),
    ("h", "はひふへほ", "ハヒフヘホ", "ha hi fu he ho", "voiceless glottal fricative (h, f)"),
    ("b", "ばびぶべぼ", "バビブベボ", "ba bi bu be bo", "voiced glottal fricative (b), the dakuten of the h row"),
    ("p", "ぱぴぷぺぽ", "パピプペポ", "pa pi pu pe po", "semi-voiced glottal fricative (p), the handakuten of the h row"),
    ("m", "まみむめも", "マミムメモ", "ma mi mu me mo", "nasal (m)"),
    ("y", "やゆよ", "ヤユヨ", "ya yu yo", "palatal glide (y)"),
    ("r", "らりるれろ", "ラリルレロ", "ra ri ru re ro", "liquid (r)"),
    ("w", "わを", "ワヲ", "wa wo", "glide (w); wo is rare and only survives in ヲン (won), literary Japanese and proper names"),
    ("", "ん", "ン", "n", "syllabic n: m, n or ng depending on the following sound"),
]

# Rows that are not part of the 46 basic kana.
VOICED_ROWS = ["g", "z", "d", "b", "p"]

# Small kana, identical in both syllabaries.
SMALL_KANA = [("ぁ", "ァ", "a"), ("ぃ", "ィ", "i"), ("ぅ", "ゥ", "u"), ("ぇ", "ェ", "e"), ("ぉ", "ォ", "o"),
              ("ゃ", "ャ", "ya"), ("ゅ", "ュ", "yu"), ("ょ", "ョ", "yo"), ("ゎ", "ヮ", "wa")]

SMALL_NOTE = "small kana: it is only used inside a digraph, such as きゃ (kya)"
SOKUON = ("っ", "ッ", "tsu", "sokuon: it doubles the consonant that follows, such as きって (kitte)")
CHOONPU = ("ー", None, "-", "chōonpu: the long vowel mark, it lengthens the vowel before it (e.g. ケーキ)")

# Kana that dropped out of everyday Japanese.
ARCHAIC_HIRAGANA = [("ゐ", "i", "archaic: only used in proper names"), ("ゑ", "e", "archaic: only used in proper names")]
ARCHAIC_KATAKANA = [
    ("ヰ", "i", "archaic: only used in proper names"),
    ("ヱ", "e", "archaic: only used in proper names"),
]

# Katakana yōon: a small y + vowel, they only exist in digraphs.
YOON = [
    ("キャ", "kya"), ("キュ", "kyu"), ("キョ", "kyo"),
    ("ギャ", "gya"), ("ギュ", "gyu"), ("ギョ", "gyo"),
    ("シャ", "sha"), ("シュ", "shu"), ("ショ", "sho"),
    ("ジャ", "ja"), ("ジュ", "ju"), ("ジョ", "jo"),
    ("チャ", "cha"), ("チュ", "chu"), ("チョ", "cho"),
    ("ニャ", "nya"), ("ニュ", "nyu"), ("ニョ", "nyo"),
    ("ヒャ", "hya"), ("ヒュ", "hyu"), ("ヒョ", "hyo"),
    ("ビャ", "bya"), ("ビュ", "byu"), ("ビョ", "byo"),
    ("ピャ", "pya"), ("ピュ", "pyu"), ("ピョ", "pyo"),
    ("ミャ", "mya"), ("ミュ", "myu"), ("ミョ", "myo"),
    ("リャ", "rya"), ("リュ", "ryu"), ("リョ", "ryo"),
]

YOON_NOTE = "yōon digraph: a palatalised y followed by a vowel, such as きゃ (kya)"

# Katakana that exist only to write sounds of other languages.
FOREIGN_KATAKANA = [
    ("ファ", "fa"), ("フィ", "fi"), ("フェ", "fe"), ("フォ", "fo"),
    ("ウィ", "wi"), ("ウェ", "we"), ("ウォ", "wo"),
    ("ヴァ", "va"), ("ヴィ", "vi"), ("ヴ", "vu"), ("ヴェ", "ve"), ("ヴォ", "vo"),
    ("ツァ", "tsa"), ("ツィ", "tsi"), ("ツェ", "tse"), ("ツォ", "tso"),
    ("シェ", "she"), ("ジェ", "je"), ("チェ", "che"),
    ("ティ", "ti"), ("ディ", "di"), ("トゥ", "tu"), ("ドゥ", "du"),
    ("クヮ", "kwa"), ("グヮ", "gwa"),
]

FOREIGN_NOTE = "extended katakana: it is only used to write sounds from other languages, such as ファイル (fairu)"

# ------------------------------------------------------------- example sentences
#
# Every kanji gets a short example sentence. Two things make the sentences
# readable for a learner:
#
# * furigana, taken from the Tatoeba "Hrkt" transcription of the sentence, which
#   is written as [漢字|よみ|...per character readings] and covers every kanji;
# * word spacing. Real Japanese does not put spaces between words, so the text is
#   segmented and the words are separated with a space. This is a learning aid,
#   deliberately not how the language is written.
#
# Sentences come from Tatoeba, preferring the Tanaka Corpus: those are the
# textbook sentences and by far the simplest ones available.

# A furigana group: base, then the reading of the base, then one reading per
# character of the base (only the second field is needed to render ruby text).
# Tatoeba also uses {...} for the same thing, and occasionally mixes both.
FURIGANA = re.compile(r"[\[{]([^\]}|]*)\|([^\]}|]*)(?:\|[^\]}]*)?[}\]]")
KANJI_CHAR = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")

# Sentences that are not clean prose: markup, URLs, dates, ellipsis spam...
NOISE = re.compile(r"[<>{}~|/\\=*&#]|https?://|\d{4}-\d{2}|…{2,}")
# Punctuation, used to keep word spacing from running across a sentence break.
PUNCTUATION = "。、！？!?,.「」『』…・"

TANAKA_URL = "https://downloads.tatoeba.org/exports/jpn_indices.tar.bz2"


def furigana_segments(transcription: str) -> list[tuple[str, str | None]]:
    """Split a Tatoeba Hrkt transcription into (text, reading|None) pairs."""
    out: list[tuple[str, str | None]] = []
    pos = 0
    for match in FURIGANA.finditer(transcription):
        if match.start() > pos:
            out.append((transcription[pos : match.start()], None))
        out.append((match.group(1), match.group(2)))
        pos = match.end()
    if pos < len(transcription):
        out.append((transcription[pos:], None))
    return out


def furigana_plain(transcription: str) -> str:
    """The sentence text with the furigana markup removed."""
    return "".join(text for text, _reading in furigana_segments(transcription))


def ruby_spans(text: str, segments: list[tuple[str, str | None]]) -> list[tuple[int, int, str]]:
    """Where the annotated kanji runs sit inside `text`: (start, end, reading)."""
    spans = []
    pos = 0
    for piece, reading in segments:
        if reading:
            spans.append((pos, pos + len(piece), reading))
        pos += len(piece)
    return spans


def load_tokenizer():
    """janome, if it is installed. Word spacing is skipped without it."""
    try:
        from janome.tokenizer import Tokenizer

        return Tokenizer()
    except ImportError:
        return None


def spaced_example(tokenizer, text: str, segments: list[tuple[str, str | None]]) -> str:
    """Render one sentence as ruby HTML with words separated by spaces.

    The sentence is segmented word by word; a word that is annotated with
    furigana is wrapped in <ruby>. Kana that continue a word (the okurigana of a
    verb or adjective) is joined back onto the word it belongs to, so 勉強し
    ている reads as one word instead of three.
    """
    spans = ruby_spans(text, segments)
    if not spans or furigana_plain("".join(piece for piece, _reading in segments)) != text:
        return None

    pieces: list[list] = []
    if tokenizer is None:
        # No segmenter available: split the sentence into its annotated runs and
        # the kana in between, and give each of them its own word. The example is
        # still readable, the spacing is just coarser.
        pos = 0
        for start, end, reading in spans:
            if start > pos:
                pieces.append([text[pos:start], None, "名詞"])
            pieces.append([text[start:end], reading, "名詞"])
            pos = end
        if pos < len(text):
            pieces.append([text[pos:], None, "名詞"])
    else:
        offset = 0
        for token in tokenizer.tokenize(text):
            surface = token.surface
            if not surface.strip():
                offset += len(surface)
                continue
            start, end = offset, offset + len(surface)
            offset = end
            # Keep the fields joined with no separator: the checks below look
            # for whole values such as 助詞 inside the string.
            part_of_speech = "".join(token.part_of_speech or ())
            # Cut the word wherever a furigana run starts or ends, so that
            # 月見て becomes <ruby>月</ruby>見て rather than losing the reading.
            cuts = sorted(
                {start, end}
                | {s for s, _e, _r in spans if start < s < end}
                | {e for _s, e, _r in spans if start < e < end}
            )
            for a, b in zip(cuts, cuts[1:]):
                reading = next((r for s, e, r in spans if s <= a and b <= e), None)
                pieces.append([text[a:b], reading, part_of_speech])

    # Okurigana belongs to the word it follows, so 勉強 + して + います and
    # 眠ら + なければ + なりません are single words. janome splits the okurigana
    # off, so runs are glued back together unless the run starts a new
    # grammatical word.
    #
    # A run with furigana is the head of its word (眠 + ら), never the tail, so it
    # also starts a new word when the previous run was a noun.
    #
    # The furigana stays on the kanji it covers, so a word is a list of
    # (text, reading) runs and only the word boundaries move.
    # A run with furigana is usually the head of a word, but it can also be the
    # okurigana-side of a verb the segmenter split: 愛して (ruby on 愛) + いる is
    # really 愛している. When the previous run is a verb, the ruby run continues
    # it. Otherwise a ruby run always starts a new word.
    VERB_PARTS = ("動詞", "形容詞")
    NEW_WORD_PARTS = ("名詞", "助詞", "記号", "接頭詞", "接続詞", "感動詞", "フィラー", "代名詞")
    # ば / な / ゃ … continue the verb or adjective they follow, so
    # しなければならない is one word, but は / が / を / に start a new one.
    CONTINUES_VERB_PARTS = ("接続助詞", "副助詞")
    words: list[list] = []
    previous_continues = False  # the previous run is part of a verb phrase
    for surface, reading, part_of_speech in pieces:
        previous = words[-1] if words else []
        previous_text = previous[-1][0] if previous else ""
        auxiliary = "助詞" in part_of_speech and any(
            kind in part_of_speech for kind in CONTINUES_VERB_PARTS
        )
        starts_word = (
            surface in PUNCTUATION
            or not previous_text
            or previous_text[-1] in PUNCTUATION
            or (
                reading is not None
                and not previous_continues
            )
            or (
                any(part in part_of_speech for part in NEW_WORD_PARTS)
                and not auxiliary
                and reading is None
            )
        )
        if previous and not starts_word:
            previous.append((surface, reading))
            previous_continues = any(part in part_of_speech for part in VERB_PARTS) or auxiliary
            continue
        words.append([(surface, reading)])
        previous_continues = any(part in part_of_speech for part in VERB_PARTS) or auxiliary

    # A run with furigana becomes <ruby>text<rt>reading</rt></ruby>, everything
    # else is escaped as is. Runs of the same word are glued together; words are
    # separated by a space.
    def render_run(text_run: str, reading: str | None) -> str:
        if reading:
            return f"<ruby>{html.escape(text_run)}<rp>(</rp><rt>{html.escape(reading)}</rt><rp>)</rp></ruby>"
        return html.escape(text_run)

    return " ".join(
        "".join(render_run(text_run, reading) for text_run, reading in runs if text_run)
        for runs in words
        if any(text_run for text_run, _reading in runs)
    )


def load_examples(tokenizer, wanted: set[str]) -> dict[str, dict]:
    """Pick one short, simple example sentence per kanji."""
    sentences = {}
    with bz2.open(fetch(TATOEBA_URL.format(name="jpn_sentences"), "tatoeba-jpn-sentences.tsv.bz2"), "rt", encoding="utf-8") as handle:
        for line in handle:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 3:
                sentences[int(parts[0])] = parts[2]

    transcriptions = {}
    path = fetch(TATOEBA_URL.format(name="jpn_transcriptions"), "tatoeba-jpn-transcriptions.tsv.bz2")
    with bz2.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 5 and parts[1] == "jpn" and parts[2] == "Hrkt":
                transcriptions[int(parts[0])] = parts[4]

    # The Tanaka Corpus sentences are the textbook ones: simplest and best for
    # a beginner, so they win over everything else.
    textbook = set()
    with bz2.open(fetch(TANAKA_URL, "tatoeba-jpn-indices.tsv.bz2"), "rt", encoding="utf-8") as handle:
        for line in handle:
            head = line.split("\t", 1)[0]
            if head.isdigit():
                textbook.add(int(head))

    # Per kanji, per quality tier: textbook sentences first, then any clean short
    # sentence, then longer ones, then sentences with gaps in the furigana.
    pools: dict[str, dict[int, list[int]]] = {}
    for sentence_id, text in sentences.items():
        transcription = transcriptions.get(sentence_id)
        if not transcription or not text or NOISE.search(text):
            continue
        segments = furigana_segments(transcription)
        if furigana_plain(transcription) != text:
            continue  # transcription out of date with the sentence, or malformed markup
        annotated = {ch for start, end, _r in ruby_spans(text, segments) for ch in text[start:end]}
        kanji = {ch for ch in text if KANJI_CHAR.match(ch)}
        if not kanji:
            continue
        complete = kanji <= annotated
        ends_well = text[-1] in "。！？!?"
        if complete and ends_well and 5 <= len(text) <= 26 and sentence_id in textbook:
            tier = 0
        elif complete and ends_well and 4 <= len(text) <= 30:
            tier = 1
        elif ends_well and 3 <= len(text) <= 34:
            tier = 2
        else:
            tier = 3
        for ch in kanji & wanted:
            pools.setdefault(ch, {}).setdefault(tier, []).append(sentence_id)

    examples: dict[str, dict] = {}
    for ch, tiers in pools.items():
        tier = next((t for t in (0, 1, 2, 3) if tiers.get(t)), 3)
        best = None
        for sentence_id in tiers[tier]:
            text = sentences[sentence_id]
            spans = ruby_spans(text, furigana_segments(transcriptions[sentence_id]))
            run = next((text[s:e] for s, e, _r in spans if ch in text[s:e]), "")
            distinct = len({c for c in text if KANJI_CHAR.match(c)})
            score = tier * 1000 + len(text) + distinct * 2.0
            score -= 8 if len(run) == 1 else 0  # the kanji alone is the clearest
            score -= 4 if text.count(ch) == 1 else 0
            if best is None or score < best[0]:
                best = (score, sentence_id)
        sentence_id = best[1]
        example = spaced_example(tokenizer, sentences[sentence_id], furigana_segments(transcriptions[sentence_id]))
        if example:
            examples[ch] = {"ex": example, "ts": 1 if sentence_id in textbook else 0}
    return examples


def jmdict_examples(wanted: set[str], dictionary: dict) -> dict[str, dict]:
    """A word example for the kanji that no Tatoeba sentence uses.

    Some rare Jōyō characters appear in no everyday sentence at all, so a word
    from JMdict is used instead. If JMdict has no word either, the kanji is shown
    with its own reading.
    """
    import tarfile

    archive = fetch(JMDICT_URL, "jmdict.json.tgz")
    examples: dict[str, dict] = {}
    with tarfile.open(archive, "r:gz") as tar:
        member = next(m for m in tar.getmembers() if m.name.endswith(".json"))
        with tar.extractfile(member) as raw:
            data = json.loads(raw.read().decode("utf-8"))
    for word in data["words"]:
        if not wanted:
            break
        kanji_forms = [k["text"] for k in (word.get("kanji") or [])]
        readings = [k["text"] for k in (word.get("kana") or []) if not k.get("tags")]
        if not kanji_forms or not readings:
            continue
        for form in kanji_forms:
            hits = set(form) & wanted
            if not hits or len(form) > 4:
                continue
            for ch in hits:
                if ch in examples:
                    continue
                reading = readings[0]
                examples[ch] = {
                    "ex": f"<ruby>{html.escape(form)}<rp>(</rp><rt>{html.escape(reading)}</rt><rp>)</rp></ruby>",
                    "w": 1,
                }
    # Last resort: nothing in JMdict either, so show the character with its own
    # reading, taken from KANJIDIC.
    for ch in sorted(wanted - set(examples)):
        entry = dictionary.get(ch) or {}
        readings = entry.get("kun") or entry.get("on") or []
        reading = readings[0] if readings else ""
        examples[ch] = {
            "ex": f"<ruby>{html.escape(ch)}<rp>(</rp><rt>{html.escape(reading)}</rt><rp>)</rp></ruby>",
            "w": 1,
        }
    return examples


# ------------------------------------------------------------------ downloading

ATTEMPTS = 4


def fetch(url: str, name: str) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    target = CACHE / name
    if target.exists() and target.stat().st_size > 0:
        return target
    request = urllib.request.Request(url, headers={"User-Agent": "kanji-flashcards-builder"})
    for attempt in range(1, ATTEMPTS + 1):
        try:
            print(f"  downloading {name} (attempt {attempt}) ...", flush=True)
            with urllib.request.urlopen(request, timeout=180) as response:
                target.write_bytes(response.read())
            return target
        except Exception as error:  # noqa: BLE001 - retried, then reported as is
            if attempt == ATTEMPTS:
                raise
            print(f"    failed: {error} - retrying", flush=True)
            time.sleep(2 * attempt)
    raise AssertionError("unreachable")


def load_json(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def normalise(kanji: str) -> str:
    """Sources mark glyphs outside JIS X 0208 with parentheses."""
    return kanji.strip("()")


# ---------------------------------------------------------------- KANJIDIC2

def build_dictionary(kanjidic: list[dict]) -> dict[str, dict]:
    dictionary: dict[str, dict] = {}
    for entry in kanjidic:
        character = entry.get("literal")
        if not character:
            continue
        meanings: list[str] = []
        for item in entry.get("meanings", []):
            if item.get("m_lang"):
                continue
            meaning = item.get("meaning", "").strip()
            if not meaning or MEANING_NOISE.search(meaning):
                continue
            if meaning not in meanings:
                meanings.append(meaning)
        on: list[str] = []
        kun: list[str] = []
        for item in entry.get("readings", []):
            reading = item.get("reading", "")
            kind = item.get("r_type")
            if kind == "ja_on" and reading not in on:
                on.append(reading)
            elif kind == "ja_kun" and reading not in kun:
                kun.append(reading)
        dictionary[character] = {"m": meanings, "on": on, "kun": kun, "s": entry.get("stroke_count")}
    return dictionary


# ------------------------------------------------------------------ Joyo table

def parse_joyo_table(wikitext: str) -> tuple[list[str], dict[str, int]]:
    """Return the Jōyō kanji in official table order plus their school grade.

    The Wikipedia table is sorted the same way as the official 常用漢字表 (by
    on'yomi, then kun'yomi). Secondary school characters are all marked "S",
    which is what we want: years 7-12 come from the Kanken levels instead.
    """
    order: list[str] = []
    grades: dict[str, int] = {}
    row = re.compile(r"^\|\s*(\d+)\|\|(.*)$", re.M)
    kanji_cell = re.compile(r"wikt:[^|\]]*\|([^|\]]+)\]")
    for number, body in row.findall(wikitext):
        line = "|" + number + "||" + body
        match = kanji_cell.search(line)
        if not match:
            raise SystemExit(f"Jōyō row {number} has no kanji cell")
        character = html.unescape(match.group(1)).strip()
        character = FORM_EQUIVALENTS.get(character, character)
        if not is_kanji(character):
            raise SystemExit(f"Jōyō row {number} has an unexpected cell: {character!r}")
        if character in grades:
            raise SystemExit(f"Jōyō row {number} repeats {character}")
        order.append(character)
        cells = body.split("||")
        grade = cells[4].strip() if len(cells) > 4 else ""
        if grade.isdigit():
            grades[character] = int(grade)
    if len(order) != JOYO_TOTAL:
        raise SystemExit(f"Jōyō table has {len(order)} kanji, expected {JOYO_TOTAL}")
    return order, grades


def is_kanji(character: str) -> bool:
    if len(character) != 1:
        return False
    code = ord(character)
    return 0x3400 <= code <= 0x9FFF or 0xF900 <= code <= 0xFAFF or 0x20000 <= code <= 0x2FA1F


# ------------------------------------------------------------------- Joyo lists

def joyo_lists(kanken: list[dict], official_order: list[str], official_grades: dict[str, int]) -> list[list[str]]:
    drop = set(KYUJITAI_FORMS)
    levels = {
        item["level"]: [k for k in (normalise(c) for c in item["kanjiList"]) if k not in drop]
        for item in kanken
    }
    rank = {kanji: index for index, kanji in enumerate(official_order)}
    missing = sorted(set(official_order) - {k for group in levels.values() for k in group})
    if missing:
        raise SystemExit("Kanken levels do not cover: " + "".join(missing))

    lists: list[list[str]] = []
    for year, level, half in SCHOOL_YEARS:
        # Keep the official 常用漢字表 order inside every list.
        kanjis = sorted(levels[level], key=lambda kanji: rank[kanji])
        if half:
            middle = len(kanjis) // 2
            kanjis = kanjis[:middle] if half == 1 else kanjis[middle:]
        lists.append(kanjis)

    # Years 1-6 must match the elementary school grades of the official table.
    for year in range(1, 7):
        expected = [kanji for kanji, grade in official_grades.items() if grade == year]
        if sorted(lists[year - 1]) != sorted(expected):
            raise SystemExit(f"Jōyō year {year} does not match the official elementary grade")

    flat = [kanji for group in lists for kanji in group]
    if len(flat) != len(set(flat)):
        duplicates = sorted({k for k in flat if flat.count(k) > 1})
        raise SystemExit("duplicate kanji across Jōyō lists: " + "".join(duplicates))
    if sorted(flat) != sorted(official_order):
        extra = sorted(set(flat) - set(official_order))
        absent = sorted(set(official_order) - set(flat))
        raise SystemExit(f"Jōyō mismatch - extra: {''.join(extra)} absent: {''.join(absent)}")
    print(f"  Jōyō: {len(lists)} lists, {len(flat)} kanji")
    return lists


# ------------------------------------------------------------------- JLPT lists

def jlpt_lists() -> list[list[str]]:
    lists: list[list[str]] = []
    for level in JLPT_LEVELS:
        entries = load_json(fetch(OPENJLPT_URL.format(level=level), f"openjlpt-{level}.json"))
        for entry in entries:
            entry.setdefault("freq", 0)
        # Most frequent kanji first, then a couple of stable tie breakers.
        entries.sort(key=lambda item: (item.get("freq") or 99999, item.get("strokes") or 99, item["character"]))
        lists.append([entry["character"] for entry in entries])
        print(f"  JLPT {level.upper()}: {len(lists[-1])} kanji")
    return lists


# ------------------------------------------------------------------ kana lists

def kana_lists() -> tuple[list[list[str]], dict[str, dict]]:
    """Return the four kana lists and their reading/notes, grouped by syllabary."""
    details: dict[str, dict] = {}
    lists: dict[str, list[str]] = {"hiragana": [], "hiragana-extra": [], "katakana": [], "katakana-extra": []}

    def add(list_name: str, characters: str, reading: str | list[str], note: str) -> None:
        """Add one or more kana to a list.

        `reading` is either a single reading for the whole `characters` string
        (a digraph such as キャ) or one reading per character (a gojūon row).
        """
        pairs = [(characters, reading)] if isinstance(reading, str) else list(zip(characters, reading))
        for character, value in pairs:
            if character in details:
                raise SystemExit(f"kana {character} is in more than one list")
            details[character] = {"r": value, "m": note}
            lists[list_name].append(character)

    # The 46 basic kana, in gojūon order.
    for row_key, hiragana, katakana, readings, note in GOJUON:
        if row_key in VOICED_ROWS:
            continue
        row = readings.split()
        add("hiragana", hiragana, row, note)
        add("katakana", katakana, row, note)
    for name, kanjis in (("Hiragana", lists["hiragana"]), ("Katakana", lists["katakana"])):
        if len(kanjis) != 46:
            raise SystemExit(f"the basic {name} table has {len(kanjis)} kana, expected 46")

    # Dakuten and handakuten rows.
    for row_key, hiragana, katakana, readings, note in GOJUON:
        if row_key in VOICED_ROWS:
            add("hiragana-extra", hiragana, readings.split(), note)
            add("katakana-extra", katakana, readings.split(), note)

    # Small kana, sokuon, archaic kana and the long vowel mark.
    for hiragana, katakana, reading in SMALL_KANA:
        add("hiragana-extra", hiragana, reading, SMALL_NOTE)
        add("katakana-extra", katakana, reading, SMALL_NOTE)
    add("hiragana-extra", SOKUON[0], SOKUON[2], SOKUON[3])
    add("katakana-extra", SOKUON[1], SOKUON[2], SOKUON[3])
    add("katakana-extra", CHOONPU[0], CHOONPU[2], CHOONPU[3])
    for character, reading, note in ARCHAIC_HIRAGANA:
        add("hiragana-extra", character, reading, note)
    for character, reading, note in ARCHAIC_KATAKANA:
        add("katakana-extra", character, reading, note)

    # Katakana only: yōon digraphs and the extended kana for foreign sounds.
    for character, reading in YOON:
        add("katakana-extra", character, reading, YOON_NOTE)
    for character, reading in FOREIGN_KATAKANA:
        add("katakana-extra", character, reading, FOREIGN_NOTE)

    ordered = [lists["hiragana"], lists["hiragana-extra"], lists["katakana"], lists["katakana-extra"]]
    for name, kanjis in zip(["Hiragana", "Hiragana extras", "Katakana", "Katakana extras"], ordered):
        print(f"  {name}: {len(kanjis)} kana")
    return ordered, details


# ------------------------------------------------------------------ write files

def encode(character: str, entry: dict, example: dict | None) -> str:
    return (
        f'"{character}":{{'
        f'"m":"{" | ".join(entry["m"])}"'
        f',"on":"{" | ".join(entry["on"])}"'
        f',"kun":"{" | ".join(entry["kun"])}"'
        + (f',"s":{entry["s"]}' if entry.get("s") else "")
        + (f',"ex":"{example["ex"]}"' if example else "")
        + (f',"ts":{example["ts"]}' if example and example.get("ts") else "")
        + (f',"w":{example["w"]}' if example and example.get("w") else "")
        + "}"
    )


def encode_kana(character: str, entry: dict) -> str:
    return f'"{character}":{{"r":"{entry["r"]}","m":"{entry["m"]}"}}'


def write_details(name: str, kanjis: list[str], dictionary: dict, examples: dict) -> None:
    unknown = [k for k in kanjis if k not in dictionary]
    if unknown:
        raise SystemExit(f"{name}: no dictionary entry for {''.join(unknown)}")
    without_meanings = [k for k in kanjis if not dictionary[k]["m"]]
    if without_meanings:
        print(f"  warning: {name}: {len(without_meanings)} kanji without English meanings")
    body = ",\n".join(encode(k, dictionary[k], examples.get(k)) for k in kanjis)
    text = (
        "// Generated by build-data.py - do not edit by hand.\n"
        "// Readings, meanings and stroke counts from KANJIDIC2 (EDRDG), CC BY-SA 4.0.\n"
        "// Example sentences with furigana from Tatoeba, CC BY 2.0 FR.\n"
        f'window.KANJI_DETAILS["{name}"] = {{\n{body}\n}};\n'
    )
    (OUT_DATA / f"details-{name}.js").write_text(text, encoding="utf-8")
    print(f"  wrote js/data/details-{name}.js ({(len(text) / 1024):.0f} KB)")


def write_kana_details(details: dict[str, dict]) -> None:
    body = ",\n".join(encode_kana(character, details[character]) for character in sorted(details, key=lambda k: (len(k), k)))
    text = (
        "// Generated by build-data.py - do not edit by hand.\n"
        "// Hepburn readings and notes for the kana, from the official gojūon (五十音) table.\n"
        'window.KANJI_DETAILS["kana"] = {\n' + body + "\n};\n"
    )
    (OUT_DATA / "details-kana.js").write_text(text, encoding="utf-8")
    print(f"  wrote js/data/details-kana.js ({(len(text) / 1024):.0f} KB)")


YEAR_DESCRIPTIONS = {
    1: "1st grade",
    2: "2nd grade",
    3: "3rd grade",
    4: "4th grade",
    5: "5th grade",
    6: "6th grade",
    7: "junior high, year 1",
    8: "junior high, year 2",
    9: "junior high, year 3",
    10: "senior high, year 1",
    11: "senior high, year 2",
    12: "senior high, year 3",
}


KANA_LIST_META = [
    ("kana-hiragana", "Hiragana", "the 46 basic kana"),
    ("kana-hiragana-extra", "Hiragana extras", "dakuten, handakuten, small and archaic kana"),
    ("kana-katakana", "Katakana", "the 46 basic kana"),
    ("kana-katakana-extra", "Katakana extras", "dakuten, small, yōon and foreign sound kana"),
]


def write_lists(kana: list[list[str]], joyo: list[list[str]], jlpt: list[list[str]]) -> None:
    # Kana are stored one string per item so that digraphs such as キャ stay
    # together; kanji lists hold one character per item.
    entries: list[str] = []

    def add(list_id: str, group: str, label: str, hint: str, items: list[str]) -> None:
        entries.append(
            f'  {{ id: "{list_id}", group: "{group}", label: "{label}", hint: "{hint}",'
            f" kanjis: {json.dumps(items, ensure_ascii=False, separators=(',', ':'))} }}"
        )

    for (list_id, label, hint), characters in zip(KANA_LIST_META, kana):
        add(list_id, "kana", label, f"{hint} - {len(characters)} kana", characters)
    for level, characters in zip(["N5", "N4", "N3", "N2", "N1"], jlpt):
        add(f"jlpt-{level.lower()}", "jlpt", f"JLPT {level}", f"{len(characters)} kanji", characters)
    for year, characters in enumerate(joyo, start=1):
        add(f"joyo-{year}", "joyo", f"Jōyō grade {year}", f"{YEAR_DESCRIPTIONS[year]} - {len(characters)} kanji", characters)

    text = (
        "// Generated by build-data.py - do not edit by hand.\n"
        "// Jōyō order follows the official 常用漢字表; JLPT order follows kanji frequency;\n"
        "// kana order follows the official 五十音 (gojūon) table.\n"
        "window.KANJI_LISTS = [\n" + ",\n".join(entries) + "\n];\n"
    )
    (OUT_DATA / "lists.js").write_text(text, encoding="utf-8")
    print(f"  wrote js/data/lists.js ({(len(text) / 1024):.0f} KB)")


def write_licenses() -> None:
    share_alike = fetch(CC_BY_SA_URL, "cc-by-sa-4.0.txt").read_text(encoding="utf-8", errors="replace")
    attribution = fetch(CC_BY_FR_URL, "cc-by-2.0-fr.html").read_text(encoding="utf-8", errors="replace")
    (ROOT / "DATA-LICENSE.txt").write_text(share_alike, encoding="utf-8")
    (ROOT / "DATA-LICENSE-CC-BY-2.0-FR.txt").write_text(attribution, encoding="utf-8")
    print("  wrote DATA-LICENSE.txt and DATA-LICENSE-CC-BY-2.0-FR.txt")


# ----------------------------------------------------------------------- main

def main() -> int:
    OUT_DATA.mkdir(parents=True, exist_ok=True)
    print("Loading sources ...")
    kanjidic = load_json(fetch(KANJIDIC2_URL, "kanjidic2.json"))
    kanken = load_json(fetch(KANKEN_URL, "kanken.json"))
    joyo_table = fetch(WIKIPEDIA_URL.format(title=urllib.parse.quote(JOYO_TITLE)), "wikipedia-joyo.txt").read_text(
        encoding="utf-8"
    )
    dictionary = build_dictionary(kanjidic)
    official_order, official_grades = parse_joyo_table(joyo_table)

    print("Building lists ...")
    joyo = joyo_lists(kanken, official_order, official_grades)
    jlpt = jlpt_lists()
    kana, kana_details = kana_lists()

    print("Picking example sentences ...")
    tokenizer = load_tokenizer()
    if tokenizer is None:
        print("  note: janome is not installed, so the example sentences will have no word spacing")
        print("        (pip install janome to get it)")
    all_kanji = {kanji for group in joyo for kanji in group} | {kanji for group in jlpt for kanji in group}
    examples = load_examples(tokenizer, all_kanji)
    print(f"  Tatoeba sentences: {sum(1 for e in examples.values() if not e.get('w'))} of {len(all_kanji)} kanji")
    missing = all_kanji - set(examples)
    if missing:
        fallback = jmdict_examples(missing, dictionary)
        print(f"  JMdict words for the remaining {len(fallback)} kanji")
        examples.update(fallback)

    print("Writing data files ...")
    joyo_kanji = {kanji for group in joyo for kanji in group}
    jlpt_kanji = {kanji for group in jlpt for kanji in group}
    write_details("joyo", sorted(joyo_kanji, key=ord), dictionary, examples)
    write_details("jlpt", sorted(jlpt_kanji, key=ord), dictionary, examples)
    write_kana_details(kana_details)
    write_lists(kana, joyo, jlpt)
    write_licenses()
    return 0


if __name__ == "__main__":
    sys.exit(main())
