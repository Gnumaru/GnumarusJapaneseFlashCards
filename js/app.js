/*
 * Kana and Kanji Flashcards - plain JavaScript, no dependencies.
 *
 * Study rules:
 *   - The current character is the only thing on the card; click it to reveal
 *     its data (meanings and readings for kanji, reading and notes for kana),
 *     click again to hide them.
 *   - Left arrow  -> move the current character to the end of the remaining list.
 *   - Right arrow -> take the current character out of the list (practiced).
 *   - The remaining characters can be shuffled, sorted back into the original
 *     order or reset to the full list at any time, and the list can be changed
 *     at any time from the picker in the top bar or from the "change list" button.
 */
(function () {
  'use strict';

  var STORAGE_PREFIX = 'kanji-flash-cards:v1:';
  var LAST_LIST_KEY = STORAGE_PREFIX + 'last';
  var DETAILS_SCRIPTS = {
    kana: 'js/data/details-kana.js',
    joyo: 'js/data/details-joyo.js',
    jlpt: 'js/data/details-jlpt.js'
  };
  var GROUP_LABELS = { kana: 'Kana', jlpt: 'JLPT', joyo: 'Jōyō' };
  var GROUP_ORDER = ['kana', 'jlpt', 'joyo'];

  // The four lines of the card, per group. A null value hides that line.
  var DETAIL_FIELDS = {
    joyo: [
      { label: 'Meanings', value: 'm' },
      { label: 'On\u2019yomi', value: 'on', kana: true },
      { label: 'Kun\u2019yomi', value: 'kun', kana: true },
      { label: 'Strokes', strokes: true }
    ],
    jlpt: [
      { label: 'Meanings', value: 'm' },
      { label: 'On\u2019yomi', value: 'on', kana: true },
      { label: 'Kun\u2019yomi', value: 'kun', kana: true },
      { label: 'Strokes', strokes: true }
    ],
    kana: [
      { label: 'Reading', value: 'r' },
      { label: 'Notes', value: 'm' },
      null,
      null
    ]
  };

  var lists = window.KANJI_LISTS || [];
  var details = window.KANJI_DETAILS || (window.KANJI_DETAILS = {});

  var el = {};
  var state = {
    list: null, // active entry of KANJI_LISTS
    order: [], // the list exactly as published (one entry per card)
    queue: [], // cards still to practice
    practiced: [], // cards already taken out of the queue
    revealed: false
  };

  /* ------------------------------------------------------------------ utils */

  function $(id) {
    return document.getElementById(id);
  }

  function plural(count, singular, many) {
    return count + ' ' + (count === 1 ? singular : many);
  }

  function unit() {
    return state.list && state.list.group === 'kana' ? 'kana' : 'kanji';
  }

  function shuffleInPlace(items) {
    for (var i = items.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var swap = items[i];
      items[i] = items[j];
      items[j] = swap;
    }
    return items;
  }

  /* ------------------------------------------------------------ data loading */

  function storage() {
    try {
      return window.localStorage;
    } catch (error) {
      return null; // private mode / disabled storage
    }
  }

  function ensureDetails(group) {
    if (details[group] || !DETAILS_SCRIPTS[group]) {
      return Promise.resolve(details[group]);
    }
    return new Promise(function (resolve, reject) {
      var script = document.createElement('script');
      script.src = DETAILS_SCRIPTS[group];
      script.onload = function () {
        resolve(details[group]);
      };
      script.onerror = function () {
        reject(new Error('Could not load ' + DETAILS_SCRIPTS[group]));
      };
      document.head.appendChild(script);
    });
  }

  /* -------------------------------------------------------------- persistence */

  function saveSession() {
    var store = storage();
    if (!store || !state.list) {
      return;
    }
    try {
      store.setItem(LAST_LIST_KEY, state.list.id);
      store.setItem(
        STORAGE_PREFIX + state.list.id,
        JSON.stringify({ q: state.queue, p: state.practiced })
      );
    } catch (error) {
      /* quota or disabled storage: progress is simply not remembered */
    }
  }

  function loadSession(list) {
    var store = storage();
    var raw = null;
    try {
      raw = store && store.getItem(STORAGE_PREFIX + list.id);
    } catch (error) {
      return null;
    }
    if (!raw) {
      return null;
    }
    try {
      var parsed = JSON.parse(raw);
      var queue = keepKnown(parsed.q, list);
      var practiced = keepKnown(parsed.p, list);
      if (!queue.length && !practiced.length) {
        return null;
      }
      return { queue: queue, practiced: practiced };
    } catch (error) {
      return null;
    }
  }

  function keepKnown(value, list) {
    if (!Array.isArray(value)) {
      return [];
    }
    var known = knownCharacters(list);
    return value.filter(function (item) {
      return typeof item === 'string' && known[item] === true;
    });
  }

  /* Looking a card up in the published list is O(n) with Array#indexOf, and the
     saved sessions of every list are validated when the picker opens, so the
     entries of each list are indexed once and kept around. */
  function knownCharacters(list) {
    if (!list.known) {
      list.known = {};
      for (var i = 0; i < list.kanjis.length; i++) {
        list.known[list.kanjis[i]] = true;
      }
    }
    return list.known;
  }

  /* -------------------------------------------------------------- list setup */

  function openList(list) {
    saveSession();
    state.list = list;
    state.order = list.kanjis.slice();
    var saved = loadSession(list);
    state.queue = saved ? saved.queue : state.order.slice();
    state.practiced = saved ? saved.practiced : [];
    state.revealed = false;
    showStudy();
    el.studyHint.textContent = list.hint;
    render();
    ensureDetails(list.group).then(function () {
      render();
    }, function (error) {
      el.studyHint.textContent = error.message;
    });
    // Move the keyboard focus into the study view without drawing a focus ring
    // around the card, so the arrow keys work right away.
    if (el.study.focus) {
      el.study.focus({ preventScroll: true });
    }
  }

  function showPicker() {
    saveSession();
    state.list = null;
    el.study.hidden = true;
    el.picker.hidden = false;
    markCurrentListInPicker();
    refreshPickerProgress();
    window.scrollTo(0, 0);
  }

  function showStudy() {
    el.picker.hidden = true;
    el.study.hidden = false;
  }

  /* ----------------------------------------------------------------- actions */

  function sendToEnd() {
    if (state.queue.length < 2) {
      return;
    }
    state.queue.push(state.queue.shift());
    state.revealed = false;
    render();
  }

  function markPracticed() {
    if (!state.queue.length) {
      return;
    }
    state.practiced.push(state.queue.shift());
    state.revealed = false;
    render();
  }

  function shuffleRemaining() {
    if (state.queue.length < 2) {
      return;
    }
    shuffleInPlace(state.queue);
    state.revealed = false;
    render();
  }

  function sortRemaining() {
    if (state.queue.length < 2) {
      return;
    }
    var positions = {};
    state.order.forEach(function (kanji, index) {
      positions[kanji] = index;
    });
    state.queue.sort(function (a, b) {
      return positions[a] - positions[b];
    });
    state.revealed = false;
    render();
  }

  function resetList() {
    state.queue = state.order.slice();
    state.practiced = [];
    state.revealed = false;
    render();
  }

  function reviewPracticed() {
    if (!state.practiced.length) {
      return;
    }
    state.queue = state.practiced.concat(state.queue);
    state.practiced = [];
    state.revealed = false;
    render();
  }

  function toggleDetails() {
    if (!state.queue.length) {
      return;
    }
    state.revealed = !state.revealed;
    render();
  }

  /* ------------------------------------------------------------------ render */

  function render() {
    if (!state.list) {
      return;
    }
    var list = state.list;
    var total = state.order.length;
    var current = state.queue[0] || null;
    var finished = !current;

    el.studyTitle.textContent = list.label;
    el.pickerSelect.value = list.id;
    var percent = total ? Math.round((state.practiced.length / total) * 100) : 0;
    el.progressFill.style.width = percent + '%';
    el.progressBar.setAttribute('aria-valuenow', String(percent));
    el.progressDone.textContent = plural(state.practiced.length, 'practiced', 'practiced');
    el.progressLeft.textContent = plural(state.queue.length, unit(), unit() + ' left');

    el.flashcard.disabled = finished;
    el.flashcard.hidden = finished;
    el.finished.hidden = !finished;

    if (finished) {
      el.cardKanji.textContent = '';
      el.cardDetails.hidden = true;
      el.flashcard.setAttribute('aria-expanded', 'false');
      el.finishedText.textContent = 'You practiced all ' + plural(total, unit(), unit()) + ' of ' + list.label + '.';
      el.finishedKanji.textContent = state.practiced.join(' ');
      el.reviewPracticed.disabled = !state.practiced.length;
    } else {
      el.cardKanji.textContent = current;
      renderDetails(current);
    }

    var left = state.queue.length;
    el.sendBack.disabled = left < 2;
    el.practice.disabled = !left;
    el.shuffle.disabled = left < 2;
    el.sort.disabled = left < 2;
    el.reset.disabled = left === total && !state.practiced.length;

    saveSession();
  }

  function renderDetails(kanji) {
    var entry = (details[state.list.group] || {})[kanji] || {};
    var fields = DETAIL_FIELDS[state.list.group] || DETAIL_FIELDS.joyo;

    // Kanji have an example sentence with furigana; kana do not have one.
    if (entry.ex) {
      el.exampleRow.hidden = false;
      // The example is pre-rendered ruby HTML built by build-data.py, so it is
      // inserted as markup rather than text. Every kanji, reading and space in
      // it comes from the Tatoeba / JMdict data files of this same origin.
      el.example.innerHTML = entry.w
        ? entry.ex + '<span class="example__note">' + (entry.w === 2 ? "word, no example sentence" : "word example") + '</span>'
        : entry.ex;
    } else {
      el.exampleRow.hidden = true;
      el.example.innerHTML = '';
    }

    for (var i = 0; i < 4; i++) {
      var field = fields[i];
      var row = el.detailRows[i];
      if (!field) {
        row.hidden = true;
        continue;
      }
      row.hidden = false;
      el.detailLabels[i].textContent = field.label;
      if (field.strokes) {
        el.detailValues[i].textContent = entry.s ? plural(entry.s, 'stroke', 'strokes') : '-';
      } else {
        el.detailValues[i].textContent = entry[field.value] || '-';
      }
      if (field.kana) {
        el.detailValues[i].classList.add('detail__value--kana');
      } else {
        el.detailValues[i].classList.remove('detail__value--kana');
      }
    }

    el.cardDetails.hidden = !state.revealed;
    el.flashcard.setAttribute('aria-expanded', state.revealed ? 'true' : 'false');
    el.flashcard.setAttribute(
      'aria-label',
      state.list.group === 'kana' ? characterName(kanji) : 'Kanji ' + kanji
    );
  }

  function characterName(kanji) {
    var entry = (details[state.list.group] || {})[kanji] || {};
    return 'Kana ' + kanji + (entry.r ? ', read ' + entry.r : '');
  }

  /* -------------------------------------------------------------- list picker */

  function buildPicker() {
    var targets = { kana: el.pickerKana, jlpt: el.pickerJlpt, joyo: el.pickerJoyo };
    var selectGroups = {};

    el.pickerSelect.innerHTML = '';
    Object.keys(targets).forEach(function (group) {
      targets[group].innerHTML = '';
      var selectGroup = document.createElement('optgroup');
      selectGroup.label = GROUP_LABELS[group];
      el.pickerSelect.appendChild(selectGroup);
      selectGroups[group] = selectGroup;
    });

    lists.forEach(function (list) {
      var item = document.createElement('li');
      var button = document.createElement('button');
      var label = document.createElement('span');
      var count = document.createElement('span');
      var option = document.createElement('option');

      button.type = 'button';
      button.className = 'picker__button';
      button.dataset.listId = list.id;
      button.setAttribute('aria-current', 'false');
      button.addEventListener('click', function () {
        openList(list);
      });

      label.className = 'picker__label';
      label.textContent = list.label;

      count.className = 'picker__count';
      count.dataset.listId = list.id;
      count.textContent = String(list.kanjis.length);

      button.appendChild(label);
      button.appendChild(count);
      item.appendChild(button);
      targets[list.group].appendChild(item);

      option.value = list.id;
      option.textContent = list.label;
      selectGroups[list.group].appendChild(option);
    });
  }

  function markCurrentListInPicker() {
    var buttons = el.picker.querySelectorAll('.picker__button');
    Array.prototype.forEach.call(buttons, function (button) {
      button.setAttribute('aria-current', state.list && button.dataset.listId === state.list.id ? 'true' : 'false');
    });
  }

  function refreshPickerProgress() {
    lists.forEach(function (list) {
      var node = el.picker.querySelector('.picker__count[data-list-id="' + list.id + '"]');
      if (!node) {
        return;
      }
      var saved = loadSession(list);
      var total = list.kanjis.length;
      if (!saved || saved.queue.length === total) {
        node.textContent = String(total);
        node.removeAttribute('data-progress');
        return;
      }
      node.textContent = saved.queue.length + ' / ' + total;
      node.setAttribute('data-progress', 'started');
    });
  }

  /* ----------------------------------------------------------------- keyboard */

  function isTypingTarget(target) {
    if (!target || !target.tagName) {
      return false;
    }
    var tag = target.tagName.toLowerCase();
    return tag === 'input' || tag === 'select' || tag === 'textarea' || target.isContentEditable;
  }

  function onKeyDown(event) {
    if (event.ctrlKey || event.metaKey || event.altKey || isTypingTarget(event.target)) {
      return;
    }
    var key = event.key;
    var handled = true;

    if (key === 'ArrowLeft') {
      sendToEnd();
    } else if (key === 'ArrowRight') {
      markPracticed();
    } else if (key === ' ' || key === 'Spacebar' || key === 'Enter') {
      // Let the focused control handle its own activation.
      if (document.activeElement !== el.flashcard && isActivatable(document.activeElement)) {
        return;
      }
      toggleDetails();
    } else if (key === 's' || key === 'S') {
      shuffleRemaining();
    } else if (key === 'o' || key === 'O') {
      sortRemaining();
    } else if (key === 'r' || key === 'R') {
      resetList();
    } else if (key === 'l' || key === 'L') {
      showPicker();
    } else {
      handled = false;
    }

    if (handled) {
      event.preventDefault();
    }
  }

  function isActivatable(node) {
    if (!node || !node.tagName) {
      return false;
    }
    var tag = node.tagName.toLowerCase();
    return tag === 'button' || tag === 'a' || tag === 'summary';
  }

  /* --------------------------------------------------------------------- init */

  function cacheElements() {
    el.picker = $('picker');
    el.pickerKana = $('picker-kana-list');
    el.pickerJlpt = $('picker-jlpt-list');
    el.pickerJoyo = $('picker-joyo-list');
    el.study = $('study');
    el.studyTitle = $('study-title');
    el.studyHint = $('study-hint');
    el.progressFill = $('progress-fill');
    el.progressBar = $('progress-bar');
    el.progressDone = $('progress-done');
    el.progressLeft = $('progress-left');
    el.flashcard = $('flashcard');
    el.cardKanji = $('card-kanji');
    el.cardDetails = $('card-details');
    el.detailRows = [$('detail-row-1'), $('detail-row-2'), $('detail-row-3'), $('detail-row-4')];
    el.detailLabels = [$('detail-label-1'), $('detail-label-2'), $('detail-label-3'), $('detail-label-4')];
    el.detailValues = [$('detail-value-1'), $('detail-value-2'), $('detail-value-3'), $('detail-value-4')];
    el.example = $('example');
    el.exampleRow = $('example-row');
    el.finished = $('finished');
    el.finishedText = $('finished-text');
    el.finishedKanji = $('finished-kanji');
    el.reviewPracticed = $('finished-review');
    el.sendBack = $('action-send-back');
    el.practice = $('action-practice');
    el.shuffle = $('action-shuffle');
    el.sort = $('action-sort');
    el.reset = $('action-reset');
    el.pickerSelect = $('list-picker');
    el.otherLists = $('action-other-lists');
  }

  function bind() {
    el.flashcard.addEventListener('click', toggleDetails);
    el.sendBack.addEventListener('click', sendToEnd);
    el.practice.addEventListener('click', markPracticed);
    el.shuffle.addEventListener('click', shuffleRemaining);
    el.sort.addEventListener('click', sortRemaining);
    el.reset.addEventListener('click', resetList);
    el.reviewPracticed.addEventListener('click', reviewPracticed);
    el.otherLists.addEventListener('click', showPicker);
    el.pickerSelect.addEventListener('change', function () {
      var chosen = findList(el.pickerSelect.value);
      if (chosen) {
        openList(chosen);
      }
    });
    document.addEventListener('keydown', onKeyDown);
    window.addEventListener('beforeunload', saveSession);
  }

  function findList(id) {
    for (var i = 0; i < lists.length; i++) {
      if (lists[i].id === id) {
        return lists[i];
      }
    }
    return null;
  }

  function start() {
    cacheElements();
    buildPicker();
    bind();
    if (!lists.length) {
      el.pickerJlpt.innerHTML = '<li>Kanji data could not be loaded.</li>';
      return;
    }
    var last = null;
    try {
      var store = storage();
      last = store && store.getItem(LAST_LIST_KEY);
    } catch (error) {
      last = null;
    }
    var list = findList(last);
    if (list) {
      openList(list);
    } else {
      showPicker();
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
