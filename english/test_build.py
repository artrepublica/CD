#!/usr/bin/env python3
"""Integration checks for the Cloudflare EN build."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import build as en


class BuildChecks(unittest.TestCase):
    def fixture(self):
        temp = tempfile.TemporaryDirectory(prefix='cd-en-test-')
        self.addCleanup(temp.cleanup)
        repo = Path(temp.name) / 'export'
        config = repo / 'english'
        config.mkdir(parents=True)
        for name in en.engine.PAGES:
            target = repo / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(en.REPO / name, target)
        for directory in en.ASSET_DIRS:
            if (en.REPO / directory).exists():
                shutil.copytree(en.REPO / directory, repo / directory)
        for name in ('tlumaczenia.json', 'kursy-walut.json', 'cennik-waluty.js'):
            shutil.copyfile(en.HERE / name, config / name)
        return repo, config, config / 'dist'

    def build(self, repo, config, output, production=False):
        with contextlib.redirect_stdout(io.StringIO()):
            en.build(repo, config, output, production)

    def test_test_build_is_complete_and_does_not_publish_source(self):
        repo, config, output = self.fixture()
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in repo.rglob('*') if p.is_file()}
        self.build(repo, config, output)
        for name in en.engine.PAGES.values():
            body = (output / name).read_text()
            self.assertIn('<meta name="robots" content="noindex,nofollow">', body)
            self.assertNotIn('EN preview', body)
            self.assertNotIn(en.PL_REDIRECT, body)
            self.assertNotIn(en.engine.ORIGIN + '/css/', body)
            self.assertNotIn(en.engine.ORIGIN + '/images/', body)
            self.assertNotIn('/lokalizacje/', body)
            self.assertNotIn('GTM-N8TGSZM9', body)
            self.assertNotIn('googletagmanager.com', body)
            self.assertNotIn('src="/js/consent.js"', body)
            self.assertNotIn('href="/css/consent.css"', body)
        self.assertIn('href="/pricing"', (output / 'index.html').read_text())
        self.assertIn('https://soundstudio.artrepublica.com/pricing"', (output / 'pricing.html').read_text())
        self.assertIn('X-Robots-Tag: noindex', (output / '_headers').read_text())
        for name in ('CNAME', 'english', 'lokalizacje', 'preview.html', 'translation-review.html', 'tlumaczenia.json'):
            self.assertFalse((output / name).exists(), name)
        for path, sha in before.items():
            self.assertEqual(sha, hashlib.sha256(path.read_bytes()).hexdigest())
        for directory in ('css', 'js', 'images', 'fonts', 'assets'):
            self.assertTrue(any((output / directory).iterdir()))
        self.assertEqual((output / 'pricing.html').read_text().count('data-pln-min='), 12)

    def test_changed_text_fails_and_preserves_previous_build(self):
        repo, config, output = self.fixture()
        self.build(repo, config, output)
        old = (output / 'index.html').read_bytes()
        catalog = (config / 'tlumaczenia.json').read_bytes()
        source = repo / 'index.html'
        body = source.read_text()
        self.assertIn('Witamy na stronie', body)
        source.write_text(body.replace('Witamy na stronie', 'Nowy tekst wymagający tłumaczenia', 1))
        with self.assertRaises(SystemExit):
            self.build(repo, config, output)
        self.assertEqual((output / 'index.html').read_bytes(), old)
        self.assertEqual((config / 'tlumaczenia.json').read_bytes(), catalog)

    def test_new_non_location_page_requires_mapping(self):
        repo, config, output = self.fixture()
        (repo / 'new-service.html').write_text('<p>Nowa usługa</p>')
        with self.assertRaisesRegex(ValueError, 'English URL mappings'):
            self.build(repo, config, output)
        self.assertFalse(output.exists())

    def test_missing_local_asset_fails_before_output(self):
        repo, config, output = self.fixture()
        (repo / 'css/normalize.css').unlink()
        with self.assertRaisesRegex(ValueError, 'missing local reference'):
            self.build(repo, config, output)
        self.assertFalse(output.exists())

    def test_production_has_clean_urls_and_sitemap(self):
        repo, config, output = self.fixture()
        self.build(repo, config, output, production=True)
        self.assertIn('content="index,follow"', (output / 'index.html').read_text())
        self.assertNotIn('X-Robots-Tag', (output / '_headers').read_text())
        sitemap = (output / 'sitemap.xml').read_text()
        self.assertEqual(sitemap.count('<url>'), 11)
        self.assertNotIn('.html', sitemap)
        self.assertNotIn('/404', sitemap)
        self.assertIn('Sitemap:', (output / 'robots.txt').read_text())
        for name in en.engine.PAGES.values():
            body = (output / name).read_text()
            self.assertEqual(body.count('GTM-N8TGSZM9'), 1)
            self.assertLess(body.index("gtag('consent', 'default'"),
                            body.index("event:'gtm.js'"))
            self.assertIn('src="/js/consent.js"', body)
            self.assertIn('href="/css/consent.css"', body)
            self.assertLess(body.index('src="/js/consent.js"'),
                            body.index("event:'gtm.js'"))


if __name__ == '__main__':
    unittest.main(verbosity=2)
