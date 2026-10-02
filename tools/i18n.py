#!/usr/bin/env python3
"""
French version of the site.

    python3 tools/i18n.py extract   # English strings -> i18n/strings-en.json (new strings only need translating)
    python3 tools/i18n.py apply     # writes site/fr/... from i18n/fr.json and adds the language switcher

Edit translations in i18n/fr.json (English text -> French text, HTML kept), then run `apply`.
Any English string missing from fr.json stays in English on the French page and is listed.
"""
import json
import re
import shutil
import sys
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
FR = SITE / "fr"
I18N = ROOT / "i18n"
SITE_URL = "https://www.breakingwalls.co"

BLOCKS = ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "figcaption", "legend", "button", "small", "time",
          "label > span", ".cap", ".meta", ".tag", "a.btn", "a.more", ".plist span", ".post-nav a"]
SKIP = ("script", "style", "svg")

GLOBE = ('<svg class="lang-ico" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9.5"/>'
         '<path d="M2.5 12h19M12 2.5c2.6 2.8 3.9 6 3.9 9.5S14.6 18.7 12 21.5M12 2.5C9.4 5.3 8.1 8.5 8.1 12s1.3 6.7 3.9 9.5"/></svg>')
CHEV = '<svg class="lang-chev" viewBox="0 0 10 6" aria-hidden="true"><path d="M1 1l4 4 4-4"/></svg>'


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


def unit_elements(soup):
    out = []
    for el in soup.select(",".join(BLOCKS)):
        if any(el.find_parent(a) for a in SKIP) or el.find_parent(class_="lang"):
            continue
        if el.name == "li" and el.find(["ul", "ol", "p"]):
            continue
        if el.find_parent(["p", "h1", "h2", "h3", "h4", "button", "figcaption"]) and el.name != "time":
            continue
        inner = norm(el.decode_contents())
        if not re.search(r"[A-Za-z]{2,}", BeautifulSoup(inner, "lxml").get_text()):
            continue
        out.append((el, inner))
    return out


ATTR_SEL = 'meta[name=description], meta[property="og:title"], meta[property="og:description"]'


def attr_strings(soup):
    out = []
    if soup.title:
        out.append(norm(soup.title.get_text()))
    for m in soup.select(ATTR_SEL):
        out.append(norm(m.get("content", "")))
    for el in soup.select("[alt], [aria-label]"):
        if el.find_parent(class_="lang"):
            continue
        for a in ("alt", "aria-label"):
            v = norm(el.get(a, "") or "")
            if re.search(r"[A-Za-z]{3,}", v):
                out.append(v)
    return out


def en_pages():
    for f in sorted(SITE.rglob("index.html")):
        if FR in f.parents:
            continue
        yield f


def page_path(f):
    rel = f.parent.relative_to(SITE).as_posix()
    return "/" if rel == "." else f"/{rel}"


# ------------------------------------------------------------------ extract
def extract():
    strings = {}
    for f in list(en_pages()) + [SITE / "404.html"]:
        soup = BeautifulSoup(f.read_text(), "lxml")
        for s in [u for _, u in unit_elements(soup)] + attr_strings(soup):
            if s and s not in strings:
                strings[s] = 1
    I18N.mkdir(exist_ok=True)
    json.dump(list(strings), open(I18N / "strings-en.json", "w"), ensure_ascii=False, indent=0)
    fr = json.load(open(I18N / "fr.json")) if (I18N / "fr.json").exists() else {}
    todo = [s for s in strings if s not in fr]
    print(f"{len(strings)} strings, {len(todo)} not yet in i18n/fr.json")


# ------------------------------------------------------------------ apply
def fr_href(h):
    if not h or not h.startswith("/") or h.startswith(("/assets/", "/fr/", "//")) or h in ("/favicon.ico", "/apple-touch-icon.png"):
        return h
    return "/fr" + h if h != "/" else "/fr/"


def switcher(cur, en_url, fr_url, extra_cls=""):
    label = "Français" if cur == "fr" else "English"
    return (f'<div class="lang{extra_cls}"><button type="button" aria-haspopup="true" aria-expanded="false" '
            f'aria-label="{"Langue" if cur == "fr" else "Language"}">{GLOBE}<span>{label}</span>{CHEV}</button>'
            f'<ul class="lang-menu">'
            f'<li><a href="{en_url}" hreflang="en" lang="en"{" aria-current=true" if cur == "en" else ""}>English</a></li>'
            f'<li><a href="{fr_url}" hreflang="fr" lang="fr"{" aria-current=true" if cur == "fr" else ""}>Français</a></li>'
            f'</ul></div>')


