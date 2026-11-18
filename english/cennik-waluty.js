(function () {
  'use strict';
  const root = document.querySelector('.ar-currency');
  if (!root) return;
  const config = JSON.parse(document.getElementById('ar-currency-rates').textContent);
  const selector = root.querySelector('#ar-currency-select');
  const value = root.querySelector('#ar-currency-value');
  const menu = root.querySelector('#ar-currency-menu');
  const options = Array.from(menu.querySelectorAll('[data-currency]'));
  let currentCode;
  const note = root.querySelector('[data-currency-note]');
  const entries = Array.from(document.querySelectorAll('[data-pln-min]')).map(function (el) {
    return { el: el, original: el.textContent, min: Number(el.dataset.plnMin), max: el.dataset.plnMax ? Number(el.dataset.plnMax) : null };
  });
  const allowed = ['PLN', 'EUR', 'USD', 'GBP'];
  const storageKey = 'artrepublica.soundstudio.currency';
  const date = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(new Date(config.effective_date + 'T12:00:00Z'));
  let selected = config.default_currency;
  try {
    const saved = localStorage.getItem(storageKey);
    if (allowed.includes(saved)) selected = saved;
  } catch (_) { /* The selector also works when browser storage is unavailable. */ }

  function apply(code) {
    if (!allowed.includes(code)) code = 'PLN';
    const rate = config.pln_per_unit[code];
    const format = new Intl.NumberFormat('en-GB', {
      style: 'currency', currency: code, currencyDisplay: 'symbol',
      minimumFractionDigits: 2, maximumFractionDigits: 2
    });
    entries.forEach(function (entry) {
      if (code === 'PLN') {
        entry.el.textContent = entry.original;
      } else {
        const low = format.format(entry.min / rate);
        const high = entry.max === null ? '' : '–' + format.format(entry.max / rate);
        entry.el.textContent = '≈ ' + low + high;
      }
    });
    currentCode = code;
    options.forEach(function (option) {
      const active = option.dataset.currency === code;
      option.setAttribute('aria-checked', String(active));
      if (active) value.textContent = option.textContent;
    });
    note.textContent = code === 'PLN'
      ? 'Base prices in PLN. The final quote is agreed before work begins.'
      : 'Estimates in ' + code + ' · NBP average rates from ' + date + '. The final quote is agreed before work begins.';
    try { localStorage.setItem(storageKey, code); } catch (_) { /* Optional preference only. */ }
  }
  function close(restoreFocus) {
    menu.hidden = true;
    selector.setAttribute('aria-expanded', 'false');
    if (restoreFocus) selector.focus();
  }
  function open(index) {
    menu.hidden = false;
    selector.setAttribute('aria-expanded', 'true');
    const selectedIndex = options.findIndex(function (option) { return option.dataset.currency === currentCode; });
    options[index === undefined ? selectedIndex : index].focus();
  }
  selector.addEventListener('click', function () {
    if (menu.hidden) open(); else close(false);
  });
  selector.addEventListener('keydown', function (event) {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      open(event.key === 'ArrowDown' ? 0 : options.length - 1);
    } else if (event.key === 'Escape') close(false);
  });
  options.forEach(function (option, index) {
    option.addEventListener('click', function () {
      apply(option.dataset.currency);
      close(true);
    });
    option.addEventListener('keydown', function (event) {
      let target;
      if (event.key === 'ArrowDown') target = (index + 1) % options.length;
      else if (event.key === 'ArrowUp') target = (index + options.length - 1) % options.length;
      else if (event.key === 'Home') target = 0;
      else if (event.key === 'End') target = options.length - 1;
      else if (event.key.length === 1) {
        const match = options.findIndex(function (item) { return item.dataset.currency[0].toLowerCase() === event.key.toLowerCase(); });
        if (match !== -1) target = match;
      }
      if (target !== undefined) {
        event.preventDefault();
        options[target].focus();
      } else if (event.key === 'Escape') {
        event.preventDefault();
        event.stopPropagation();
        close(true);
      } else if (event.key === 'Tab') close(false);
    });
  });
  document.addEventListener('click', function (event) {
    if (!root.contains(event.target)) close(false);
  });
  root.addEventListener('focusout', function (event) {
    if (!root.contains(event.relatedTarget)) close(false);
  });
  apply(selected);
  root.hidden = false;
})();
