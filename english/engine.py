#!/usr/bin/env python3
"""English translation engine for the Webflow export (stdlib only).

No network requests, API calls, source edits or publication. Unknown text stops
the build. Translations are keyed by the exact normalized source, so new source
text never silently reuses a translation of a different sentence.
"""
import argparse
import base64
import hashlib
import html
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import posixpath
import re
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1] / 'WERSJA-EN'
ORIGIN = 'https://studiodzwiekowe.artrepublica.pl'
EN_ORIGIN = 'https://soundstudio.artrepublica.com'
PAGES = {
    'index.html': 'index.html',
    'cennik.html': 'pricing.html',
    'menu/uslugi/nagraj-audiobook.html': 'services/audiobook-production.html',
    'menu/uslugi/nagraj-film.html': 'services/film-production.html',
    'menu/uslugi/mix-mastering.html': 'services/mixing-mastering.html',
    'menu/projekty/audiobooki.html': 'work/audiobooks.html',
    'menu/projekty/architektura.html': 'work/architecture.html',
    'menu/projekty/film-rasz.html': 'work/rasz.html',
    'menu/projekty/face-clinic.html': 'work/face-clinic.html',
    'menu/projekty/szkola-lauder-morasha.html': 'work/lauder-morasha-school.html',
    'menu/projekty/muzeum-ludowych-instrumentow-muzycznych-w-szydlowcu.html': 'work/museum-of-folk-musical-instruments.html',
    '404.html': '404.html',
}
VOID = set('area base br col embed hr img input link meta param source track wbr'.split())
SKIP = {'script', 'style', 'svg', 'noscript'}
ATTR_RE = re.compile(r'''([^\s=/>]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))''')
TEXT_ATTRS = {'alt', 'title', 'aria-label', 'placeholder', 'data-wait', 'data-ar-label'}
META_TEXT = {'description', 'og:title', 'og:description', 'twitter:title', 'twitter:description'}
JSON_TEXT = {'name', 'description', 'serviceType', 'alternateName'}
PRICING_LITERALS = ['kopiuj', 'skopiowano', 'Skopiowano ', 'Zaznaczono ',
                    '. Użyj opcji Kopiuj lub skrótu ⌘C / Ctrl+C.', 'Skopiuj ręcznie ']
ASSETS = {
    'images/Logo_CD_Jasno-Szare.svg': 'assets/logo-sound-studio-en.svg',
    'documents/AR_CD_WB_Desktop_2026_hybryda.json': 'assets/animation-desktop-en.json',
    'documents/CD_Mobile_2026_r1_hybryda.json': 'assets/animation-mobile-en.json',
}


def norm(value):
    return re.sub(r'\s+', ' ', value).strip(' \t\r\n\u200b\u200d\ufeff')


def source_key(value):
    return hashlib.sha256(norm(value).encode('utf-8')).hexdigest()[:20]


def public_en(name):
    return EN_ORIGIN + ('/' if name == 'index.html' else '/' + name.removesuffix('.html'))


def mapped_path(value, source_page):
    parsed = urlsplit(urljoin(ORIGIN + '/' + source_page, value))
    if parsed.netloc != urlsplit(ORIGIN).netloc:
        return None
    path = parsed.path.lstrip('/') or 'index.html'
    if path.endswith('/'):
        path += 'index.html'
    if path not in PAGES and path + '.html' in PAGES:
        path += '.html'
    return (path, parsed)


