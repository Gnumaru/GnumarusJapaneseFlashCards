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

Run with:  python3 build-data.py
"""

from __future__ import annotations

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
CC_BY_SA_URL = "https://creativecommons.org/licenses/by-sa/4.0/legalcode.txt"

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


# ------------------------------------------------------------------ write files

def encode(character: str, entry: dict) -> str:
    return (
        f'"{character}":{{'
        f'"m":"{" | ".join(entry["m"])}"'
        f',"on":"{" | ".join(entry["on"])}"'
        f',"kun":"{" | ".join(entry["kun"])}"'
        + (f',"s":{entry["s"]}' if entry.get("s") else "")
        + "}"
    )


def write_details(name: str, kanjis: list[str], dictionary: dict) -> None:
    unknown = [k for k in kanjis if k not in dictionary]
    if unknown:
        raise SystemExit(f"{name}: no dictionary entry for {''.join(unknown)}")
    without_meanings = [k for k in kanjis if not dictionary[k]["m"]]
    if without_meanings:
        print(f"  warning: {name}: {len(without_meanings)} kanji without English meanings")
    body = ",\n".join(encode(k, dictionary[k]) for k in kanjis)
    text = (
        "// Generated by build-data.py - do not edit by hand.\n"
        "// Readings, meanings and stroke counts from KANJIDIC2 (EDRDG), CC BY-SA 4.0.\n"
        f'window.KANJI_DETAILS["{name}"] = {{\n{body}\n}};\n'
    )
    (OUT_DATA / f"details-{name}.js").write_text(text, encoding="utf-8")
    print(f"  wrote js/data/details-{name}.js ({(len(text) / 1024):.0f} KB)")


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


def write_lists(joyo: list[list[str]], jlpt: list[list[str]]) -> None:
    entries: list[str] = []
    for level, kanjis in zip(["N5", "N4", "N3", "N2", "N1"], jlpt):
        entries.append(
            f'  {{ id: "jlpt-{level.lower()}", group: "jlpt", label: "JLPT {level}",'
            f' hint: "{len(kanjis)} kanji", kanjis: "{"".join(kanjis)}" }}'
        )
    for year, kanjis in enumerate(joyo, start=1):
        entries.append(
            f'  {{ id: "joyo-{year}", group: "joyo", label: "Jōyō grade {year}",'
            f' hint: "{YEAR_DESCRIPTIONS[year]} - {len(kanjis)} kanji", kanjis: "{"".join(kanjis)}" }}'
        )
    text = (
        "// Generated by build-data.py - do not edit by hand.\n"
        "// Jōyō order follows the official 常用漢字表; JLPT order follows kanji frequency.\n"
        "window.KANJI_LISTS = [\n" + ",\n".join(entries) + "\n];\n"
    )
    (OUT_DATA / "lists.js").write_text(text, encoding="utf-8")
    print(f"  wrote js/data/lists.js ({(len(text) / 1024):.0f} KB)")


def write_licenses() -> None:
    text = fetch(CC_BY_SA_URL, "cc-by-sa-4.0.txt").read_text(encoding="utf-8", errors="replace")
    (ROOT / "DATA-LICENSE.txt").write_text(text, encoding="utf-8")
    print("  wrote DATA-LICENSE.txt")


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

    print("Writing data files ...")
    joyo_kanji = {kanji for group in joyo for kanji in group}
    jlpt_kanji = {kanji for group in jlpt for kanji in group}
    write_details("joyo", sorted(joyo_kanji, key=ord), dictionary)
    write_details("jlpt", sorted(jlpt_kanji, key=ord), dictionary)
    write_lists(joyo, jlpt)
    write_licenses()
    return 0


if __name__ == "__main__":
    sys.exit(main())
