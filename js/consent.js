(function () {
  'use strict';
  if (window.arConsentLoaded) return;
  window.arConsentLoaded = true;
  var key = 'ar-consent-v2';
  var lifetime = 180 * 24 * 60 * 60 * 1000;
  var choice = null;
  var panel, reopen, analytics, ads, status;
  var en = document.documentElement.lang.toLowerCase().indexOf('en') === 0;
  var labels = en ? {
    title: 'Privacy settings',
    text: 'With your permission, we use Google Analytics to measure visits and Google advertising features for advertising and personalisation. Without consent, Google may receive limited cookieless signals. Your choice is saved on this device for 180 days. You can change it at any time using Privacy settings.',
    analytics: 'Analytics — measuring visits with Google Analytics',
    ads: 'Advertising — advertising data and personalised ads',
    accept: 'Accept all', reject: 'Reject optional', settings: 'Choose settings',
    save: 'Save choices', reopen: 'Privacy settings',
    storage: 'Your browser could not save this choice. It applies to this page only.'
  } : {
    title: 'Ustawienia prywatności',
    text: 'Za Twoją zgodą korzystamy z Google Analytics do pomiaru wizyt oraz funkcji reklamowych Google do reklamy i personalizacji. Bez zgody Google może otrzymywać ograniczone sygnały bez plików cookie. Decyzję zapisujemy na tym urządzeniu przez 180 dni. Możesz ją zmienić w każdej chwili przyciskiem Ustawienia prywatności.',
    analytics: 'Analityka — pomiar wizyt w Google Analytics',
    ads: 'Reklamy — dane reklamowe i personalizacja reklam',
    accept: 'Akceptuję wszystkie', reject: 'Odrzucam opcjonalne', settings: 'Wybieram ustawienia',
    save: 'Zapisz wybór', reopen: 'Ustawienia prywatności',
    storage: 'Przeglądarka nie zapisała decyzji. Wybór obowiązuje tylko na tej stronie.'
  };

  function readChoice() {
    try {
      var saved = JSON.parse(localStorage.getItem(key));
      if (saved && saved.version === 1 && typeof saved.analytics === 'boolean' &&
          typeof saved.ads === 'boolean' && typeof saved.time === 'number' &&
          saved.time <= Date.now() && Date.now() - saved.time < lifetime) return saved;
    } catch (error) { /* Storage may be unavailable. Defaults remain denied. */ }
    return null;
  }

  function removeCookies(pattern) {
    var cookies;
    try { cookies = document.cookie; }
    catch (error) { return; }
    var domains = [''];
    var parts = location.hostname.split('.');
    for (var i = 0; i < parts.length - 1; i++) {
      domains.push(parts.slice(i).join('.'));
    }
    var paths = ['/'];
    var segments = location.pathname.split('/');
    for (var j = 1; j < segments.length; j++) paths.push(segments.slice(0, j + 1).join('/'));
    cookies.split(';').forEach(function (cookie) {
      var name = cookie.trim().split('=')[0];
      if (!pattern.test(name)) return;
      domains.forEach(function (domain) {
        paths.forEach(function (path) {
          try {
            document.cookie = name + '=; Max-Age=0; Path=' + path +
              (domain ? '; Domain=' + domain : '') + '; SameSite=Lax';
          } catch (error) { /* Cookie access must not prevent consent changes. */ }
        });
      });
    });
  }

  function apply(saved) {
    window.gtag('consent', 'update', {
      analytics_storage: saved.analytics ? 'granted' : 'denied',
      ad_storage: saved.ads ? 'granted' : 'denied',
      ad_user_data: saved.ads ? 'granted' : 'denied',
      ad_personalization: saved.ads ? 'granted' : 'denied'
    });
    if (!saved.analytics) removeCookies(/^(_ga($|_)|_gid$|_gat($|_))/);
    if (!saved.ads) removeCookies(/^(_gcl_|_gac_)/);
  }

  // This file runs synchronously before the GTM loader, including on return visits.
  choice = readChoice();
  if (choice) apply(choice);

  function button(text, handler) {
    var node = document.createElement('button');
    node.type = 'button';
    node.textContent = text;
    node.addEventListener('click', handler);
    return node;
  }

  function save(allowAnalytics, allowAds) {
    choice = { version: 1, analytics: allowAnalytics, ads: allowAds, time: Date.now() };
    apply(choice);
    var persisted = true;
    try { localStorage.setItem(key, JSON.stringify(choice)); }
    catch (error) { persisted = false; }
    panel.hidden = true;
    reopen.hidden = false;
    status.textContent = persisted ? '' : labels.storage;
    reopen.focus();
  }

  function mount() {
    panel = document.createElement('section');
    panel.id = 'ar-consent';
    panel.setAttribute('role', 'region');
    panel.setAttribute('aria-labelledby', 'ar-consent-title');
    panel.innerHTML = '<h2 id="ar-consent-title"></h2><p></p>' +
      '<div class="ar-consent-options" hidden>' +
      '<label><input type="checkbox" name="analytics"><span></span></label>' +
      '<label><input type="checkbox" name="ads"><span></span></label></div>' +
      '<div class="ar-consent-actions"></div>';
    panel.querySelector('h2').textContent = labels.title;
    panel.querySelector('p').textContent = labels.text;
    var options = panel.querySelector('.ar-consent-options');
    analytics = options.querySelector('[name="analytics"]');
    ads = options.querySelector('[name="ads"]');
    var spans = options.querySelectorAll('span');
    spans[0].textContent = labels.analytics;
    spans[1].textContent = labels.ads;
    var actions = panel.querySelector('.ar-consent-actions');
    actions.appendChild(button(labels.accept, function () { save(true, true); }));
    actions.appendChild(button(labels.reject, function () { save(false, false); }));
    var settings = button(labels.settings, function () {
      options.hidden = !options.hidden;
      settings.setAttribute('aria-expanded', String(!options.hidden));
      saveButton.hidden = options.hidden;
    });
    settings.setAttribute('aria-expanded', 'false');
    actions.appendChild(settings);
    var saveButton = button(labels.save, function () { save(analytics.checked, ads.checked); });
    saveButton.hidden = true;
    actions.appendChild(saveButton);
    reopen = button(labels.reopen, function () {
      analytics.checked = !!(choice && choice.analytics);
      ads.checked = !!(choice && choice.ads);
      options.hidden = false;
      saveButton.hidden = false;
      settings.setAttribute('aria-expanded', 'true');
      panel.hidden = false;
      reopen.hidden = true;
      panel.querySelector('h2').focus();
    });
    reopen.id = 'ar-consent-reopen';
    panel.querySelector('h2').tabIndex = -1;
    panel.hidden = !!choice;
    reopen.hidden = !choice;
    status = document.createElement('div');
    status.id = 'ar-consent-status';
    status.setAttribute('role', 'status');
    document.body.appendChild(panel);
    document.body.appendChild(reopen);
    document.body.appendChild(status);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount);
  else mount();
})();
