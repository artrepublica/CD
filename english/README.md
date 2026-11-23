[CD] English build — Cloudflare Pages

This directory generates English pages directly from the current Polish Webflow
export at the repository root. Do not edit generated files in `dist/`.

## Cloudflare setup

- Repository: `artrepublica/CD`
- Project: `cd-en`
- Production branch: `main`
- Framework preset: `None`
- Build command: `python3 english/build.py`
- Build output directory: `english/dist`
- Root directory: leave empty (repository root)
- Environment variables: none required

Python 3.9+ is sufficient; no pip/npm install or network access is used by the
build. The normal Cloudflare Python 3 image is suitable.

The initial build is a **test deployment** with HTML noindex and an HTTP
X-Robots-Tag header. It contains 11 content pages plus 404, local CSS, JS, images,
fonts and English logo/animations. It excludes Location SEO pages and links to
Polish Creative. Existing externally hosted audio/video and third-party embeds
remain external. No checkout, shop, new form backend or payment service is added.
The source currently contains no HTML forms on these pages; email/phone links
remain active. Original audio and video are not translated.

Pages serves clean URLs, e.g. `/pricing` and `/services/mixing-mastering`.
The Polish export's script forcing `.html` URLs is removed only in the EN build
so that it cannot create a redirect loop on Pages. Polish files and CNAME remain
unchanged. The Polish publish workflow excludes the entire `english/` directory;
commits touching only `english/**` do not trigger Polish Pages deployment.

Production pages inherit the `GTM-N8TGSZM9` container from the Polish export;
test builds remove it to keep preview traffic out of GA4. Do not add a separate
GA4 script: GA4 is configured inside GTM. Consent defaults to denied for
analytics and advertising before the container loads. A CMP must update consent
after the visitor's choice; the loader does not provide a consent banner.
Denied consent can still allow cookieless Google pings. Custom tags in GTM must
have their consent requirements configured separately. No noscript iframe is
included because it cannot honor this JavaScript consent setup.

## Updating and checking

```sh
python3 english/build.py
PYTHONDONTWRITEBYTECODE=1 python3 english/test_build.py
```

`tlumaczenia.json` holds reviewed English strings keyed by the exact normalized
Polish source text. The build stops on new/changed text or an unmapped new page;
the Cloudflare build log prints entries requiring translation. Existing deployed
EN remains available after a failed build. This is automatic generation and
translation reuse, not an automatic AI translation API. Webflow remains the
source of layout and Polish content; retain this directory and the publishing
workflow when updating the export in GitHub.

`engine.py` originated in the local EN prototype; this repository copy is now the
build engine for deployment. Local prototype changes are not synchronized into
this directory automatically. Future production corrections belong here.

`kursy-walut.json` contains an indicative PLN conversion snapshot, with its date.
EUR/USD/GBP/PLN switching does not set a payment currency. Refresh the NBP snapshot
before later releases; rates are not fetched live. `cennik-waluty.js` controls the
currency selection. The custom select chevron stays 14 px from its right edge.

## Activation after the test

1. Confirm successful deployment and its actual `*.pages.dev` hostname.
2. Review EN pages, pricing and mobile navigation on that address.
3. In this Pages project's Custom domains add `soundstudio.artrepublica.com`.
4. In OVH's **artrepublica.com** zone add CNAME `soundstudio` pointing to the
   actual hostname from step 1. No nameserver transfer is needed.
5. Verify HTTPS on the custom domain. Then change the build command to
   `python3 english/build.py --production` and redeploy. This enables indexing
   and emits the EN sitemap with canonicals on the custom .com domain.

Do not configure the custom domain on the Polish GitHub Pages site. Do not copy
the Polish `CNAME`, sitemap or redirects into `english/dist`.

Sources for hosting behavior:
[build settings](https://developers.cloudflare.com/pages/configuration/build-configuration/),
[clean URLs](https://developers.cloudflare.com/pages/configuration/serving-pages/),
[custom domains](https://developers.cloudflare.com/pages/configuration/custom-domains/).
