# GnumarusJapaneseFlashCards

A flashcard trainer for hiragana, katakana and kanji, built with plain HTML,
CSS and JavaScript. There are no dependencies, no build step and no network
calls at runtime: open `index.html` in a browser and it works, straight from
`file://` or from a web server.

## Lists

**Kana** (4 lists, in the order of the official 五十音 table)

* **Hiragana** — the 46 basic kana: あいうえお かきくけこ …
* **Hiragana extras** — dakuten, handakuten, small kana, っ and the archaic ゐゑ
* **Katakana** — the 46 basic kana: アイウエオ カキクケコ …
* **Katakana extras** — dakuten, small kana, ッ, ー, the archaic ヰヱ, the yōon
  (キャ シャ チャ …) and the extended kana used for foreign sounds
  (ファ ヴァ ティ シェ …)

**Kanji** (17 lists)

* **JLPT N5 → N1** (79, 166, 367, 367 and 1232 kanji), ordered from the most
  frequent kanji to the least frequent.
* **Jōyō grades 1 → 12** (all 2136 Jōyō kanji), ordered the way the official
  常用漢字表 is: grade 1 starts with 一右雨円王音下… See
  [CREDITS.md](CREDITS.md) for how the school years are derived.

Pick a list, and the cards come up one after another in the order of that list.

## How to study

| Action | Result |
| --- | --- |
| Click the character (or `Space` / `Enter`) | Show or hide its data: an example sentence, meanings, on'yomi, kun'yomi and stroke count for kanji; reading and a note for kana |
| `←` | Move the current card to the end of the list, to study it again later |
| `→` | Take the current card out of the list (it counts as practiced) |
| `S` | Shuffle the cards that are left |
| `O` | Sort the cards that are left back into the original order of the list |
| `R` | Reset the list, so practiced cards come back |
| `L` | Go back to the list picker |

The same actions are available as buttons under the card, and the list can be
changed at any moment from the picker in the top bar or from **Change list**.
When every card of a list has been practiced, the app shows them and offers to
practice exactly those again.

Progress is kept per list in the browser's `localStorage`, so reloading or
switching lists does not lose your place. Nothing is sent anywhere.

## Example sentences

Every kanji card has a short example sentence with furigana, for example 犬:

> これ は <ruby>犬<rt>いぬ</rt></ruby> です 。

Two things are done on purpose to help a learner:

* **Furigana** sits above the kanji, using the readings Tatoeba contributors
  attached to the sentence.
* **Word spacing.** Real Japanese is written without spaces. The example is
  segmented word by word and the words are separated with a space, so a beginner
  can see where one word ends and the next begins. This is a teaching aid, not
  correct Japanese typography — do not copy it when writing Japanese.

The sentences are the simplest ones available: the app prefers the Tanaka
Corpus, the sentences from Japanese textbooks that Tatoeba also publishes, and
falls back to any short clean sentence when a kanji has no textbook one. A
handful of rare Jōyō characters appear in no everyday sentence at all; those
cards show a dictionary word instead, marked as such.

## Project layout

```
index.html                  markup for both the picker and the study view
css/styles.css              all styling, light and dark themes
js/app.js                   the whole app: state, rendering, keyboard
js/data/lists.js            generated: the 21 lists and their order
js/data/details-kana.js     generated: readings and notes for the kana
js/data/details-joyo.js     generated: data + examples for the Jōyō kanji
js/data/details-jlpt.js     generated: data + examples for the JLPT kanji
build-data.py               build tool: refreshes the four generated files
```

The files in `js/data/` are generated and committed, so the app never needs
Python to run. To rebuild them:

```sh
python3 build-data.py
```

The script downloads its sources into `.cache/` (git ignored), regenerates the
data files and fails loudly if the sources stop adding up — for example if the
Jōyō tables no longer contain exactly the 2136 expected characters.

Word spacing in the example sentences uses [janome](https://mecab.github.io/),
which is an optional build dependency:

```sh
pip install janome
```

Without it the build still works; the example sentences are then spaced less
precisely, splitting at every annotated run instead of at word boundaries. The
app itself never needs it.

## Licences

Code: MIT ([`LICENSE`](LICENSE)).

Kanji data: derived from KANJIDIC2 (EDRDG), Jonathan Waller's JLPT resources,
Wikipedia, the Kanji Kentei grade lists and JMdict, and therefore
[CC BY-SA 4.0](DATA-LICENSE.txt).

The example sentences come from Tatoeba and are
[CC BY 2.0 FR](DATA-LICENSE-CC-BY-2.0-FR.txt).

See [CREDITS.md](CREDITS.md) for the full attribution.
