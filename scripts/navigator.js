(function () {
  'use strict';

  const rootURL = new URL('../', document.currentScript.src);
  const previewURL = new URL('retro-preview.html', rootURL);

  function addStars(header) {
    if (!header || header.querySelector('.ascii-star')) return;
    let field = header.querySelector('.ascii-starfield');
    if (!field) {
      field = document.createElement('div');
      field.className = 'ascii-starfield';
      field.setAttribute('aria-hidden', 'true');
      header.prepend(field);
    }
    const symbols = ['*', '+', '.', ':', 'x'];
    const stars = document.createDocumentFragment();
    for (let index = 0; index < 48; index++) {
      const star = document.createElement('span');
      const angle = index * Math.PI * 2 / 48;
      const duration = 4 + Math.random() * 4;
      star.className = 'ascii-star';
      star.textContent = symbols[index % symbols.length];
      star.style.setProperty('--star-x', (Math.cos(angle) * 100) + 'cqw');
      star.style.setProperty('--star-y', (Math.sin(angle) * 100) + 'cqh');
      star.style.setProperty('--flight-time', duration + 's');
      star.style.setProperty('--flight-delay', (-Math.random() * duration) + 's');
      stars.append(star);
    }
    field.append(stars);
  }

  function setupEffectVisibility() {
    const updateVisibility = () => document.body.classList.toggle('effects-inactive', document.hidden);
    document.addEventListener('visibilitychange', updateVisibility);
    updateVisibility();
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => entry.target.classList.toggle('effects-offscreen', !entry.isIntersecting));
    });
    document.querySelectorAll('.masthead, .navigator-badge').forEach(element => observer.observe(element));
  }

  async function loadStyles() {
    if (document.querySelector('link[data-navigator-style]')) return;
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = new URL('navigator.css', rootURL).href;
    link.dataset.navigatorStyle = '';
    await new Promise((resolve, reject) => {
      link.addEventListener('load', resolve, { once: true });
      link.addEventListener('error', () => reject(new Error('The browser theme stylesheet could not load.')), { once: true });
      document.head.append(link);
    });
  }

  async function loadTemplate() {
    const response = await fetch(previewURL);
    if (!response.ok) throw new Error('The browser shell returned HTTP ' + response.status + '.');
    const template = new DOMParser().parseFromString(await response.text(), 'text/html');
    if (!template.querySelector('.window .page .masthead') ||
        !template.querySelector('.directory-bar .browser-navigation .main-nav .whats-new') ||
        !template.querySelector('.social-links')) throw new Error('The browser shell template is incomplete.');
    return template;
  }

  function moveNavigation(navigation, directory) {
    navigation.querySelectorAll('a[href]').forEach(link => { link.href = link.href; });
    navigation.hidden = false;
    const current = directory.querySelector('.browser-navigation');
    if (current !== navigation) current.replaceWith(navigation);
  }

  function decoratePage(template) {
    const header = document.querySelector('.topbar');
    if (!header) return;
    const masthead = template.querySelector('.masthead').cloneNode(true);
    masthead.id = header.id;
    const nav = header.querySelector('.main-nav');
    const toggle = header.querySelector('.nav-toggle');
    const ticker = header.parentElement.querySelector(':scope > .ticker');
    header.replaceWith(masthead);
    addStars(masthead);
    if (nav) {
      nav.prepend(template.querySelector('.whats-new').cloneNode(true));
      const navigation = document.createElement('div');
      navigation.className = 'browser-navigation';
      if (toggle) navigation.append(toggle);
      navigation.append(nav);
      if (window.parent !== window) {
        navigation.hidden = true;
        masthead.after(navigation);
      } else {
        moveNavigation(navigation, document.querySelector('.directory-bar'));
      }
    }
    const socials = template.querySelector('.social-links').cloneNode(true);
    socials.classList.add('site-navigation');
    if (ticker) ticker.replaceWith(socials);
    else masthead.after(socials);
    document.dispatchEvent(new Event('navigator-ready'));
  }

  async function start() {
    if (window.parent !== window) {
      await loadStyles();
      const template = await loadTemplate();
      document.body.classList.add('navigator-embedded');
      decoratePage(template);
      setupEffectVisibility();
      return;
    }
    if (!document.querySelector('.window')) {
      await loadStyles();
      const template = await loadTemplate();
      const templateShell = template.querySelector('.window');
      if (!templateShell?.querySelector('.page')) throw new Error('The browser shell template is incomplete.');
      const shell = templateShell.cloneNode(true);
      const content = document.createElement('div');
      content.className = 'page';
      const source = document.querySelector('.site-shell');
      if (!source) throw new Error('This page has no site content container.');
      content.append(source);
      shell.querySelector('.page').replaceWith(content);
      shell.querySelectorAll('.menu-popup a, .directory-bar a').forEach(link => {
        if (!link.getAttribute('href').startsWith('#')) link.href = new URL(link.getAttribute('href'), rootURL).href;
      });
      document.body.prepend(shell);
      template.querySelectorAll('body > dialog').forEach(dialog => document.body.append(dialog.cloneNode(true)));
      document.body.classList.add('navigator-site');
      decoratePage(template);
    }
    setupBrowser();
    addStars(document.querySelector('.masthead'));
    setupEffectVisibility();
  }

  function setupBrowser() {
    const browserWindow = document.querySelector('.window');
    const menuBar = browserWindow.querySelector('.menu-bar');
    const menus = [...menuBar.querySelectorAll('details')];
    const dialog = document.querySelector('.browser-dialog');
    const inputDialog = document.querySelector('.input-dialog');
    const input = inputDialog.querySelector('input');
    const homePage = browserWindow.querySelector('.page');
    const frame = browserWindow.querySelector('.browser-page');
    const status = browserWindow.querySelector('.status-bar [role="status"]');
    const address = browserWindow.querySelector('.address');
    const initialURL = new URL(window.location.href);
    initialURL.hash = '';
    const pages = [initialURL.href];
    let pageIndex = 0;
    let pending = null;
    let inputAction = '';
    let query = '';
    let findOffset = 0;
    const originalTitle = document.title;
    const originalClasses = document.body.className;
    const directory = browserWindow.querySelector('.directory-bar');
    const originalNavigation = directory.querySelector('.browser-navigation');

    const buttons = action => browserWindow.querySelectorAll('[data-action="' + action + '"]');
    const contentDocument = () => frame.hidden ? document : frame.contentDocument;
    const contentRoot = () => frame.hidden ? homePage : frame.contentDocument.body;
    function pressed(action, value) { buttons(action).forEach(button => button.setAttribute('aria-pressed', String(value))); }
    function closeMenus() { menus.forEach(menu => { menu.open = false; }); }
    function updateWindowControls() {
      const minimized = browserWindow.classList.contains('is-minimized');
      const maximized = browserWindow.classList.contains('is-maximized');
      const maximize = browserWindow.querySelector('[data-action="maximize"]');
      maximize.setAttribute('aria-label', maximized && !minimized ? 'Restore window size' : 'Maximize window');
      maximize.title = maximized && !minimized ? 'Restore' : 'Maximize';
      maximize.setAttribute('aria-pressed', String(maximized && !minimized));
    }
    async function leaveFullscreen() {
      if (!document.fullscreenElement) return true;
      try {
        await document.exitFullscreen();
        return true;
      } catch (error) {
        message('Window Control Unavailable', error.message);
        return false;
      }
    }
    async function minimizeWindow() {
      if (!await leaveFullscreen()) return;
      browserWindow.classList.add('is-minimized');
      updateWindowControls();
    }
    function restoreMinimizedWindow() {
      browserWindow.classList.remove('is-minimized');
      updateWindowControls();
      browserWindow.querySelector('[data-action="minimize"]').focus();
    }
    async function maximizeWindow() {
      if (!await leaveFullscreen()) return;
      if (browserWindow.classList.contains('is-minimized')) {
        browserWindow.classList.remove('is-minimized');
        browserWindow.classList.add('is-maximized');
      } else {
        browserWindow.classList.toggle('is-maximized');
      }
      updateWindowControls();
    }
    function reboot() {
      if (pending) stop();
      const screen = document.createElement('div');
      screen.className = 'panic-screen';
      screen.setAttribute('role', 'alert');
      screen.tabIndex = -1;
      const content = document.createElement('div');
      content.className = 'panic-screen-content';
      const heading = document.createElement('p');
      heading.textContent = 'KERNEL PANIC';
      const detail = document.createElement('p');
      detail.textContent = 'Net Navigator has encountered a cosmic malfunction.';
      const progress = document.createElement('p');
      progress.textContent = 'System halted. Preparing reboot...';
      content.append(heading, detail, progress);
      screen.append(content);
      browserWindow.inert = true;
      browserWindow.classList.add('is-crashing');
      const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      const delay = reduced || document.body.classList.contains('effects-paused') ? 0 : 600;
      window.setTimeout(() => {
        document.body.append(screen);
        screen.focus();
      }, delay);
      window.setTimeout(() => { progress.textContent = 'Rebooting Net Navigator...'; }, 1900);
      window.setTimeout(() => {
        const target = new URL(pages[pageIndex]);
        const current = new URL(window.location.href);
        if (target.origin === current.origin && target.pathname === current.pathname && target.search === current.search) {
          window.location.hash = target.hash;
          window.location.reload();
        } else {
          window.location.assign(target.href);
        }
      }, 3200);
    }
    function message(title, text) {
      document.querySelector('#dialog-title').textContent = title;
      document.querySelector('#dialog-message').textContent = text;
      dialog.showModal();
    }
    function update() {
      buttons('back').forEach(button => { button.disabled = Boolean(pending) || pageIndex === 0; });
      buttons('forward').forEach(button => { button.disabled = Boolean(pending) || pageIndex === pages.length - 1; });
      buttons('stop').forEach(button => { button.disabled = !pending; });
      address.textContent = pages[pageIndex];
    }
    function applyOptions() {
      if (frame.hidden) return;
      const doc = frame.contentDocument;
      let style = doc.querySelector('#navigator-options');
      if (!style) {
        style = doc.createElement('style');
        style.id = 'navigator-options';
        doc.head.append(style);
      }
      style.textContent =
        (browserWindow.classList.contains('images-hidden') ? 'img { visibility: hidden !important; }' : '') +
        (document.body.classList.contains('effects-paused') ? '*, *::before, *::after { animation: none !important; } .ascii-starfield { display: none !important; }' : '');
    }
    function identity() {
      syncNavigation(contentDocument());
      if (!document.body.classList.contains('navigator-site')) return;
      const paused = document.body.classList.contains('effects-paused');
      const inactive = document.hidden;
      const classes = frame.hidden ? originalClasses : frame.contentDocument.body.className;
      document.body.className = classes.replace('navigator-embedded', 'navigator-site');
      document.body.classList.add('navigator-site');
      document.body.classList.toggle('effects-paused', paused);
      document.body.classList.toggle('effects-inactive', inactive);
      document.title = frame.hidden ? originalTitle : frame.contentDocument.title;
    }
    function syncNavigation(doc) {
      if (doc !== contentDocument()) return;
      const navigation = doc === document ? originalNavigation : doc.querySelector('.browser-navigation');
      if (navigation?.querySelector('.main-nav')) moveNavigation(navigation, directory);
    }
    function commit(navigation) {
      if (navigation.index === undefined) {
        if (navigation.url !== pages[pageIndex]) {
          pages.splice(pageIndex + 1);
          pages.push(navigation.url);
          pageIndex++;
        }
      } else {
        pageIndex = navigation.index;
        pages[pageIndex] = navigation.url;
      }
      pending = null;
      findOffset = 0;
      identity();
      status.textContent = 'Done.';
      update();
    }
    function stop() {
      if (!pending) return;
      pending.controller.abort();
      pending = null;
      frame.contentWindow.stop();
      frame.hidden = pages[pageIndex] === initialURL.href;
      homePage.hidden = !frame.hidden;
      if (!frame.hidden) frame.src = pages[pageIndex];
      status.textContent = 'Loading stopped.';
      update();
    }
    function showInitial(navigation) {
      frame.hidden = true;
      frame.src = 'about:blank';
      homePage.hidden = false;
      commit(navigation);
      homePage.scrollIntoView({ block: 'start' });
    }
    async function navigate(rawURL, index) {
      let url;
      try {
        url = new URL(rawURL, pages[pageIndex]);
        if (!['http:', 'https:'].includes(url.protocol) || url.origin !== initialURL.origin || url.username || url.password) {
          throw new Error('Only pages on this site can open inside Net Navigator. Use an HTTP preview server when testing files.');
        }
      } catch (error) {
        message('Cannot Open Location', error.message);
        return;
      }
      if (pending) stop();
      const navigation = { url: url.href, index, controller: new AbortController() };
      if (url.href === initialURL.href || url.href === initialURL.href + '#top') {
        navigation.url = initialURL.href;
        showInitial(navigation);
        return;
      }
      pending = navigation;
      status.textContent = 'Loading ' + url.pathname + '...';
      update();
      try {
        const response = await fetch(url, { method: 'HEAD', signal: navigation.controller.signal });
        if (!response.ok) throw new Error('The page returned HTTP ' + response.status + '.');
        if (new URL(response.url).origin !== initialURL.origin) throw new Error('This page redirects outside the site.');
        if (!response.headers.get('content-type')?.includes('text/html')) throw new Error('This location is not an HTML page.');
        if (pending !== navigation) return;
        const destination = new URL(response.url);
        destination.hash = url.hash;
        navigation.url = destination.href;
        frame.src = navigation.url;
      } catch (error) {
        if (pending !== navigation) return;
        pending = null;
        status.textContent = 'Page could not be loaded.';
        update();
        message('Cannot Open Location', error.message);
      }
    }
    function linkClick(event) {
      const link = event.target.closest('a[href]');
      if (!link || event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey ||
          event.shiftKey || event.altKey || link.hasAttribute('download') || link.target === '_blank') return;
      const url = new URL(link.href);
      if (!['http:', 'https:', 'file:'].includes(url.protocol)) return;
      if (url.origin !== initialURL.origin) {
        if (link.ownerDocument !== document && (!link.target || link.target === '_self')) {
          event.preventDefault();
          window.location.assign(url.href);
        }
        return;
      }
      if (link.getAttribute('href').startsWith('#')) return;
      event.preventDefault();
      navigate(url.href);
    }
    function connectFrame() {
      const doc = frame.contentDocument;
      doc.addEventListener('click', closeMenus);
      doc.addEventListener('click', linkClick);
      doc.addEventListener('navigator-ready', () => syncNavigation(doc));
      syncNavigation(doc);
      applyOptions();
    }
    frame.addEventListener('load', async () => {
      try {
        if (!pending) {
          if (!frame.hidden && frame.contentWindow.location.href === pages[pageIndex]) connectFrame();
          return;
        }
        const navigation = pending;
        if (frame.contentWindow.location.href !== navigation.url) return;
        frame.hidden = false;
        homePage.hidden = true;
        connectFrame();
        commit(navigation);
      } catch (error) {
        stop();
        status.textContent = 'Embedded page access was blocked.';
        message('Page Unavailable', error.message);
      }
    });
    homePage.addEventListener('click', linkClick);
    menuBar.addEventListener('click', linkClick);
    directory.addEventListener('click', linkClick);

    function openInput(action) {
      inputAction = action;
      document.querySelector('#input-title').textContent = action === 'open' ? 'Open Location' : 'Find in Page';
      document.querySelector('#input-label').textContent = action === 'open' ? 'Location:' : 'Find text:';
      document.querySelector('#input-hint').textContent = action === 'open' ?
        'Enter a site URL or relative page path. Navigation stays inside this frame.' :
        'Search the current page. Find Again wraps to the beginning.';
      input.value = action === 'open' ? pages[pageIndex] : query;
      inputDialog.showModal();
      input.select();
    }
    function find() {
      const doc = contentDocument();
      const walker = doc.createTreeWalker(contentRoot(), NodeFilter.SHOW_TEXT, {
        acceptNode(node) {
          return node.parentElement.closest('script, style, noscript, [hidden], [aria-hidden="true"]') ?
            NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT;
        }
      });
      const nodes = [];
      let text = '';
      while (walker.nextNode()) {
        nodes.push({ node: walker.currentNode, start: text.length });
        text += walker.currentNode.textContent;
      }
      let match = text.toLowerCase().indexOf(query.toLowerCase(), findOffset);
      if (match < 0) match = text.toLowerCase().indexOf(query.toLowerCase());
      if (match < 0) { status.textContent = 'Text not found: "' + query + '".'; return; }
      const start = nodes.find(entry => entry.start + entry.node.length > match);
      const end = nodes.find(entry => entry.start + entry.node.length >= match + query.length);
      const range = doc.createRange();
      range.setStart(start.node, match - start.start);
      range.setEnd(end.node, match + query.length - end.start);
      const selection = doc.defaultView.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
      start.node.parentElement.scrollIntoView({ block: 'center' });
      findOffset = match + query.length;
      status.textContent = 'Found: "' + query + '".';
    }
    inputDialog.querySelector('[data-dismiss]').addEventListener('click', () => inputDialog.close());
    input.addEventListener('input', () => input.setCustomValidity(''));
    inputDialog.querySelector('form').addEventListener('submit', event => {
      event.preventDefault();
      const value = input.value.trim();
      if (!value) { input.setCustomValidity('Enter a location or search text.'); input.reportValidity(); return; }
      inputDialog.close();
      if (inputAction === 'open') navigate(value);
      else { query = value; findOffset = 0; buttons('find-again').forEach(button => { button.disabled = false; }); find(); }
    });
    function positionMenu(menu) {
      const popup = menu.querySelector('.menu-popup');
      const bounds = menu.getBoundingClientRect();
      popup.style.left = (Math.max(8, Math.min(bounds.left, innerWidth - popup.offsetWidth - 8)) - bounds.left) + 'px';
      popup.style.right = 'auto';
    }
    menus.forEach(menu => menu.addEventListener('toggle', () => {
      if (menu.open) { menus.filter(other => other !== menu).forEach(other => { other.open = false; }); positionMenu(menu); }
    }));
    window.addEventListener('resize', () => menus.filter(menu => menu.open).forEach(positionMenu));
    document.addEventListener('click', event => { if (!menuBar.contains(event.target)) closeMenus(); });
    browserWindow.querySelector('.title-bar').addEventListener('dblclick', event => {
      if (event.target.closest('button')) return;
      if (browserWindow.classList.contains('is-minimized')) restoreMinimizedWindow();
      else maximizeWindow();
    });
    menuBar.addEventListener('keydown', event => {
      const menu = event.target.closest('details');
      if (!menu) return;
      const items = [...menu.querySelectorAll('button:not(:disabled), a')];
      if (event.key === 'Escape') { closeMenus(); menu.querySelector('summary').focus(); event.preventDefault(); }
      else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        menu.open = true;
        const index = items.indexOf(event.target);
        const next = event.key === 'ArrowDown' ? index + 1 : index < 0 ? items.length - 1 : index - 1;
        items[(next + items.length) % items.length]?.focus();
      } else if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
        event.preventDefault();
        const next = menus[(menus.indexOf(menu) + (event.key === 'ArrowRight' ? 1 : -1) + menus.length) % menus.length];
        closeMenus(); next.open = true; next.querySelector('summary').focus();
      }
    });
    browserWindow.addEventListener('click', async event => {
      const item = event.target.closest('button[data-action], button[data-toggle], .menu-popup a');
      if (!item || item.disabled) return;
      item.closest('details')?.querySelector('summary').focus();
      closeMenus();
      if (item.dataset.toggle) {
        const bar = browserWindow.querySelector('.' + item.dataset.toggle);
        bar.hidden = !bar.hidden;
        item.setAttribute('aria-pressed', String(!bar.hidden));
      }
      switch (item.dataset.action) {
        case 'minimize': await minimizeWindow(); break;
        case 'restore-minimized': restoreMinimizedWindow(); break;
        case 'maximize': await maximizeWindow(); break;
        case 'exit': if (await leaveFullscreen()) reboot(); break;
        case 'back': navigate(pages[pageIndex - 1], pageIndex - 1); break;
        case 'forward': navigate(pages[pageIndex + 1], pageIndex + 1); break;
        case 'home':
          if (pending) stop();
          if (initialURL.href === previewURL.href) showInitial({ url: initialURL.href });
          else navigate(new URL('index.html', rootURL).href);
          break;
        case 'open': case 'find': openInput(item.dataset.action); break;
        case 'find-again': find(); break;
        case 'stop': stop(); break;
        case 'print': contentDocument().defaultView.print(); break;
        case 'reload':
          if (frame.hidden) { status.textContent = 'Done.'; homePage.scrollIntoView({ block: 'start' }); }
          else navigate(pages[pageIndex], pageIndex);
          break;
        case 'select-all': {
          const range = contentDocument().createRange();
          range.selectNodeContents(contentRoot());
          const selection = contentDocument().defaultView.getSelection();
          selection.removeAllRanges(); selection.addRange(range); break;
        }
        case 'images': pressed('images', !browserWindow.classList.toggle('images-hidden')); applyOptions(); break;
        case 'effects': pressed('effects', !document.body.classList.toggle('effects-paused')); applyOptions(); break;
        case 'fullscreen':
          try {
            if (document.fullscreenElement) await document.exitFullscreen();
            else await browserWindow.requestFullscreen();
          } catch (error) { message('Full Screen Unavailable', error.message); }
          break;
        case 'help': message('Navigator Handbook', 'Browse site pages inside the frame with Back/Forward, Home, and Open. External sources use normal links. Find searches the current page; Images toggles pictures; Stop cancels loading. Digital Effects controls the background, stars, and globe. Arrow keys navigate menus; Escape closes them. Gray commands are unavailable. History and options last for this visit.'); break;
        case 'about': message('About Net Navigator', 'AlienCultist Net Navigator is an independent, nostalgic browser-themed website, not a real browser or a Netscape product. Each section retains its own palette, content, and archive tools.'); break;
      }
    });
    const fullscreenItem = menuBar.querySelector('[data-action="fullscreen"]');
    fullscreenItem.disabled = !document.fullscreenEnabled;
    document.addEventListener('fullscreenchange', () => pressed('fullscreen', document.fullscreenElement === browserWindow));
    update();
  }

  start().catch(error => {
    console.error('Net Navigator could not start:', error);
    const alert = document.createElement('p');
    alert.setAttribute('role', 'alert');
    alert.textContent = 'The browser theme could not load. The original page remains available. ' + error.message;
    document.body.prepend(alert);
  });
}());