class Page(HTMLParser):
    def __init__(self, source, name):
        super().__init__(convert_charrefs=True)
        self.source, self.name = source, name
        self.lines = [0] + [m.end() for m in re.finditer('\n', source)]
        self.stack, self.items, self.edits, self.removals, self.json_blocks = [], [], [], [], []
        self.warnings = []
        self.feed(source)
        self.close()

    def absolute_pos(self):
        line, col = self.getpos()
        return self.lines[line - 1] + col

    def item(self, start, end, raw, kind, context):
        value = norm(html.unescape(raw))
        if value:
            self.items.append({'start': start, 'end': end, 'raw': raw, 'source': value,
                               'key': source_key(value), 'kind': kind, 'context': context})

    def handle_starttag(self, tag, attrs):
        start, raw, a = self.absolute_pos(), self.get_starttag_text(), dict(attrs)
        entry = {'tag': tag, 'start': start, 'attrs': a}
        link = urlsplit(urljoin(ORIGIN + '/' + self.name, a.get('href', '')))
        excluded = tag == 'a' and (link.path.startswith('/lokalizacje/') or link.hostname in {'artrepublica.pl', 'www.artrepublica.pl'})
        entry['excluded'] = excluded or any(e['excluded'] for e in self.stack)
        if tag not in VOID:
            self.stack.append(entry)
        if tag == 'link' and a.get('rel') in {'canonical', 'alternate'}:
            self.removals.append((start, start + len(raw)))
        if tag == 'meta' and a.get('name', '').lower() == 'robots':
            self.removals.append((start, start + len(raw)))
        if tag == 'iframe':
            self.warnings.append('External iframe: ' + a.get('src', '')[:160])
        for match in ATTR_RE.finditer(raw):
            key = match.group(1).lower()
            group = next(g for g in (2, 3, 4) if match.group(g) is not None)
            value = match.group(group)
            lo, hi = start + match.start(group), start + match.end(group)
            if tag == 'html' and key == 'lang':
                self.edits.append((lo, hi, 'en'))
            elif key in TEXT_ATTRS or (tag == 'input' and key == 'value' and a.get('type') in {'submit', 'button'}):
                if not entry['excluded']:
                    self.item(lo, hi, value, 'attribute', tag + '@' + key)
            elif tag == 'meta' and key == 'content' and a.get('name', a.get('property', '')) in META_TEXT:
                self.item(lo, hi, value, 'attribute', 'meta ' + a.get('name', a.get('property', '')))
            elif tag == 'meta' and key == 'content' and a.get('property') == 'og:url':
                self.edits.append((lo, hi, html.escape(public_en(PAGES[self.name]), quote=True)))
            elif key in {'src', 'href', 'poster', 'data-src'} and value and not value.startswith(('data:', 'mailto:', 'tel:', 'javascript:', '#')):
                absolute = urljoin(ORIGIN + '/' + self.name, html.unescape(value))
                if tag == 'iframe' and key == 'src':
                    if 'youtube.com/embed/' in absolute or 'google.com/maps/embed' in absolute:
                        absolute += ('&' if '?' in absolute else '?') + 'hl=en'
                target = mapped_path(html.unescape(value), self.name) if tag == 'a' and key == 'href' else None
                if target and target[0] in PAGES:
                    path, parsed = target
                    relative = '/' if path == 'index.html' else '/' + PAGES[path].removesuffix('.html')
                    absolute = urlunsplit(('', '', relative, parsed.query, parsed.fragment))
                asset_path = urlsplit(urljoin(ORIGIN + '/' + self.name, html.unescape(value))).path.lstrip('/')
                if asset_path in ASSETS:
                    absolute = posixpath.relpath(ASSETS[asset_path], posixpath.dirname(PAGES[self.name]) or '.')
                self.edits.append((lo, hi, html.escape(absolute, quote=True)))
            elif key == 'srcset':
                values = []
                for candidate in html.unescape(value).split(','):
                    parts = candidate.strip().split()
                    if parts:
                        parts[0] = urljoin(ORIGIN + '/' + self.name, parts[0])
                        values.append(' '.join(parts))
                self.edits.append((lo, hi, html.escape(', '.join(values), quote=True)))
            elif key == 'style' and 'url(' in value:
                new = re.sub(r'url\([\'\"]?([^\)\'\"]+)[\'\"]?\)',
                             lambda m: 'url(' + urljoin(ORIGIN + '/' + self.name, html.unescape(m[1])) + ')', value)
                self.edits.append((lo, hi, html.escape(new, quote=True)))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i]['tag'] == tag:
                entry = self.stack[i]
                if tag == 'a' and entry['excluded']:
                    end = self.source.find('>', self.absolute_pos()) + 1
                    self.removals.append((entry['start'], end))
                del self.stack[i:]
                break

    def handle_data(self, data):
        start = self.absolute_pos()
        end = self.source.find('<', start)
        if end < 0:
            end = len(self.source)
        if self.stack and self.stack[-1]['tag'] == 'script' and self.stack[-1]['attrs'].get('type') == 'application/ld+json':
            # JSON may contain a '<' inside a quoted value; the closing script
            # is the actual boundary, and the entire block is rendered at once.
            end = self.source.lower().find('</script', start)
            raw = self.source[start:end]
            try:
                obj = json.loads(raw)
            except ValueError as exc:
                raise ValueError(self.name + ': invalid JSON-LD') from exc
            self.json_blocks.append((start, end, obj))
            self.walk_json(obj, collect=True)
        elif self.stack and self.stack[-1]['tag'] == 'script' and self.name == 'cennik.html' and '.ar-pricing' in data:
            # Explicit adapter for the existing pricing embed's UI strings;
            # arbitrary JavaScript and CSS are never machine-translated.
            for literal in PRICING_LITERALS:
                for match in re.finditer(re.escape(json.dumps(literal, ensure_ascii=False)), data):
                    self.item(start + match.start() + 1, start + match.end() - 1,
                              literal, 'javascript', 'pricing clipboard message')
        elif not any(e['tag'] in SKIP or e['excluded'] for e in self.stack):
            self.item(start, end, self.source[start:end], 'text', '/'.join(e['tag'] for e in self.stack[-3:]))

    def walk_json(self, obj, collect=False, translations=None, field=''):
        if isinstance(obj, dict):
            return {k: self.walk_json(v, collect, translations, k) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self.walk_json(v, collect, translations, field) for v in obj]
        if isinstance(obj, str):
            if field in JSON_TEXT and norm(obj):
                if collect:
                    self.items.append({'source': norm(obj), 'key': source_key(obj), 'kind': 'json', 'context': 'JSON-LD ' + field})
                else:
                    return translations[source_key(obj)]['en']
            if not collect and obj.startswith(ORIGIN):
                target = mapped_path(obj, self.name)
                if target and target[0] in PAGES:
                    return public_en(PAGES[target[0]]) + (('#' + target[1].fragment) if target[1].fragment else '')
                return obj.replace(ORIGIN, EN_ORIGIN, 1)
        return obj

    def render(self, translations, preview=True):
        edits = list(self.edits)
        for item in self.items:
            if item['kind'] == 'json':
                continue
            target = html.escape(translations[item['key']]['en'], quote=True)
            raw = item['raw']
            leading = re.match(r'^\s*', raw)[0]
            trailing = re.search(r'\s*$', raw)[0]
            if item['kind'] == 'javascript':
                target = json.dumps(leading + translations[item['key']]['en'] + trailing, ensure_ascii=False)[1:-1]
            else:
                target = leading + target + trailing
            edits.append((item['start'], item['end'], target))
        for start, end, obj in self.json_blocks:
            translated = self.walk_json(obj, translations=translations)
            edits.append((start, end, json.dumps(translated, ensure_ascii=False).replace('</', '<\\/')))
        edits = [e for e in edits if not any(a <= e[0] and e[1] <= b for a, b in self.removals)]
        edits += [(a, b, '') for a, b in self.removals]
        # A translated attribute inside a removed element must not overlap it.
        edits.sort(key=lambda e: (e[0], e[1]))
        for left, right in zip(edits, edits[1:]):
            if left[1] > right[0]:
                raise ValueError(self.name + ': overlapping HTML edits')
        result = self.source
        for start, end, replacement in reversed(edits):
            result = result[:start] + replacement + result[end:]
        relative_review = posixpath.relpath('translation-review.html', posixpath.dirname(PAGES[self.name]) or '.')
        seo = ('<meta name="robots" content="noindex,nofollow">'
               '<link rel="canonical" href="' + public_en(PAGES[self.name]) + '">'
               '<link rel="alternate" hreflang="en" href="' + public_en(PAGES[self.name]) + '">'
               '<link rel="alternate" hreflang="pl" href="' + ORIGIN + ('/' if self.name == 'index.html' else '/' + self.name) + '">')
        result = result.replace('</head>', seo + '</head>', 1)
        if not preview:
            return result
        badge = ('<aside style="position:fixed;bottom:8px;left:8px;z-index:2147483646;'
                 'font:12px/1.5 Arial,sans-serif;padding:7px 11px;border-radius:8px;'
                 'background:#101820;color:#fff;box-shadow:0 2px 14px #0006">EN preview · '
                 '<a style="color:#8ed5ff" href="' + ORIGIN + ('/' if self.name == 'index.html' else '/' + self.name) + '">PL original</a> · '
                 '<a style="color:#8ed5ff" href="' + relative_review + '">Translation review</a></aside>')
        guard = ('<script>document.addEventListener("submit",function(e){e.preventDefault();'
                 'e.stopImmediatePropagation();alert("This is a preview. Please use the Polish website to submit forms.");},true);</script>')
        return result.replace('</body>', badge + guard + '</body>', 1)


