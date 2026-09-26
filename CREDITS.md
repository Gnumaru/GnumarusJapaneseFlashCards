# Data credits

The application code in this repository is MIT licensed (see `LICENSE`). The
kanji data files under `js/data/` are **derived works** and are therefore licensed
under **CC BY-SA 4.0** — the license of the upstream data they come from. The
full license text is in [`DATA-LICENSE.txt`](DATA-LICENSE.txt).

| Data | Used for | Source | License |
| --- | --- | --- | --- |
| KANJIDIC2 | Readings (on'yomi / kun'yomi), English meanings, stroke counts | Electronic Dictionary Research and Development Group — <https://www.edrdg.org/wiki/KANJIDIC_Project.html> | CC BY-SA 4.0 (EDRDG licence) |
| Jonathan Waller's JLPT kanji levels, packaged as [OpenJLPT](https://github.com/evanclan/OpenJLPT) | JLPT N5–N1 membership and kanji frequency | <https://www.tanos.co.uk/jlpt/> | CC BY-SA 4.0 |
| [List of jōyō kanji](https://en.wikipedia.org/wiki/List_of_j%C5%8Dy%C5%8D_kanji) on Wikipedia | The 2136 Jōyō characters in the order of the official 常用漢字表, and the elementary school grade of each | Wikimedia Foundation | CC BY-SA 4.0 |
| [kanken-json](https://github.com/hoffmannjp/kanken-json) | Kanji Kentei (漢検) grade lists, used to spread the 1110 secondary school Jōyō kanji over school years 7–12 | Benjamin Hoffmann | MIT |

KANJIDIC2 is the property of the Electronic Dictionary Research and Development
Group and is used in conformance with the Group's
[licence](https://www.edrdg.org/edrdg/licence.html).

## How the Jōyō grades are built

* **Grades 1–6** are the official 学年別漢字配当表 (elementary school) content: the
  80 / 160 / 200 / 202 / 193 / 191 characters, in the order of the official table.
  `build-data.py` fails if these do not match the elementary grades published
  with the Jōyō table.
* **Grades 7–8** are the two junior high Kanji Kentei levels (4級 and 3級).
* **Grades 9–12** split the two senior high Kanji Kentei levels in half, because
  the Ministry of Education does not publish a per-year table for secondary
  school and the 常用漢字表 is not split by year either. The halves follow the
  official reading order, so each year continues where the previous one stopped.

The 2136 characters of the twelve lists together are exactly the 2136 characters
of the Jōyō kanji list; the build script verifies this.

## JLPT levels

The Japan Foundation does not publish official JLPT kanji lists, so the N5–N1
membership comes from Jonathan Waller's widely used community lists, the same
source OpenJLPT uses. KANJIDIC2's own `jlpt` field (the pre-2010 four level
system) is deliberately not used.
