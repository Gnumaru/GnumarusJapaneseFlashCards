/*
 * Kanji Flashcards - plain JavaScript, no dependencies.
 *
 * Study rules:
 *   - The current kanji is the only thing on the card; click it to reveal its
 *     meanings and readings, click again to hide them.
 *   - Left arrow  -> move the current kanji to the end of the remaining list.
 *   - Right arrow -> take the current kanji out of the list (practiced).
 *   - The remaining kanji can be shuffled, sorted back into the original order
 *     or reset to the full list at any time, and the list can be changed at any
 *     time from the picker in the top bar or from the "other lists" button.
 */
(function () {
  'use strict';

  var STORAGE_PREFIX = 'kanji-flash-cards:v1:';
  var LAST_LIST_KEY = STORAGE_PREFIX + 'last';
  var DETAILS_SCRIPTS = { joyo: 'js/data/details-joyo.js', jlpt: 'js/data/details-jlpt.js' };
  var GROUP_LABELS = { jlpt: 'JLPT', joyo: 'Jōyō' };
  var GROUP_ORDER = ['jlpt', 'joyo'];

  var lists = window.KANJI_LISTS || [];
  var details = window.KANJI_DETAILS || (window.KANJI_DETAILS = {});

  var el = {};
  var state = {
    list: null, // active entry of KANJI_LISTS
    order: [], // the list exactly as published
    queue: [], // kanji still to practice
    practiced: [], // kanji already taken out of the queue
    revealed: false
  };

  /* ------------------------------------------------------------------ utils */

  function $(id) {
    return document.getElementById(id);
  }

  function plural(count, singular, many) {
    return count + ' ' + (count === 1 ? singular : many);
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
        JSON.stringify({ q: state.queue.join(''), p: state.practiced.join('') })
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
    if (typeof value !== 'string') {
      return [];
    }
    var known = knownCharacters(list);
    return value.split('').filter(function (kanji) {
      return known[kanji] === true;
    });
  }

  /* Looking a kanji up in the published list is O(n) with String#indexOf, and
     the saved sessions of every list are validated when the picker opens, so
     the characters of each list are indexed once and kept around. */
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
    state.order = list.kanjis.split('');
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
    el.progressLeft.textContent = plural(state.queue.length, 'kanji left', 'kanji left');

    el.flashcard.disabled = finished;
    el.flashcard.hidden = finished;
    el.finished.hidden = !finished;

    if (finished) {
      el.cardKanji.textContent = '';
      el.cardDetails.hidden = true;
      el.flashcard.setAttribute('aria-expanded', 'false');
      el.finishedText.textContent = 'You practiced all ' + plural(total, 'kanji', 'kanji') + ' of ' + list.label + '.';
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
    el.detailMeanings.textContent = entry.m || 'no meaning listed';
    el.detailOnyomi.textContent = entry.on || '-';
    el.detailKunyomi.textContent = entry.kun || '-';
    el.detailStrokes.textContent = entry.s ? plural(entry.s, 'stroke', 'strokes') : '-';
    el.detailOnyomi.setAttribute('data-kana', 'true');
    el.detailKunyomi.setAttribute('data-kana', 'true');

    el.cardDetails.hidden = !state.revealed;
    el.flashcard.setAttribute('aria-expanded', state.revealed ? 'true' : 'false');
    el.flashcard.setAttribute(
      'aria-label',
      'Kanji ' + kanji + '. ' + (state.revealed ? 'Hide' : 'Show') + ' its meanings and readings.'
    );
  }

  /* -------------------------------------------------------------- list picker */

  function buildPicker() {
    var targets = { jlpt: el.pickerJlpt, joyo: el.pickerJoyo };
    var selectGroups = {};

    el.pickerSelect.innerHTML = '';
    el.pickerJlpt.innerHTML = '';
    el.pickerJoyo.innerHTML = '';

    GROUP_ORDER.forEach(function (group) {
      var selectGroup = document.createElement('optgroup');
      selectGroup.label = GROUP_LABELS[group];
      el.pickerSelect.appendChild(selectGroup);
      selectGroups[group] = selectGroup;
      targets[group].innerHTML = '';
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
    el.detailMeanings = $('detail-meanings');
    el.detailOnyomi = $('detail-onyomi');
    el.detailKunyomi = $('detail-kunyomi');
    el.detailStrokes = $('detail-strokes');
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