def scan(root):
    result = {}
    unknown = [str(p.relative_to(root / 'zrodlo')) for p in (root / 'zrodlo').rglob('*.html')
               if str(p.relative_to(root / 'zrodlo')) not in PAGES
               and not str(p.relative_to(root / 'zrodlo')).startswith('lokalizacje/')
               and p.name not in {'401.html', 'google552765333c924b75.html'}]
    if unknown:
        raise ValueError('New source pages need English URL mappings: ' + ', '.join(unknown))
    for name in PAGES:
        path = root / 'zrodlo' / name
        if not path.is_file():
            raise ValueError('Missing source: ' + str(path))
        result[name] = Page(path.read_text(encoding='utf-8'), name)
    return result


def inventory(pages):
    result = {}
    for name, page in pages.items():
        for item in page.items:
            key = item['key']
            row = result.setdefault(key, {'source': item['source'], 'en': '', 'status': 'missing', 'occurrences': []})
            if row['source'] != item['source']:
                raise ValueError('Translation key collision')
            occurrence = {'page': name, 'kind': item['kind'], 'context': item['context']}
            if occurrence not in row['occurrences']:
                row['occurrences'].append(occurrence)
    return result


def write_checked(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    if path.read_text(encoding='utf-8') != text:
        raise OSError('Write verification failed: ' + str(path))


def review_html(records):
    rows = []
    for key, row in records.items():
        places = ', '.join(dict.fromkeys(PAGES[o['page']] for o in row['occurrences']))
        rows.append('<tr><td>' + html.escape(row['source']) + '</td><td>' + html.escape(row['en']) + '</td><td>' + html.escape(places) + '</td></tr>')
    links = ''.join('<li><a href="' + dest + '">' + dest + '</a></li>' for src, dest in PAGES.items() if src != '404.html')
    return '''<!doctype html><html lang="pl"><meta charset="utf-8"><meta name="robots" content="noindex,nofollow"><meta name="viewport" content="width=device-width,initial-scale=1"><title>[CD] Przegląd wersji EN</title>
<style>body{font:16px/1.6 system-ui;margin:32px auto;max-width:1300px;padding:0 20px;color:#192b39}h1{font-size:28px}input{font:inherit;padding:10px;width:min(600px,90%)}table{border-collapse:collapse;width:100%;margin-top:24px}th,td{padding:14px;text-align:left;border-bottom:1px solid #dce3e9;vertical-align:top}td:nth-child(1),td:nth-child(2){width:42%}td:last-child{font-size:11px;overflow-wrap:anywhere}thead{background:#edf5fb;position:sticky;top:0}a{color:#006fb0}summary{cursor:pointer}@media(max-width:700px){th:last-child,td:last-child{display:none}td{padding:9px;font-size:14px}}</style>
<h1>[CD] Angielska wersja obecnej strony</h1><p>Wersja robocza do przeglądu. Pominięto Lokalizacje i odnośniki do polskiego Creative. Układ i treść źródłowa pochodzą z obecnej strony; teksty EN są w osobnym katalogu tłumaczeń. Nagrania i materiały filmowe pozostają w oryginale; tytuły książek i opisy realizacji mają angielskie odpowiedniki.</p>
<details><summary>Strony podglądu</summary><ul>''' + links + '''</ul></details><p><label>Filtruj tekst: <input id="filter" type="search" placeholder="np. mastering, audiobook, cena"></label></p>
<table><thead><tr><th>Polski oryginal</th><th>Wersja angielska</th><th>Strony</th></tr></thead><tbody>''' + ''.join(rows) + '''</tbody></table><script>document.getElementById('filter').addEventListener('input',function(){const q=this.value.toLowerCase();document.querySelectorAll('tbody tr').forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q));});</script></html>'''


def english_assets(root):
    output = {}
    for source, target in ASSETS.items():
        path = root / 'assets-zrodlo' / Path(source).name
        text = path.read_text(encoding='utf-8')
        if source.endswith('.svg'):
            ns = '{http://www.w3.org/2000/svg}'
            ET.register_namespace('', ns[1:-1])
            svg = ET.fromstring(text)
            group = svg.find(ns + 'g')
            subtitles = group.findall(ns + 'g')
            if len(subtitles) != 1 or len(subtitles[0].findall(ns + 'path')) < 10:
                raise ValueError('Unexpected subtitle structure in the source logo')
            group.remove(subtitles[0])
            subtitle = ET.SubElement(group, ns + 'text', {
                'x': '57', 'y': '63', 'fill': '#E6E7E8', 'font-family': 'Arial, sans-serif',
                'font-size': '28', 'letter-spacing': '2', 'textLength': '240', 'lengthAdjust': 'spacingAndGlyphs',
            })
            subtitle.text = 'sound studio'
            output[target] = ET.tostring(svg, encoding='unicode')
        else:
            data = json.loads(text)
            layers = [l for l in data['layers'] if l.get('nm') == 'studio dźwiękowe Outlines']
            if len(layers) != 1:
                raise ValueError('Unexpected studio subtitle in the source animation')
            layer = layers[0]
            layer.pop('shapes')
            layer.update(ty=5, nm='sound studio EN')
            layer['t'] = {'d': {'k': [{'t': 0, 's': {
                't': 'sound studio', 'f': 'OpenSansLocal-Regular', 's': 28,
                'j': 0, 'tr': 100, 'lh': 34, 'ls': 0, 'fc': [1, 1, 1],
            }}]}, 'p': {}, 'm': {'g': 1, 'a': {'a': 0, 'k': [0, 0]}}, 'a': []}
            data.setdefault('fonts', {}).setdefault('list', []).append({
                'fName': 'OpenSansLocal-Regular', 'fFamily': 'Open Sans Local',
                'fStyle': 'Regular', 'ascent': 75,
            })
            output[target] = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    return output


def portable_preview(output):
    """Single-file review: pages and local logo/animation assets are embedded.

    Styles, photos, fonts and media still come from the original public site.
    This is a review artifact, never the public production build.
    """
    pages = {name: body for name, body in output.items() if name.endswith('.html')}
    assets = {}
    for name, body in output.items():
        if name.startswith('assets/'):
            mime = 'image/svg+xml' if name.endswith('.svg') else 'application/json'
            assets[name] = 'data:' + mime + ';base64,' + base64.b64encode(body.encode()).decode()
    data = json.dumps({'pages': pages, 'assets': assets}, ensure_ascii=False).replace('</', '<\\/')
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="robots" content="noindex,nofollow"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ARTREPUBLICA Sound Studio - English preview</title><style>html,body,iframe{width:100%;height:100%;margin:0;border:0;display:block}</style><iframe id="preview" title="English website preview"></iframe><script>
const bundle=''' + data + ''';
const frame=document.getElementById('preview');
function show(name,hash=''){
 if(!Object.hasOwn(bundle.pages,name))return;
 let body=bundle.pages[name];
 const folder=name.includes('/')?name.slice(0,name.lastIndexOf('/')+1):'';
 for(const [asset,url] of Object.entries(bundle.assets)){
   const path=(folder?'../':'')+asset;
   body=body.split(path).join(url);
 }
 const routes=JSON.stringify(Object.keys(bundle.pages));
 const bridge=`<script>const routes=${routes};document.addEventListener('click',function(e){const a=e.target.closest('a[href]');if(!a)return;const u=new URL(a.href);if(u.origin==='https://en-preview.invalid'&&routes.includes(u.pathname.slice(1))){e.preventDefault();parent.postMessage({type:'en-preview',page:u.pathname.slice(1),hash:u.hash},'*');}},true);if(${JSON.stringify(hash)})addEventListener('load',()=>{const el=document.getElementById(${JSON.stringify(hash)}.slice(1));if(el)el.scrollIntoView();});<`+'/script>';
 body=body.replace('<head>','<head><base href="https://en-preview.invalid/'+name+'">');
 body=body.replace('</body>',bridge+'</body>');
 frame.srcdoc=body;
}
addEventListener('message',e=>{if(e.source===frame.contentWindow&&e.data?.type==='en-preview')show(e.data.page,e.data.hash);});
show('index.html');
</script></html>'''


def currency_pricing(root, body):
    """Add indicative currency display; keep every original PLN amount intact."""
    config = json.loads((root / 'kursy-walut.json').read_text(encoding='utf-8'))
    rates = config['pln_per_unit']
    if config.get('model') != 'indicative' or config.get('default_currency') not in {'PLN', 'EUR', 'USD', 'GBP'}:
        raise ValueError('Unsupported pricing currency model')
    if set(rates) != {'PLN', 'EUR', 'USD', 'GBP'} or rates['PLN'] != 1:
        raise ValueError('Expected PLN base and EUR/USD/GBP reference rates')
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0 for v in rates.values()):
        raise ValueError('Invalid currency reference rate')
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', config['effective_date']):
        raise ValueError('Missing reference rate date')

    class Amounts(HTMLParser):
        def __init__(self, source):
            super().__init__(convert_charrefs=True)
            self.source, self.in_cell, self.edits = source, False, []
            self.lines = [0] + [m.end() for m in re.finditer('\n', source)]
            self.feed(source)

        def handle_starttag(self, tag, attrs):
            if tag == 'td':
                self.in_cell = True

        def handle_endtag(self, tag):
            if tag == 'td':
                self.in_cell = False

        def handle_data(self, data):
            if not self.in_cell or 'PLN' not in data:
                return
            line, col = self.getpos()
            start = self.lines[line - 1] + col
            number = r'(\d+(?:,\d{3})*)'
            matches = list(re.finditer(r'PLN\s+' + number + r'(?:[-–]' + number + r')?', data))
            if not matches:
                raise ValueError('Unrecognised PLN price format')
            for match in matches:
                low = int(match[1].replace(',', ''))
                high = int(match[2].replace(',', '')) if match[2] else None
                if high is not None and high < low:
                    raise ValueError('Invalid price range')
                attrs = ' data-pln-min="' + str(low) + '"'
                if high is not None:
                    attrs += ' data-pln-max="' + str(high) + '"'
                replacement = '<span class="ar-price-amount"' + attrs + '>' + html.escape(match[0]) + '</span>'
                self.edits.append((start + match.start(), start + match.end(), replacement))

    parsed = Amounts(body)
    if not parsed.edits:
        raise ValueError('No PLN prices found in pricing tables')
    for start, end, text in reversed(parsed.edits):
        body = body[:start] + text + body[end:]
    controls = '''<div class="ar-currency" hidden>
<label for="ar-currency-select">Currency
<select id="ar-currency-select" aria-describedby="ar-currency-note">
<option value="EUR">EUR · Euro (€)</option><option value="USD">USD · US dollar ($)</option><option value="GBP">GBP · Pound sterling (£)</option><option value="PLN" selected>PLN · Polish zloty (zł)</option>
</select></label><p id="ar-currency-note" data-currency-note role="status" aria-live="polite"></p></div>'''
    anchor = '<div class="ar-pricing__inner">'
    if body.count(anchor) != 1:
        raise ValueError('Pricing layout changed: currency control placement needs review')
    body = body.replace(anchor, anchor + controls, 1)
    style = '''<style>
.ar-currency[hidden]{display:none}.ar-currency{display:grid;grid-template-columns:minmax(0,235px) minmax(0,580px);align-items:start;justify-content:start;gap:12px 22px;margin:0 0 20px;padding:15px 18px;background:var(--ar-panel);border-radius:var(--ar-radius);-webkit-backdrop-filter:blur(30px);backdrop-filter:blur(30px);color:#fff;text-align:left}
.ar-currency label{display:grid;gap:5px;flex:0 1 235px;max-width:100%;font-size:12px;line-height:1.5;letter-spacing:.06em}.ar-currency select{width:100%;max-width:100%;min-height:42px;border:0;outline:none;box-shadow:none;border-radius:8px;padding:8px 42px 8px 10px;appearance:none;-webkit-appearance:none;background-color:rgba(0,68,119,.55);background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Cpath d='M4 6l4 4 4-4' fill='none' stroke='white' stroke-width='1.7' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right 14px center;background-size:14px 14px;color:#fff;font-family:inherit;font-size:14px;font-weight:600;line-height:1.4;letter-spacing:normal}.ar-currency select:hover,.ar-currency select:focus-visible{outline:none;box-shadow:none;background-color:rgba(0,54,98,.85)}.ar-currency option{background:#fff;color:#183044}.ar-currency p{margin:0;padding-top:23px;font-size:12px;line-height:1.6;max-width:580px}.ar-price-amount{font-variant-numeric:tabular-nums}
@media(max-width:560px){.ar-currency{grid-template-columns:minmax(0,1fr);padding:13px 16px;gap:10px}.ar-currency p{padding-top:0}}
</style>'''
    body = body.replace('</head>', style + '</head>', 1)
    data = json.dumps(config, ensure_ascii=False).replace('</', '<\\/')
    script = (root / 'cennik-waluty.js').read_text(encoding='utf-8')
    body = body.replace('</body>', '<script id="ar-currency-rates" type="application/json">' + data + '</script><script>' + script + '</script></body>', 1)
    return body


def run(root, command, preview=True):
    pages = scan(root)
    needed = inventory(pages)
    catalog_path = root / 'tlumaczenia.json'
    existing = json.loads(catalog_path.read_text(encoding='utf-8')) if catalog_path.exists() else {}
    missing = {}
    for key, row in needed.items():
        saved = existing.get(key)
        if saved and saved['source'] == row['source'] and isinstance(saved.get('en'), str) and saved['en'].strip() and saved.get('status') in {'reviewed', 'keep'}:
            row.update(en=saved['en'], status=saved['status'])
        else:
            missing[key] = row
    report = {'pages': len(pages), 'segments': len(needed), 'missing': len(missing),
              'excluded': '/lokalizacje/', 'external_content': {name: p.warnings for name, p in pages.items() if p.warnings}}
    write_checked(root / 'raport.json', json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    write_checked(root / 'do-tlumaczenia.json', json.dumps(missing, ensure_ascii=False, indent=2) + '\n')
    if command == 'scan':
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    if missing:
        raise SystemExit('Build stopped: ' + str(len(missing)) + ' missing or unreviewed translations; see do-tlumaczenia.json')
    # Render all pages before writing any of them: no partial build on failure.
    output = {PAGES[name]: page.render(needed, preview=preview) for name, page in pages.items()}
    output['pricing.html'] = currency_pricing(root, output['pricing.html'])
    output.update(english_assets(root))
    if preview:
        output['translation-review.html'] = review_html(needed)
        output['preview.html'] = portable_preview(output)
    for name, body in output.items():
        write_checked(root / 'podglad' / name, body)
    print('Built', len(pages), 'pages;', len(needed), 'source segments; no missing translations.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['scan', 'build'])
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    run(args.root.resolve(), args.command)
