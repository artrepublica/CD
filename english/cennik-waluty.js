(function () {
  'use strict';
  const root = document.querySelector('.ar-currency');
  if (!root) return;
  const config = JSON.parse(document.getElementById('ar-currency-rates').textContent);
  const selector = root.querySelector('select');
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
    selector.value = code;
    note.textContent = code === 'PLN'
      ? 'Base prices in PLN. The final quote is agreed before work begins.'
      : 'Estimates in ' + code + ' · NBP average rates from ' + date + '. The final quote is agreed before work begins.';
    try { localStorage.setItem(storageKey, code); } catch (_) { /* Optional preference only. */ }
  }
  selector.addEventListener('change', function () { apply(selector.value); });
  apply(selected);
  root.hidden = false;
})();