def add_lang_ui(soup, cur, en_url, fr_url):
    for old in soup.select(".lang, .lang-float, link[hreflang]"):
        old.decompose()
    head = soup.head
    for code, url in (("en", en_url), ("fr", fr_url), ("x-default", en_url)):
        head.append(BeautifulSoup(f'<link rel="alternate" hreflang="{code}" href="{SITE_URL}{url}">', "html.parser"))
    acts = soup.select_one(".hd-actions")
    mob = soup.select_one(".hd-mobile")
    if acts:
        acts.append(BeautifulSoup(switcher(cur, en_url, fr_url), "html.parser"))
    if mob:
        mob.append(BeautifulSoup(switcher(cur, en_url, fr_url, " lang-mobile"), "html.parser"))
    if not acts:
        soup.body.insert(0, BeautifulSoup(switcher(cur, en_url, fr_url, " lang-float"), "html.parser"))


def apply():
    tr = json.load(open(I18N / "fr.json"))
    missing = {}
    if FR.exists():
        shutil.rmtree(FR)
    for f in en_pages():
        path = page_path(f)
        en_url = path if path == "/" else path
        fr_url = "/fr/" if path == "/" else "/fr" + path

        # English page: just the switcher + hreflang
        en = BeautifulSoup(f.read_text(), "lxml")
        add_lang_ui(en, "en", en_url, fr_url)
        f.write_text(str(en))

        # French page
        soup = BeautifulSoup(f.read_text(), "lxml")
        for el, key in unit_elements(soup):
            t = tr.get(key)
            if t is None:
                missing[key] = path
                continue
            el.clear()
            for node in list(BeautifulSoup(t, "html.parser").contents):
                el.append(node)
        if soup.title:
            k = norm(soup.title.get_text())
            soup.title.string = tr.get(k, k)
        for m in soup.select(ATTR_SEL):
            k = norm(m.get("content", ""))
            m["content"] = tr.get(k, k)
        for el in soup.select("[alt], [aria-label]"):
            if el.find_parent(class_="lang"):
                continue
            for a in ("alt", "aria-label"):
                if el.get(a):
                    k = norm(el[a])
                    el[a] = tr.get(k, el[a])
        for a in soup.select("a[href]"):
            if a.find_parent(class_="lang"):
                continue
            a["href"] = fr_href(a["href"])
        soup.html["lang"] = "fr-CA"
        can = soup.select_one('link[rel=canonical]')
        if can:
            can["href"] = SITE_URL + fr_url
        ogu = soup.select_one('meta[property="og:url"]')
        if ogu:
            ogu["content"] = SITE_URL + fr_url
        loc = soup.new_tag("meta", property="og:locale", content="fr_CA")
        soup.head.append(loc)
        add_lang_ui(soup, "fr", en_url, fr_url)
        out = FR / f.parent.relative_to(SITE) / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(str(soup))

    # sitemap with both languages
    urls = []
    for f in en_pages():
        p = page_path(f)
        if p == "/breakingwalls":
            continue
        frp = "/fr/" if p == "/" else "/fr" + p
        alt = (f'<xhtml:link rel="alternate" hreflang="en" href="{SITE_URL}{p}"/>'
               f'<xhtml:link rel="alternate" hreflang="fr" href="{SITE_URL}{frp}"/>')
        urls.append(f"  <url><loc>{SITE_URL}{p}</loc>{alt}</url>")
        urls.append(f"  <url><loc>{SITE_URL}{frp}</loc>{alt}</url>")
    (SITE / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
                                      'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n' + "\n".join(urls) + "\n</urlset>\n")
    n = len(list(FR.rglob("index.html")))
    print(f"{n} French pages written to site/fr/")
    if missing:
        print(f"{len(missing)} strings not translated (left in English):")
        for k, p in list(missing.items())[:30]:
            print(f"  {p}: {k[:90]}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "apply"
    {"extract": extract, "apply": apply}[cmd]()
