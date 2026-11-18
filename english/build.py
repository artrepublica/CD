#!/usr/bin/env python3
"""Build EN from the current Webflow export. No downloads or dependencies.

Default: public test build with noindex. --production enables indexing for
soundstudio.artrepublica.com after domain activation and review.
"""
import argparse
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import tempfile
from urllib.parse import unquote, urlsplit
import engine

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
OUTPUT = HERE / 'dist'
ASSET_DIRS = ('css', 'js', 'images', 'fonts', 'documents', 'videos')
# The Polish site requires .html; Pages requires extensionless URLs. Carrying
# this exact PL-only redirect into EN would create a redirect loop.
PL_REDIRECT = '(function(){var p=location.pathname;if(p!=="/"&&!p.endsWith("/")&&!p.endsWith(".html")){location.replace(p+".html"+location.search+location.hash);}})();'


def read_source(path, repo):
    if path.is_symlink() or not path.resolve().is_relative_to(repo.resolve()):
        raise ValueError('Source must be a regular file inside the export: ' + str(path))
    return path.read_text(encoding='utf-8')


def localize(body):
    # Assets come from this export, not from the Polish production server.
    body = re.sub(re.escape(engine.ORIGIN) + r'/(?=(?:css|js|images|fonts|documents|videos)/)', '/', body)
    # Explicit quoted asset paths in embeds are not handled by HTML attributes.
    body = re.sub(r'''(["'])(?:\.\./)*(css|js|images|fonts|documents|videos)/([^"']+)\1''',
                  lambda m: m[1] + '/' + m[2] + '/' + m[3] + m[1], body)
    return body


class References(HTMLParser):
    def __init__(self, body):
        super().__init__()
        self.urls = []
        self.feed(body)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        for key in ('src', 'href', 'poster', 'data-src'):
            if a.get(key):
                self.urls.append(a[key])
        if a.get('srcset'):
            self.urls.extend(x.strip().split()[0] for x in a['srcset'].split(',') if x.strip())
        self.urls.extend(re.findall(r'''url\(["']?([^)'"\s]+)''', a.get('style', '')))


def resolve_reference(root, current, url):
    u = urlsplit(html.unescape(url))
    if u.scheme or u.netloc or not u.path:
        return None
    relative = unquote(u.path)
    candidate = (root / relative.lstrip('/') if relative.startswith('/') else current.parent / relative).resolve()
    if not candidate.is_relative_to(root.resolve()):
        raise ValueError('Reference escapes site: ' + url)
    if candidate.is_file():
        return candidate
    if not candidate.suffix and candidate.with_suffix('.html').is_file():
        return candidate.with_suffix('.html')
    if (candidate / 'index.html').is_file():
        return candidate / 'index.html'
    raise ValueError(str(current.relative_to(root)) + ': missing local reference ' + url)


def validate(root):
    for name in engine.PAGES.values():
        page = root / name
        body = page.read_text(encoding='utf-8')
        if 'location.replace(p+".html"' in body:
            raise ValueError('PL-only redirect is present in EN')
        for url in References(body).urls:
            resolve_reference(root, page, url)
        # Also check inline CSS and JS asset URLs.
        scripts = '\n'.join(re.findall(r'<script[^>]*>(.*?)</script>', body, re.S))
        for url in re.findall(r'''["'](/(?:css|js|images|fonts|documents|videos)/[^"']+)["']''', scripts):
            resolve_reference(root, page, url)
    for css in (root / 'css').glob('*.css'):
        for url in re.findall(r'''url\(["']?([^)'"\s]+)''', css.read_text(encoding='utf-8')):
            resolve_reference(root, css, url)
    if (root / 'CNAME').exists() or (root / 'english').exists() or (root / 'lokalizacje').exists():
        raise ValueError('Non-English source content leaked into output')


def build(repo=REPO, config=HERE, output=OUTPUT, production=False):
    repo, config, output = Path(repo).resolve(), Path(config).resolve(), Path(output).resolve()
    if output != config / 'dist':
        raise ValueError('Output must be the dedicated english/dist directory')
    with tempfile.TemporaryDirectory(prefix='cd-en-') as tmp:
        root = Path(tmp)
        for path in repo.rglob('*.html'):
            rel = path.relative_to(repo)
            if rel.parts[0] in {'.git', '.github', 'english', 'lokalizacje'}:
                continue
            body = read_source(path, repo)
            body = body.replace('<script>' + PL_REDIRECT + '</script>', '')
            target = root / 'zrodlo' / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body, encoding='utf-8')
        for name in ('tlumaczenia.json', 'kursy-walut.json', 'cennik-waluty.js'):
            shutil.copyfile(config / name, root / name)
        for asset in engine.ASSETS:
            source = repo / asset
            target = root / 'assets-zrodlo' / source.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(read_source(source, repo), encoding='utf-8')
        # All texts and layout adapters are checked before touching dist.
        try:
            engine.run(root, 'build', preview=False)
        except SystemExit:
            print((root / 'do-tlumaczenia.json').read_text(encoding='utf-8'))
            raise
        stage = root / 'podglad'
        for directory in ASSET_DIRS:
            source = repo / directory
            if not source.exists():
                continue
            for asset in source.rglob('*'):
                if asset.is_symlink():
                    raise ValueError('Symlink in asset directory: ' + str(asset))
                if not asset.is_file():
                    continue
                if asset.stat().st_size > 25 * 1024 * 1024:
                    raise ValueError('Asset exceeds Pages 25 MiB limit: ' + str(asset))
                target = stage / asset.relative_to(repo)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(asset, target)
        for target in stage.rglob('*.html'):
            body = localize(target.read_text(encoding='utf-8'))
            if production:
                body = body.replace('<meta name="robots" content="noindex,nofollow">',
                                    '<meta name="robots" content="index,follow">')
            target.write_text(body, encoding='utf-8')
        (stage / 'robots.txt').write_text('User-agent: *\nAllow: /\n' +
            ('Sitemap: ' + engine.EN_ORIGIN + '/sitemap.xml\n' if production else ''), encoding='utf-8')
        headers = '/*\n  X-Content-Type-Options: nosniff\n'
        if not production:
            headers += '  X-Robots-Tag: noindex, nofollow\n'
        (stage / '_headers').write_text(headers, encoding='utf-8')
        if production:
            urls = [engine.public_en(p) for p in engine.PAGES.values() if p != '404.html']
            (stage / 'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' +
                ''.join('<url><loc>' + html.escape(u) + '</loc></url>' for u in urls) + '</urlset>\n', encoding='utf-8')
        validate(stage)
        if output.exists():
            if output.is_symlink():
                raise ValueError('Output must not be a symlink')
            shutil.rmtree(output)
        shutil.copytree(stage, output)
        # Verify every output file against the checked staging tree.
        for p in stage.rglob('*'):
            if p.is_file():
                assert hashlib.sha256(p.read_bytes()).digest() == hashlib.sha256((output / p.relative_to(stage)).read_bytes()).digest()
    print('EN output:', output, '(production)' if production else '(test, noindex)')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--production', action='store_true')
    args = parser.parse_args()
    build(production=args.production)
