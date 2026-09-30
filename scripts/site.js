/*
  Alien Cultist Labs — shared client-side behaviour.

  Plain browser JavaScript, no frameworks and no build step. Every feature in
  here is progressive: if this file fails to load the site still works, it just
  loses the filter box, the back-to-top button and the mobile menu toggle.
*/
(function () {
  'use strict';

  var doc = document;

  /* Small helpers so the rest of the file reads cleanly. */
  function make(tag, className, text) {
    var el = doc.createElement(tag);
    if (className) { el.className = className; }
    if (text) { el.textContent = text; }
    return el;
  }

  function onReady(fn) {
    if (doc.readyState === 'loading') {
      doc.addEventListener('DOMContentLoaded', fn);
    } else {
      fn();
    }
  }

  /* ------------------------------------------------------------------
     Skip link: lets keyboard and screen-reader visitors jump past the
     navigation straight to the page content.
     ------------------------------------------------------------------ */
  function addSkipLink() {
    if (doc.querySelector('.skip-link')) { return; }

    var main = doc.querySelector('main');
    if (!main) { return; }

    if (!main.id) { main.id = 'main-content'; }

    var link = make('a', 'skip-link', 'SKIP TO CONTENT');
    link.href = '#' + main.id;
    doc.body.insertBefore(link, doc.body.firstChild);
  }

  /* ------------------------------------------------------------------
     Mobile navigation toggle. The nav is a wrapping flex row, which gets
     cramped on small screens, so below 800px we collapse it behind a
     button instead of letting it eat the whole viewport.
     ------------------------------------------------------------------ */
  function setupNavToggle() {
    var nav = doc.querySelector('.main-nav');
    var bar = doc.querySelector('.topbar');
    if (!nav || !bar || doc.querySelector('.nav-toggle')) { return; }

    if (!nav.id) { nav.id = 'main-nav'; }

    var toggle = make('button', 'nav-toggle');
    toggle.type = 'button';
    toggle.setAttribute('aria-expanded', 'false');
    toggle.setAttribute('aria-controls', nav.id);
    toggle.innerHTML = '<span class="nav-toggle-bars" aria-hidden="true"></span><span class="nav-toggle-text">MENU</span>';

    toggle.addEventListener('click', function () {
      var open = nav.classList.toggle('is-open');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      toggle.querySelector('.nav-toggle-text').textContent = open ? 'CLOSE' : 'MENU';
    });

    bar.insertBefore(toggle, nav);

    /* Closing on link click keeps the menu from covering the destination. */
    nav.addEventListener('click', function (event) {
      if (event.target.closest('a') && nav.classList.contains('is-open')) {
        nav.classList.remove('is-open');
        toggle.setAttribute('aria-expanded', 'false');
        toggle.querySelector('.nav-toggle-text').textContent = 'MENU';
      }
    });
  }

  /* ------------------------------------------------------------------
     Back-to-top button. The archive pages are long; this saves a lot of
     scrolling. It only appears once you are well down the page.
     ------------------------------------------------------------------ */
  function setupBackToTop() {
    if (doc.querySelector('.to-top')) { return; }

    var button = make('button', 'to-top');
    button.type = 'button';
    button.setAttribute('aria-label', 'Back to top');
    button.innerHTML = '<span aria-hidden="true">↑</span>';

    button.addEventListener('click', function () {
      var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      window.scrollTo({ top: 0, behavior: reduce ? 'auto' : 'smooth' });
    });

    doc.body.appendChild(button);

    var ticking = false;
    function update() {
      button.classList.toggle('is-visible', window.scrollY > 600);
      ticking = false;
    }

    window.addEventListener('scroll', function () {
      if (!ticking) {
        ticking = true;
        window.requestAnimationFrame(update);
      }
    }, { passive: true });

    update();
  }

  /* ------------------------------------------------------------------
     Archive filter. The hardware and Area 42 catalogues run to thousands
     of records, so scanning them by eye is painful. This adds a live
     filter box above the first large card grid on the page.
     ------------------------------------------------------------------ */

  /* Grids we know how to filter, paired with the card inside them. */
  var GRIDS = [
    { grid: '.hardware-grid', card: '.hardware-card', noun: 'categories', hint: 'Try a broader word, like "storage" or "audio".' },
    { grid: '.component-grid', card: '.component-card', noun: 'records', hint: 'Try fewer words, or part of a model number.' },
    { grid: '.area42-category-grid', card: '.area42-category-card', noun: 'categories', hint: 'Try a broader word, like "medicine" or "politics".' },
    { grid: '.area42-dossier-grid', card: '.area42-dossier-card', noun: 'dossiers', hint: 'Try fewer words, or a name, place, or year.' }
  ];

  /* Below this many cards a filter box is more clutter than help. */
  var MIN_CARDS = 8;

  function normalise(value) {
    return value.toLowerCase().replace(/\s+/g, ' ').trim();
  }

  function setupFilter() {
    var target = null;

    for (var i = 0; i < GRIDS.length && !target; i++) {
      var grid = doc.querySelector(GRIDS[i].grid);
      if (!grid) { continue; }

      var cards = grid.querySelectorAll(GRIDS[i].card);
      if (cards.length >= MIN_CARDS) {
        target = { grid: grid, cards: cards, noun: GRIDS[i].noun, hint: GRIDS[i].hint };
      }
    }

    if (!target) { return; }

    /* Cache each card's searchable text once instead of on every keystroke. */
    var entries = [];
    Array.prototype.forEach.call(target.cards, function (card) {
      entries.push({ el: card, text: normalise(card.textContent || '') });
    });

    var total = entries.length;

    var panel = make('div', 'archive-filter');

    var label = make('label', 'archive-filter-label', 'FILTER THE ARCHIVE');
    label.htmlFor = 'archive-filter-input';

    var field = make('div', 'archive-filter-field');

    var prompt = make('span', 'prompt', 'ACLAB:~$');
    prompt.setAttribute('aria-hidden', 'true');

    var input = doc.createElement('input');
    input.type = 'search';
    input.id = 'archive-filter-input';
    input.className = 'archive-filter-input';
    input.setAttribute('autocomplete', 'off');
    input.placeholder = 'type to narrow ' + total + ' ' + target.noun + '…';

    var clear = make('button', 'archive-filter-clear', 'CLEAR');
    clear.type = 'button';
    clear.hidden = true;

    field.appendChild(prompt);
    field.appendChild(input);
    field.appendChild(clear);

    /* aria-live lets screen readers hear the result count change. */
    var count = make('p', 'archive-filter-count');
    count.setAttribute('role', 'status');
    count.setAttribute('aria-live', 'polite');
    count.textContent = 'SHOWING ALL ' + total + ' ' + target.noun.toUpperCase();

    var empty = make('p', 'archive-filter-empty', 'Nothing matched that search. ' + target.hint);
    empty.hidden = true;

    panel.appendChild(label);
    panel.appendChild(field);
    panel.appendChild(count);

    target.grid.parentNode.insertBefore(panel, target.grid);
    target.grid.parentNode.insertBefore(empty, target.grid.nextSibling);

    function apply() {
      var query = normalise(input.value);
      clear.hidden = query === '';

      if (!query) {
        entries.forEach(function (entry) { entry.el.hidden = false; });
        count.textContent = 'SHOWING ALL ' + total + ' ' + target.noun.toUpperCase();
        empty.hidden = true;
        return;
      }

      /* Every word must appear somewhere in the card, in any order. */
      var words = query.split(' ');
      var shown = 0;

      entries.forEach(function (entry) {
        var match = words.every(function (word) {
          return entry.text.indexOf(word) !== -1;
        });
        entry.el.hidden = !match;
        if (match) { shown++; }
      });

      count.textContent = shown + ' OF ' + total + ' ' + target.noun.toUpperCase() + ' MATCH';
      empty.hidden = shown !== 0;
    }

    /* Keep typing responsive on the very large catalogue pages. */
    var timer = null;
    input.addEventListener('input', function () {
      window.clearTimeout(timer);
      timer = window.setTimeout(apply, 120);
    });

    input.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') {
        input.value = '';
        apply();
      }
    });

    clear.addEventListener('click', function () {
      input.value = '';
      apply();
      input.focus();
    });
  }

  onReady(function () {
    addSkipLink();
    setupNavToggle();
    setupBackToTop();
    setupFilter();
  });
}());
