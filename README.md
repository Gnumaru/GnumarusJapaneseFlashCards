# GnumarusJapaneseFlashCards

A flashcard trainer for Japanese kanji, built with plain HTML, CSS and
JavaScript. There are no dependencies, no build step and no network calls at
runtime: open `index.html` in a browser and it works, straight from `file://` or
from a web server.

## Lists

* **JLPT N5 → N1** (79, 166, 367, 367 and 1232 kanji), ordered from the most
  frequent kanji to the least frequent.
* **Jōyō grades 1 → 12** (all 2136 Jōyō kanji), ordered the way the official
  常用漢字表 is: grade 1 starts with 一右雨円王音下… See
  [CREDITS.md](CREDITS.md) for how the school years are derived.

Pick a list, and the cards come up one after another in the order of that list.

## How to study

| Action | Result |
| --- | --- |
| Click the kanji (or `Space` / `Enter`) | Show or hide its meanings, on'yomi, kun'yomi and stroke count |
| `←` | Move the current kanji to the end of the list, to study it again later |
| `→` | Take the current kanji out of the list (it counts as practiced) |
| `S` | Shuffle the kanji that are left |
| `O` | Sort the kanji that are left back into the original order of the list |
| `R` | Reset the list, so practiced kanji come back |
| `L` | Go back to the list picker |

The same actions are available as buttons under the card, and the list can be
changed at any moment from the picker in the top bar or from **Change list**.
When every kanji of a list has been practiced, the app shows them and offers to
practice exactly those again.

Progress is kept per list in the browser's `localStorage`, so reloading or
switching lists does not lose your place. Nothing is sent anywhere.

## Project layout

```
index.html                  markup for both the picker and the study view
css/styles.css              all styling, light and dark themes
js/app.js                   the whole app: state, rendering, keyboard
js/data/lists.js            generated: the 17 lists and their kanji order
js/data/details-joyo.js     generated: readings/meanings for the Jōyō kanji
js/data/details-jlpt.js     generated: readings/meanings for the JLPT kanji
build-data.py               build tool: refreshes the three generated files
```

The files in `js/data/` are generated and committed, so the app never needs
Python to run. To rebuild them:

```sh
python3 build-data.py
```

The script downloads its sources into `.cache/` (git ignored), regenerates the
data files and fails loudly if the sources stop adding up — for example if the
Jōyō tables no longer contain exactly the 2136 expected characters.

## Licences

Code: MIT ([`LICENSE`](LICENSE)).

Kanji data: derived from KANJIDIC2 (EDRDG), Jonathan Waller's JLPT resources,
Wikipedia and the Kanji Kentei grade lists, and therefore
[CC BY-SA 4.0](DATA-LICENSE.txt) — see [CREDITS.md](CREDITS.md).
