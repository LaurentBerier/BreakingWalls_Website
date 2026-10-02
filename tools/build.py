#!/usr/bin/env python3
"""
Breaking Walls site builder.

Converts the raw Squarespace capture in _capture/ (rendered HTML + JSON + assets)
into a clean static site in site/. Run from the repo root:

    python3 tools/build.py

Only needed again if you re-capture the Squarespace site. After the migration,
edit the files in site/ directly.
"""
import hashlib
import html
import json
import os
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse, parse_qs

from bs4 import BeautifulSoup, NavigableString, Comment

ROOT = Path(__file__).resolve().parent.parent
CAP = ROOT / "_capture"
OUT = ROOT / "site"
VIDEO_SRC = ROOT / "_work" / "video"
SITE_URL = "https://www.breakingwalls.co"
WEGLOT_KEY = None  # filled from capture if Weglot is present

# ---------------------------------------------------------------- palette
PAL = {
    "white": "hsl(0 0% 88%)",
    "black": "hsl(0 0% 0%)",
    "accent": "hsl(213 5% 51%)",
    "lightAccent": "hsl(210 3.23% 87.84%)",
    "darkAccent": "hsl(240 2.61% 22.55%)",
    "safeLightAccent": "hsl(213 5% 51%)",
    "safeDarkAccent": "hsl(213 5% 51%)",
    "safeInverseAccent": "hsl(0 0% 88%)",
    "safeInverseLightAccent": "hsl(0 0% 88%)",
    "safeInverseDarkAccent": "hsl(0 0% 88%)",
}
THEMES = {"white", "white-bold", "light", "light-bold", "bright", "bright-inverse",
          "dark", "dark-bold", "black", "black-bold"}

# Squarespace native video systemDataId -> local file name (see _work/video)
VIDEO_MAP = {
    "4fdff358-4c3d-4c2c-a189-b74f1d262f2e": "bw-logo-loop",
    "1e35e3f1-ceae-4c9a-ab75-8161cc31b6d8": "bw-logo-loop",
    "8de44e12-5164-41c0-826f-40fbdedcbd58": "bw-showreel",
    "9ae7aa54-4398-4ab2-bf62-8a7db9fae217": "away-trailer",
    "369d6839-827e-4a37-9f2f-09860f6de6bf": "bw-labs",
    "d7608ce9-ad6b-4a8a-a9f8-ff7499b8e24c": "foldandfly-clip-1",
    "03dc4c27-75c4-43d6-8a3a-b20ddf011323": "foldandfly-clip-2",
    "75473314-a980-4f86-a3db-ee2fd2e1f2e3": "goboom-trailer",
    "1ef23c32-985b-41e1-ab0d-5b9447056a53": "venus-trailer",
}

PAGES = [
    "/", "/home", "/about", "/careers", "/away-faqs-support", "/away-the-survival-series",
    "/foldandflypress", "/disruption", "/venus", "/privacy-policy", "/gifs", "/goboom",
    "/bwlabs", "/foldandfly", "/away-press", "/faqs-1", "/breakingwalls",
    "/blog", "/blog/the-sugar-glider-time-trial-challenge", "/blog/a-canadian-game-sale",
    "/blog/christmas-chaos-arrives-in-go-boom-our-new-project-from-breaking-walls-labs",
    "/blog/welcome", "/news", "/news/upcoming-patch-on-away", "/news/indie-game-of-the-month",
    "/news/new-projects", "/news/away-on-xbox",
]


def capname(p):
    return "_root" if p == "/" else p.strip("/").replace("/", "__")


def ws(s):
    return re.sub(r"\s+", " ", s or "").strip()


# ---------------------------------------------------------------- assets
class Assets:
    def __init__(self):
        man = json.loads((CAP / "manifest.json").read_text())
        self.keys = {}
        for url, key in man["assets"]:
            self.keys[self.norm(url)] = key
        self.used = {}      # key -> public path
        self.byhash = {}    # content md5 -> public path
        self.names = set()

    @staticmethod
    def norm(u):
        if not u:
            return ""
        u = u.strip()
        if u.startswith("//"):
            u = "https:" + u
        u = u.replace("http://", "https://")
        return u.split("?")[0].split("#")[0]

    def is_cdn(self, u):
        return bool(re.search(r"squarespace-cdn\.com|static1\.squarespace\.com", u or ""))

    def local(self, u):
        """Return public path (/assets/...) for a captured asset URL, or None."""
        n = self.norm(u)
        key = self.keys.get(n)
        if not key:
            # some urls are referenced with a different host (static1 vs images cdn)
            for k, v in self.keys.items():
                if k.endswith(urlparse(n).path) and urlparse(n).path.count("/") > 3:
                    key = v
                    break
        if not key:
            return None
        if key in self.used:
            return self.used[key]
        src = CAP / "assets" / key
        if not src.exists():
            return None
        data = src.read_bytes()
        digest = hashlib.md5(data).hexdigest()
        if digest in self.byhash:
            self.used[key] = self.byhash[digest]
            return self.used[key]
        name = unquote(os.path.basename(key))
        name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-").lower() or "file"
        stem, ext = os.path.splitext(name)
        real = sniff_ext(src)
        if not ext or ext == ".jpeg" or (real in (".png", ".jpg", ".gif", ".webp") and ext != real):
            ext = real
        # opaque photographic PNGs become JPEGs (much smaller)
        if ext == ".png" and len(data) > 300_000 and png_is_opaque(src):
            ext = ".jpg"
        # big animated GIFs become looping MP4s (5-10x smaller); see video_for_gif()
        if ext == ".gif" and len(data) > 1_500_000:
            ext = ".mp4"
        folder = "img" if ext in (".png", ".jpg", ".gif", ".webp", ".svg", ".ico", ".avif", ".mp4") else "files"
        cand = f"{stem}{ext}"
        if cand in self.names:
            cand = f"{stem}-{digest[:6]}{ext}"
        self.names.add(cand)
        pub = f"/assets/{folder}/{cand}"
        self.used[key] = pub
        self.byhash[digest] = pub
        dst = OUT / pub.lstrip("/")
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists() or dst.stat().st_size == 0:   # cached between runs
            optimize(src, dst)
        return pub


def sniff_ext(p):
    b = p.read_bytes()[:16]
    if b.startswith(b"\x89PNG"):
        return ".png"
    if b[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if b[:4] == b"GIF8":
        return ".gif"
    if b[:4] == b"RIFF":
        return ".webp"
    if b[:4] == b"%PDF":
        return ".pdf"
    if b.lstrip().startswith(b"<svg") or b.lstrip().startswith(b"<?xml"):
        return ".svg"
    if b[:4] == b"\x00\x00\x01\x00":
        return ".ico"
    return ".bin"


def png_is_opaque(p):
    try:
        from PIL import Image
        im = Image.open(p)
        if im.mode in ("RGB", "L"):
            return True
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            return im.getchannel("A").getextrema()[0] == 255
    except Exception:
        pass
    return False


def optimize(src, dst):
    ext = dst.suffix.lower()
    tmp = dst.with_name(dst.name + ".tmp" + ext)
    if ext == ".mp4":
        import subprocess
        subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(src), "-movflags", "+faststart",
                        "-pix_fmt", "yuv420p", "-vf", "scale='min(1280,iw)':-2,scale=trunc(iw/2)*2:trunc(ih/2)*2",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-an", str(tmp)], check=True)
        os.replace(tmp, dst)
        return
    try:
        if ext in (".jpg", ".png") and sniff_ext(src) in (".jpg", ".png"):
            from PIL import Image
            im = Image.open(src)
            im.load()
            w, h = im.size
            if w > 2200:
                im = im.resize((2200, round(h * 2200 / w)), Image.LANCZOS)
            if ext == ".png":
                im.save(tmp, format="PNG", optimize=True)
            else:
                if im.mode not in ("RGB", "L"):
                    im = im.convert("RGB")
                im.save(tmp, format="JPEG", quality=84, optimize=True, progressive=True)
            if sniff_ext(src) == ext and tmp.stat().st_size > src.stat().st_size:
                shutil.copyfile(src, tmp)
            os.replace(tmp, dst)
            return
    except Exception as e:  # noqa
        print("  ! optimize failed", src.name, e)
    shutil.copyfile(src, tmp)
    os.replace(tmp, dst)


A = None  # Assets instance


def img_src(el):
    for a in ("data-src", "data-image", "src"):
        v = el.get(a)
        if v and not v.startswith("data:"):
            return v
    return None


def asset_or_remote(u):
    if not u:
        return u
    if A.is_cdn(u):
        loc = A.local(u)
        if loc:
            return loc
        return A.norm(u)
    return u


# ---------------------------------------------------------------- colors
def color_from(cfg, fallback="#000"):
    if not cfg:
        return fallback
    t = cfg.get("type")
    if t == "CUSTOM_COLOR" and cfg.get("customColor"):
        c = cfg["customColor"]
        return c if isinstance(c, str) else fallback
    if t == "SITE_PALETTE_COLOR":
        sp = cfg.get("sitePaletteColor") or {}
        base = PAL.get(sp.get("id"), fallback)
        a = sp.get("alpha", 1)
        if a is not None and a < 1 and base.startswith("hsl("):
            return base[:-1] + f" / {a})"
        return base
    return fallback


# ---------------------------------------------------------------- html cleaning
ALLOWED = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "a", "strong", "em", "b", "i", "u", "s",
           "br", "ul", "ol", "li", "span", "blockquote", "code", "pre", "sup", "sub",
           "hr", "table", "thead", "tbody", "tr", "td", "th", "figure", "figcaption", "img", "mark"}


def fix_href(h):
    if not h:
        return h
    h = h.strip()
    if A.is_cdn(h):
        return asset_or_remote(h)
    m = re.match(r"https?://(www\.)?breakingwalls\.co(/[^?#]*)?", h)
    if m:
        h = (m.group(2) or "/")
    if h.startswith("/s/"):
        loc = A.local(SITE_URL + h)
        if loc:
            return loc
    return h


def clean_rich(node):
    """Clean a Squarespace rich text node into lean HTML string."""
    soup = BeautifulSoup(str(node), "lxml")
    body = soup.body or soup
    for c in body.find_all(string=lambda t: isinstance(t, Comment)):
        c.extract()
    for t in body.find_all(["style", "script", "noscript"]):
        t.decompose()
    for t in list(body.find_all(True)):
        if t.name in ("html", "body"):
            continue
        if t.name not in ALLOWED:
            t.unwrap()
            continue
        attrs = {}
        style = t.get("style", "")
        st_out = []
        m = re.search(r"text-align:\s*(left|center|right|justify)", style)
        if m and m.group(1) != "left":
            st_out.append(f"text-align:{m.group(1)}")
        mc = re.search(r"(?:^|;)\s*color:\s*([^;]+)", style)
        if mc and "sqsrte-text-color--custom" in t.get("class", []):
            st_out.append(f"color:{mc.group(1).strip()}")
        if st_out:
            attrs["style"] = ";".join(st_out)
        cls = [c for c in t.get("class", []) if c.startswith("sqsrte-") and c != "sqsrte-text-color--custom"]
        cls = [c.replace("sqsrte-", "rt-") for c in cls]
        if cls:
            attrs["class"] = " ".join(cls)
        if t.name == "a":
            attrs["href"] = fix_href(t.get("href", ""))
            if (attrs["href"] or "").startswith("http"):
                attrs["target"] = "_blank"
                attrs["rel"] = "noopener"
        if t.name == "img":
            attrs["src"] = asset_or_remote(img_src(t))
            attrs["alt"] = t.get("alt", "")
            attrs["loading"] = "lazy"
        t.attrs = attrs
        if t.name == "span" and not attrs:
            t.unwrap()
    out = "".join(str(c) for c in body.children)
    out = re.sub(r"<p>\s*</p>", "<p>&nbsp;</p>", out)
    return out.strip()


# ---------------------------------------------------------------- icons
ICONS = {
    "url": '<path d="M7.1 3c2.6 1.9 5.3 5.8 6.3 7.9 1-2.1 3.7-6 6.3-7.9 1.9-1.4 4.9-2.4 4.9 1 0 .7-.4 5.7-.6 6.5-.8 2.9-3.7 3.6-6.3 3.2 4.5.8 5.7 3.3 3.2 5.9-4.7 4.8-6.7-1.2-7.3-2.7l-.2-.6-.2.6c-.5 1.5-2.6 7.5-7.3 2.7-2.5-2.6-1.3-5.1 3.2-5.9-2.6.4-5.5-.3-6.3-3.2C2.6 9.7 2.2 4.7 2.2 4 2.2.6 5.2 1.6 7.1 3z" transform="translate(-1.4 0)"/>',
    "tiktok": '<path d="M16.6 2h-3.4v13.4a2.9 2.9 0 1 1-2-2.8V9.2a6.3 6.3 0 1 0 5.4 6.2V8.6a8 8 0 0 0 4.6 1.5V6.7a4.6 4.6 0 0 1-4.6-4.7z"/>',
    "youtube": '<path d="M22.5 6.9a2.7 2.7 0 0 0-1.9-1.9C18.9 4.5 12 4.5 12 4.5s-6.9 0-8.6.5A2.7 2.7 0 0 0 1.5 6.9 28.6 28.6 0 0 0 1 12a28.6 28.6 0 0 0 .5 5.1 2.7 2.7 0 0 0 1.9 1.9c1.7.5 8.6.5 8.6.5s6.9 0 8.6-.5a2.7 2.7 0 0 0 1.9-1.9A28.6 28.6 0 0 0 23 12a28.6 28.6 0 0 0-.5-5.1zM9.8 15.2V8.8l5.7 3.2z"/>',
    "discord": '<path d="M19.6 5.3A17.6 17.6 0 0 0 15.3 4l-.6 1.1a16.3 16.3 0 0 0-5 0L9.1 4a17.5 17.5 0 0 0-4.4 1.3C2 9.4 1.2 13.4 1.6 17.3a17.7 17.7 0 0 0 5.4 2.7l1.2-1.9a11.5 11.5 0 0 1-1.8-.9l.4-.3a12.6 12.6 0 0 0 10.8 0l.4.3c-.6.3-1.2.6-1.8.9l1.2 1.9a17.6 17.6 0 0 0 5.4-2.7c.5-4.5-.8-8.5-3.2-12zM8.5 14.9c-1 0-1.9-1-1.9-2.2s.8-2.2 1.9-2.2 1.9 1 1.9 2.2-.8 2.2-1.9 2.2zm7 0c-1 0-1.9-1-1.9-2.2s.8-2.2 1.9-2.2 1.9 1 1.9 2.2-.8 2.2-1.9 2.2z"/>',
    "instagram": '<path d="M12 7.2A4.8 4.8 0 1 0 16.8 12 4.8 4.8 0 0 0 12 7.2zm0 7.9a3.1 3.1 0 1 1 3.1-3.1 3.1 3.1 0 0 1-3.1 3.1zm6.1-8.1a1.1 1.1 0 1 1-1.1-1.1 1.1 1.1 0 0 1 1.1 1.1zM21.3 8.1a5.5 5.5 0 0 0-1.5-3.9 5.6 5.6 0 0 0-3.9-1.5c-1.6-.1-6.3-.1-7.8 0a5.5 5.5 0 0 0-3.9 1.5A5.5 5.5 0 0 0 2.7 8c-.1 1.6-.1 6.3 0 7.8a5.5 5.5 0 0 0 1.5 3.9 5.6 5.6 0 0 0 3.9 1.5c1.6.1 6.3.1 7.8 0a5.5 5.5 0 0 0 3.9-1.5 5.6 5.6 0 0 0 1.5-3.9c.1-1.6.1-6.2 0-7.7zm-2 9.5a3.2 3.2 0 0 1-1.8 1.8c-1.3.5-4.2.4-5.5.4s-4.3.1-5.5-.4a3.2 3.2 0 0 1-1.8-1.8c-.5-1.3-.4-4.2-.4-5.5s-.1-4.3.4-5.5a3.2 3.2 0 0 1 1.8-1.8c1.3-.5 4.2-.4 5.5-.4s4.3-.1 5.5.4a3.2 3.2 0 0 1 1.8 1.8c.5 1.3.4 4.2.4 5.5s.1 4.3-.4 5.5z"/>',
    "facebook": '<path d="M22 12a10 10 0 1 0-11.6 9.9v-7H7.9V12h2.5V9.8c0-2.5 1.5-3.9 3.8-3.9a15.4 15.4 0 0 1 2.2.2v2.5h-1.3c-1.2 0-1.6.8-1.6 1.6V12h2.8l-.4 2.9h-2.3v7A10 10 0 0 0 22 12z"/>',
    "twitter": '<path d="M17.8 3h3.1l-6.8 7.8 8 10.6h-6.3l-4.9-6.4L5.3 21.4H2.2l7.3-8.3L1.8 3h6.4l4.4 5.9zm-1.1 16.5h1.7L7.4 4.8H5.6z"/>',
    "linkedin": '<path d="M20.4 20.5h-3.6v-5.6c0-1.3 0-3-1.8-3s-2.1 1.4-2.1 2.9v5.7H9.3V9h3.4v1.6a3.8 3.8 0 0 1 3.4-1.9c3.6 0 4.3 2.4 4.3 5.5zM5.3 7.4a2.1 2.1 0 1 1 2.1-2.1 2.1 2.1 0 0 1-2.1 2.1zm1.8 13.1H3.5V9h3.6zM22.2 0H1.8A1.8 1.8 0 0 0 0 1.7v20.6A1.8 1.8 0 0 0 1.8 24h20.4a1.8 1.8 0 0 0 1.8-1.7V1.7A1.8 1.8 0 0 0 22.2 0z"/>',
    "steam": '<path d="M12 2a10 10 0 0 0-10 9.2l5.4 2.2a2.8 2.8 0 0 1 1.6-.5h.2l2.4-3.5v-.1a3.8 3.8 0 1 1 3.8 3.8h-.1l-3.4 2.4v.1a2.8 2.8 0 0 1-5.6.5L2.4 14.6A10 10 0 1 0 12 2zM8.3 17.2l-1.2-.5a2.1 2.1 0 1 0 1.1-2.9l1.3.5a1.5 1.5 0 1 1-1.2 2.9zm9.1-7.9a2.5 2.5 0 1 0-2.5 2.5 2.5 2.5 0 0 0 2.5-2.5zm-4.4 0a1.9 1.9 0 1 1 1.9 1.9 1.9 1.9 0 0 1-1.9-1.9z"/>',
    "email": '<path d="M2 5h20v14H2zm2 2v.5l8 5 8-5V7zm16 2.8-8 5-8-5V17h16z"/>',
}


def icon_for(label, href):
    l = (label or "").lower() + " " + (href or "").lower()
    for k in ["tiktok", "youtube", "discord", "instagram", "facebook", "twitter", "linkedin", "steam"]:
        if k in l:
            return k
    if "x.com" in l:
        return "twitter"
    if "bsky" in l:
        return "url"
    if "mailto" in l:
        return "email"
    return "url"


def social_links(links):
    out = []
    for label, href in links:
        k = icon_for(label, href)
        name = {"url": "Bluesky"}.get(k, k.capitalize()) if "bsky" in (href or "") or k != "url" else (label or "Link")
        out.append(f'<a class="soc" href="{html.escape(href)}" target="_blank" rel="noopener" aria-label="{html.escape(name)}">'
                   f'<svg viewBox="0 0 24 24" aria-hidden="true">{ICONS[k]}</svg></a>')
    return "".join(out)


# ---------------------------------------------------------------- blocks
def block_type(b):
    for c in b.get("class", []):
        if c.startswith("sqs-block-") and c not in ("sqs-block-website-component", "sqs-block-content"):
            return c[len("sqs-block-"):]
    return "unknown"


def youtube_from(s):
    s = html.unescape(s or "")
    m = re.search(r"(?:youtube\.com/embed/|youtube\.com/watch\?v=|youtu\.be/|youtube\.com%2Fembed%2F|watch%3Fv%3D)([A-Za-z0-9_-]{11})", s)
    if m:
        return m.group(1)
    return None


def vimeo_from(s):
    s = html.unescape(unquote(s or ""))
    m = re.search(r"vimeo\.com/(?:video/)?(\d+)", s)
    return m.group(1) if m else None


def render_block(b, ctx):
    t = block_type(b)
    if t == "html":
        c = b.select_one(".sqs-html-content")
        style = ""
        if "sqs-background-enabled" in b.get("class", []):
            css = " ".join(x.get_text() for x in b.find_all("style"))
            pad = re.search(r"--tweak-text-block-padding:\s*([^;]+);", css)
            rad = re.search(r"--tweak-text-block-radius:\s*([^;]+);", css)
            bgc = re.search(r"--tweak-text-block-background-color:\s*([^;]+);", css)
            blur = re.search(r"--blur-value:\s*blur\((\d+)px\)", css)
            parts = []
            if bgc:
                v = bgc.group(1).strip()
                mm = re.match(r"hsla\(var\(--([\w]+)-hsl\),\s*([\d.]+)\)", v)
                if mm and mm.group(1) in PAL:
                    v = PAL[mm.group(1)][:-1] + f" / {mm.group(2)})"
                parts.append(f"background:{v}")
                if blur and blur.group(1) != "0":
                    parts.append(f"backdrop-filter:blur({blur.group(1)}px);-webkit-backdrop-filter:blur({blur.group(1)}px)")
            else:
                parts.append("background:var(--white);--c-text:var(--black);--c-head:var(--black);color:var(--black)")
            if pad and pad.group(1).strip() != "initial":
                parts.append(f"padding:{pad.group(1).strip()}")
            if rad:
                parts.append(f"border-radius:{rad.group(1).strip()}")
            style = f' style="{";".join(parts)};height:100%;display:flex;flex-direction:column;justify-content:center"'
        return "text", f'<div class="rt"{style}>{clean_rich(c) if c else ""}</div>'
    if t == "image":
        img = b.find("img")
        if not img:
            return "image", ""
        src = asset_or_remote(img_src(img))
        alt = html.escape(img.get("alt", ""), quote=True)
        fill = bool(b.select_one(".content-fill")) or (b.select_one("[data-is-image-stretched='true']") is not None)
        fp = img.get("data-image-focal-point") or "0.5,0.5"
        try:
            fx, fy = [float(x) * 100 for x in fp.split(",")]
        except Exception:
            fx, fy = 50, 50
        dims = img.get("data-image-dimensions", "")
        wh = ""
        if re.match(r"\d+x\d+", dims):
            w, h = dims.split("x")
            wh = f' width="{w}" height="{h}"'
        hpos = "center"
        root = b.select_one(".image-block-outer-wrapper")
        for c in (root.get("class", []) if root else []):
            mm = re.match(r"image-position-(left|center|right)", c)
            if mm:
                hpos = mm.group(1)
        if fill:
            pos = f' style="object-position:{fx:.0f}% {fy:.0f}%"' if (fx, fy) != (50, 50) else ""
        else:
            vpos = {"flex-start": "top", "flex-end": "bottom"}.get((ctx or {}).get("valign", {}).get(b.get("id", "").replace("block-", ""), "center") if isinstance(ctx, dict) else "center", "center")
            pos = f' style="object-position:{hpos} {vpos}"' if (hpos, vpos) != ("center", "center") else ""
        tag = f'<img src="{src}" alt="{alt}"{wh} loading="lazy"{pos}>'
        a = b.find("a", href=True)
        if a:
            href = fix_href(a["href"])
            tgt = ' target="_blank" rel="noopener"' if href.startswith("http") or a.get("target") == "_blank" else ""
            tag = f'<a href="{html.escape(href)}"{tgt}>{tag}</a>'
        cap = b.select_one(".image-caption, figcaption")
        caph = f'<div class="cap">{clean_rich(cap)}</div>' if cap and ws(cap.get_text()) else ""
        return ("image fill" if fill else "image fit"), f'<figure class="im">{tag}</figure>{caph}'
    if t == "button":
        a = b.find("a")
        if not a:
            return "button", ""
        href = fix_href(a.get("href", "#"))
        cont = b.select_one(".sqs-block-button-container")
        typ = (cont.get("data-button-type") if cont else None) or "primary"
        size = (cont.get("data-button-size") if cont else None) or "medium"
        align = "center"
        if cont:
            for c in cont.get("class", []):
                m = re.match(r"sqs-block-button-container--(left|center|right)", c)
                if m:
                    align = m.group(1)
        stretched = cont is not None and "sqs-stretched" in cont.get("class", [])
        tgt = ' target="_blank" rel="noopener"' if a.get("target") == "_blank" or href.startswith("http") else ""
        return f"button al-{align}" + (" stretch" if stretched else ""), \
            f'<div class="bw" style="text-align:{align}"><a class="btn btn-{typ} btn-{size}" href="{html.escape(href)}"{tgt}>{html.escape(ws(a.get_text()))}</a></div>'
    if t == "socialaccountlinks":
        links = [(a.get("aria-label"), a.get("href")) for a in b.select("a[href]")]
        al = "center"
        o = b.select_one(".sqs-svg-icon--outer")
        if o:
            for c in o.get("class", []):
                m = re.match(r"social-icon-alignment-(left|center|right)", c)
                if m:
                    al = m.group(1)
        return f"social al-{al}", f'<nav class="socials" style="justify-content:{ {"left": "flex-start", "right": "flex-end"}.get(al, "center")}">{social_links(links)}</nav>'
    if t == "video":
        w = b.select_one(".sqs-video-wrapper")
        data = (w.get("data-html") if w else "") or str(b)
        yt = youtube_from(data)
        vm = vimeo_from(data)
        if yt:
            src = f"https://www.youtube-nocookie.com/embed/{yt}"
        elif vm:
            src = f"https://player.vimeo.com/video/{vm}"
        else:
            cv = b.select_one("[data-config-video]")
            if cv:
                v = json.loads(cv["data-config-video"])
                name = VIDEO_MAP.get(v.get("systemDataId"))
                try:
                    sett = json.loads(cv.get("data-config-settings") or "{}")
                except Exception:
                    sett = {}
                flags = " ".join(k for k, on in [("autoplay", sett.get("autoPlay")), ("muted", sett.get("muted") or sett.get("autoPlay")), ("loop", sett.get("loop"))] if on)
                ctrl = "" if sett.get("autoPlay") else " controls"
                if name:
                    return "video", f'<div class="vid"><video src="/assets/video/{name}.mp4" poster="/assets/video/{name}-poster.jpg" {flags}{ctrl} playsinline preload="metadata"></video></div>'
            nv = b.select_one("[data-config-native-video]")
            if nv:
                v = json.loads(nv["data-config-native-video"])
                name = VIDEO_MAP.get(v.get("systemDataId"))
                if name:
                    return "video", f'<div class="vid"><video src="/assets/video/{name}.mp4" poster="/assets/video/{name}-poster.jpg" controls playsinline preload="none"></video></div>'
            return "video", "<!-- video embed not recognised -->"
        title = html.escape((w.get("data-provider-name") if w else None) or "Video")
        return "video", f'<div class="vid"><iframe src="{src}" title="{title}" loading="lazy" allow="autoplay; fullscreen; picture-in-picture" allowfullscreen></iframe></div>'
    if t == "form":
        sc = b.select_one("script.sqs-form-block-context")
        try:
            f = json.loads(sc.string)
        except Exception:
            f = {"formFields": [], "formSubmitButtonText": "Send"}
        fields = []
        for fl in f.get("formFields", []):
            ty = fl.get("type")
            lab = html.escape(fl.get("title", ""))
            desc = html.escape(fl.get("description", "") or "")
            req = " required" if fl.get("required") else ""
            name = re.sub(r"[^a-z0-9]+", "_", fl.get("title", "field").lower()).strip("_")
            d = f'<small>{desc}</small>' if desc else ""
            if ty == "textarea":
                inp = f'<textarea name="{name}" rows="5"{req}></textarea>'
            elif ty == "email":
                inp = f'<input type="email" name="email"{req}>'
            elif ty == "name":
                fields.append(f'<fieldset class="cf-name"><legend>{lab}</legend>'
                              f'<label><span>First Name {"<em>(required)</em>" if req else ""}</span><input type="text" name="first_name" autocomplete="given-name"{req}></label>'
                              f'<label><span>Last Name {"<em>(required)</em>" if req else ""}</span><input type="text" name="last_name" autocomplete="family-name"{req}></label></fieldset>')
                continue
            else:
                inp = f'<input type="text" name="{name}"{req}>'
            fields.append(f'<label><span>{lab} {"<em>(required)</em>" if req else ""}</span>{d}{inp}</label>')
        btn = html.escape(f.get("formSubmitButtonText") or "Send")
        ok = clean_rich(BeautifulSoup((f.get("formSubmissionMessage") or {}).get("html", "Thank you!"), "lxml"))
        card = " card" if "sqs-background-enabled" in b.get("class", []) else ""
        return "form", (f'<form class="cform{card}" method="POST" data-form-endpoint>'
                        f'{"".join(fields)}<button class="btn btn-primary btn-medium" type="submit">{btn}</button>'
                        f'<div class="cform-ok" hidden>{ok}</div></form>')
    if t == "instagram":
        return "embed", '<p class="embed-note"><a class="btn btn-secondary btn-small" href="https://www.instagram.com/breakingwallsstudio" target="_blank" rel="noopener">Follow us on Instagram</a></p>'
    if t == "twitter":
        return "embed", '<p class="embed-note"><a class="btn btn-secondary btn-small" href="https://twitter.com/BWallsStudio" target="_blank" rel="noopener">Follow us on X</a></p>'
    if t == "spacer":
        return "spacer", ""
    if t == "horizontalrule":
        return "hr", "<hr>"
    if t == "gallery":
        imgs = dedupe_imgs(b.find_all("img"))
        items = "".join(f'<figure><img src="{s}" alt="{html.escape(a)}" loading="lazy"></figure>' for s, a, _ in imgs)
        return "gallery", f'<div class="gal-grid cols-3">{items}</div>'
    if t in ("code", "embed"):
        c = b.select_one(".sqs-block-content")
        raw = "".join(str(x) for x in c.children) if c else ""
        return "code", raw
    if t == "quote":
        return "text", f'<blockquote class="rt">{clean_rich(b.select_one("blockquote") or b)}</blockquote>'
    print("   ? unhandled block", t, ctx)
    return "unknown", f"<!-- unhandled block: {t} -->"


def dedupe_imgs(imgs):
    seen, out = set(), []
    for i in imgs:
        s = img_src(i)
        if not s:
            continue
        n = A.norm(s)
        if n in seen:
            continue
        seen.add(n)
        link = None
        a = i.find_parent("a")
        if a and a.get("href"):
            link = fix_href(a["href"])
        out.append((asset_or_remote(s), i.get("alt", ""), link))
    return out


# ---------------------------------------------------------------- fluid css
def convert_fluid_css(css):
    css = re.sub(r"@media \(max-width: 767px\) \{\s*\}", "", css)
    css = css.replace(".sqs-block-alignment-wrapper", ".blk-al").replace(".sqs-block", ".blk")
    css = re.sub(r"\s+", " ", css)
    css = re.sub(r"\s*([{};:,])\s*", r"\1", css)
    return css.strip()


# ---------------------------------------------------------------- sections
def section_styles(sec):
    raw = sec.get("data-current-styles") or "{}"
    try:
        return json.loads(raw)
    except Exception:
        try:
            return json.loads(re.sub(r"\s+", " ", raw))
        except Exception:
            return {}


def section_context(sec):
    try:
        return json.loads(sec.get("data-current-context") or "{}")
    except Exception:
        return {}


def render_background(sec, st, theme):
    bg = sec.select_one(".section-background")
    mode = st.get("backgroundMode")
    overlay = st.get("imageOverlayOpacity")
    parts = []
    if bg is None:
        bg = sec
    nv = bg.select_one("[data-config-native-video]")
    vbg = bg.select_one(".sqs-video-background, [data-config-video], .section-background-video")
    img = None
    for i in bg.find_all("img"):
        if img_src(i):
            img = i
            break
    gen_el = sec.select_one("[data-generative-config]")
    gen_cfg = None
    if mode == "generative" or (gen_el and not img and not nv):
        gen_cfg = st.get("generative")
        if not gen_cfg and gen_el:
            try:
                gen_cfg = json.loads(re.sub(r"\s+", " ", gen_el["data-generative-config"]))
            except Exception:
                gen_cfg = None
    if nv:
        v = json.loads(nv["data-config-native-video"])
        name = VIDEO_MAP.get(v.get("systemDataId"))
        rate = nv.get("data-config-playback-speed") or "1"
        if name:
            parts.append(f'<video class="bg-media" src="/assets/video/{name}.mp4" poster="/assets/video/{name}-poster.jpg" '
                         f'autoplay muted loop playsinline data-rate="{rate}"></video>')
    elif mode == "video" or vbg is not None:
        ctxv = (section_context(sec).get("video") or {})
        url = ctxv.get("url") or (vbg.get("data-config-url") if vbg else "") or ""
        yt = youtube_from(url)
        if yt:
            parts.append(f'<div class="bg-media bg-yt"><iframe src="https://www.youtube-nocookie.com/embed/{yt}?autoplay=1&mute=1&loop=1&playlist={yt}&controls=0&showinfo=0&modestbranding=1&playsinline=1" '
                         f'title="Background video" allow="autoplay" tabindex="-1"></iframe></div>')
        if img:
            parts.insert(0, f'<img class="bg-media" src="{asset_or_remote(img_src(img))}" alt="" loading="lazy">')
    elif gen_cfg and mode == "generative":
        parts.append(render_generative(gen_cfg))
    elif img:
        fp = img.get("data-image-focal-point") or "0.5,0.5"
        try:
            fx, fy = [float(x) * 100 for x in fp.split(",")]
        except Exception:
            fx, fy = 50, 50
        parts.append(f'<img class="bg-media" src="{asset_or_remote(img_src(img))}" alt="" loading="lazy" style="object-position:{fx:.0f}% {fy:.0f}%">')
    if parts and overlay and mode != "generative":
        parts.append(f'<div class="bg-overlay" style="opacity:{overlay}"></div>')
    if not parts:
        return ""
    return f'<div class="sec-bg">{"".join(parts)}</div>'


def render_generative(g):
    t = g.get("type", "gradient")
    c1 = color_from(g.get("startColor") or g.get("color1"), PAL["darkAccent"])
    c2 = color_from(g.get("endColor") or g.get("color2"), PAL["accent"])
    c3 = color_from(g.get("color3"), c2)
    c4 = color_from(g.get("color4"), c1)
    inv = " inv" if g.get("invertColors") else ""
    gbg = color_from(g.get("backgroundColor"), c1)
    style = f"--g1:{c1};--g2:{c2};--g3:{c3};--g4:{c4};--gbg:{gbg}"
    return f'<div class="bg-media gen gen-{t}{inv}" style="{style}" aria-hidden="true"></div>'


def section_theme(sec):
    t = sec.get("data-section-theme") or ""
    if t not in THEMES:
        st = section_styles(sec)
        t = st.get("sectionTheme") if st.get("sectionTheme") in THEMES else ""
    return t or "white"


def render_fluid_section(sec, ctx):
    st = section_styles(sec)
    theme = section_theme(sec)
    sid = sec.get("data-section-id", "x")
    classes = ["sec", f"t-{theme}"]
    for c in sec.get("class", []):
        if c.startswith(("section-height--", "background-width--", "vertical-alignment--", "content-width--")):
            classes.append(c.replace("section-height--", "h-").replace("background-width--", "bw-")
                           .replace("vertical-alignment--", "va-").replace("content-width--", "cw-"))
    sstyle = sec.get("style", "")
    m = re.search(r"min-height:\s*([\d.]+)vh", sstyle)
    style = f' style="min-height:{m.group(1)}vh"' if m else ""
    cw = sec.select_one(".content-wrapper")
    pad = ""
    if cw and cw.get("style"):
        p = ws(cw["style"])
        pt = re.search(r"padding-top:\s*([^;]+);", p)
        pb = re.search(r"padding-bottom:\s*([^;]+);", p)
        pad = ";".join(x for x in [f"padding-top:{pt.group(1)}" if pt else "", f"padding-bottom:{pb.group(1)}" if pb else ""] if x)
    fe = sec.select_one("[data-fluid-engine]")
    css = ""
    inner = ""
    if fe:
        stl = fe.find("style", recursive=False)
        css = convert_fluid_css(stl.string or "") if stl else ""
        grid = fe.select_one(".fluid-engine")
        gcls = " ".join(c for c in grid.get("class", []) if c.startswith("fe-")) if grid else ""
        blocks = []
        valign = {}
        for mm in re.finditer(r"\.fe-block-([\w-]+) \.blk\{justify-content:([\w-]+);?\}", css):
            valign[mm.group(1)] = mm.group(2)   # later (desktop) rules win
        bctx = {"path": ctx, "valign": valign}
        for fb in (grid.find_all("div", class_="fe-block", recursive=False) if grid else []):
            fbc = " ".join(c for c in fb.get("class", []) if c.startswith("fe-block"))
            b = fb.select_one(".sqs-block")
            if not b:
                continue
            kind, h = render_block(b, bctx)
            blocks.append(f'<div class="{fbc}"><div class="blk b-{kind.split()[0]} {" ".join(kind.split()[1:])}"><div class="blk-al">{h}</div></div></div>')
        inner = f'<div class="fluid-engine {gcls}">{"".join(blocks)}</div>'
    bg = render_background(sec, st, theme)
    return (f'<section class="{" ".join(classes)}" id="s-{sid}"{style}>{bg}'
            f'<div class="sec-in"{(" style=" + chr(34) + pad + chr(34)) if pad else ""}>{inner}</div>'
            f'{"<style>" + css + "</style>" if css else ""}</section>')


def render_gallery_section(sec, ctx):
    theme = section_theme(sec)
    ctl = sec.select_one("[data-controller^=Gallery]")
    kind = (ctl.get("data-controller") if ctl else "GalleryGrid").replace("Gallery", "").lower()
    props = {}
    el = sec.select_one("[data-props]")
    if el:
        try:
            props = json.loads(ws(el["data-props"]))
        except Exception:
            props = {}
    imgs = dedupe_imgs(sec.select(".gallery img, img"))
    figs = []
    for s, a, link in imgs:
        im = f'<img src="{s}" alt="{html.escape(a, quote=True)}" loading="lazy">'
        if link:
            im = f'<a href="{html.escape(link)}">{im}</a>'
        figs.append(f'<figure>{im}</figure>')
    if kind in ("slideshowsimple", "slideshow", "slideshowfullscreen", "fullscreenslideshow", "slideshowbanner"):
        kind = "slideshow"
    if kind == "reel":
        body = f'<div class="gal-reel" data-reel><div class="reel-track">{"".join(figs)}</div><button class="g-prev" aria-label="Previous">&larr;</button><button class="g-next" aria-label="Next">&rarr;</button></div>'
    elif kind == "slideshow":
        body = f'<div class="gal-slides" data-slides><div class="slides-track">{"".join(figs)}</div><button class="g-prev" aria-label="Previous">&larr;</button><button class="g-next" aria-label="Next">&rarr;</button></div>'
    elif kind == "masonry":
        cols = props.get("numColumns") or 3
        gut = props.get("gutter", 20)
        body = f'<div class="gal-masonry" style="--cols:{cols};--gut:{gut}px">{"".join(figs)}</div>'
    else:
        cols = props.get("numColumns") or (ctl.get("data-columns") if ctl else None) or 3
        gut = props.get("gutter", ctl.get("data-gutter") if ctl else 20) or 20
        ar = {"square": "1/1", "four-three": "4/3", "three-four-vertical": "3/4", "widescreen": "16/9",
              "three-two": "3/2", "two-three-vertical": "2/3", "standard": "4/3"}.get(props.get("aspectRatio") or (ctl.get("data-aspect-ratio") if ctl else ""), "auto")
        body = f'<div class="gal-grid" style="--cols:{cols};--gut:{gut}px;--ar:{ar}">{"".join(figs)}</div>'
    width = props.get("width", "")
    wcls = " gal-full" if width in ("full", "full-bleed") else ""
    hcls = [c.replace("section-height--", "h-") for c in sec.get("class", []) if c.startswith("section-height--")]
    vh = props.get("viewportHeight")
    style = f' style="--vh:{vh}vh"' if vh else ""
    return f'<section class="sec sec-gallery t-{theme} {" ".join(hcls)}{wcls}"{style}><div class="gal-wrap">{body}</div></section>'


def render_useritems_section(sec, ctx):
    theme = section_theme(sec)
    ul = sec.select_one("[data-current-context]") if not sec.select_one("ul[data-current-context]") else sec.select_one("ul[data-current-context]")
    try:
        data = json.loads(html.unescape(ul["data-current-context"]))
    except Exception:
        data = {"userItems": []}
    title = sec.select_one(".list-section-title")
    th = f'<div class="ui-title rt">{clean_rich(title)}</div>' if title else ""
    cards = []
    for it in data.get("userItems", []):
        img = (it.get("image") or {}).get("assetUrl")
        src = asset_or_remote(img) if img else ""
        btn = it.get("button") or {}
        bh = ""
        if btn.get("buttonText"):
            bh = f'<a class="btn btn-primary btn-small" href="{html.escape(fix_href(btn.get("buttonLink", "#")))}"{" target=_blank rel=noopener" if btn.get("buttonNewWindow") else ""}>{html.escape(btn["buttonText"])}</a>'
        fp = it.get("mediaFocalPoint") or {"x": .5, "y": .5}
        cards.append(
            f'<li class="ui-card">' + (f'<div class="ui-media"><img src="{src}" alt="{html.escape(it.get("imageAltText", ""), quote=True)}" loading="lazy" style="object-position:{fp.get("x", .5)*100:.0f}% {fp.get("y", .5)*100:.0f}%"></div>' if src else "")
            + f'<div class="ui-body"><h3>{html.escape(it.get("title", ""))}</h3><div class="rt">{clean_rich(BeautifulSoup(it.get("description", ""), "lxml"))}</div>{bh}</div></li>')
    return f'<section class="sec sec-list t-{theme}"><div class="sec-in wrap">{th}<ul class="ui-list">{"".join(cards)}</ul></div></section>'


def render_cdk_section(sec, ctx):
    theme = section_theme(sec)
    items = []
    for a in sec.select("a[href]"):
        img = a.find("img") or (a.find_parent().find("img") if a.find_parent() else None)
        src = asset_or_remote(img_src(img)) if img else ""
        items.append(f'<li><a href="{html.escape(fix_href(a["href"]))}">'
                     + (f'<img src="{src}" alt="" loading="lazy">' if src else "")
                     + f'<span>{html.escape(ws(a.get_text(" ")))}</span></a></li>')
    gen = sec.select_one("[data-generative-config]")
    bg = ""
    if gen:
        try:
            bg = f'<div class="sec-bg">{render_generative(json.loads(ws(gen["data-generative-config"])))}</div>'
        except Exception:
            bg = ""
    return f'<section class="sec sec-plist t-{theme}">{bg}<div class="sec-in wrap"><ul class="plist">{"".join(items)}</ul></div></section>'


def render_section(sec, ctx):
    cls = sec.get("class", [])
    if sec.has_attr("data-fluid-engine-section"):
        return render_fluid_section(sec, ctx)
    if "gallery-section" in cls:
        return render_gallery_section(sec, ctx)
    if "user-items-list-section" in cls:
        return render_useritems_section(sec, ctx)
    if "cdk-section" in cls:
        return render_cdk_section(sec, ctx)
    return None  # collection sections handled separately


# ---------------------------------------------------------------- classic layout (blog posts)
def render_classic_layout(layout, ctx):
    out = []
    for row in layout.find_all("div", class_="sqs-row", recursive=False):
        out.append(render_row(row, ctx))
    return "".join(out)


def render_row(row, ctx):
    cols = []
    for col in row.find_all("div", class_="col", recursive=False):
        span = 12
        for c in col.get("class", []):
            m = re.match(r"span-(\d+)", c)
            if m:
                span = int(m.group(1))
        inner = []
        for ch in col.find_all("div", recursive=False):
            if "sqs-row" in ch.get("class", []):
                inner.append(render_row(ch, ctx))
            elif "sqs-block" in ch.get("class", []):
                kind, h = render_block(ch, ctx)
                inner.append(f'<div class="cblk b-{kind.split()[0]} {" ".join(kind.split()[1:])}">{h}</div>')
        cols.append(f'<div class="ccol" style="--span:{span}">{"".join(inner)}</div>')
    return f'<div class="crow">{"".join(cols)}</div>'


# ---------------------------------------------------------------- blog
def fmt_date(ms):
    import datetime
    d = datetime.datetime.utcfromtimestamp(int(ms) / 1000)
    return d.strftime("%b %-d, %Y"), d.strftime("%Y-%m-%d")


def blog_items():
    j = json.loads((CAP / "json" / "blog.json").read_text())
    return j.get("items", [])


def render_blog_list(soup):
    items = blog_items()
    # map item thumbnails from the rendered list page
    thumbs = {}
    for art in soup.select("article"):
        a = art.find("a", href=True)
        img = art.find("img")
        if a and img:
            thumbs[a["href"]] = asset_or_remote(img_src(img))
    cards = []
    for it in items:
        url = it["fullUrl"]
        src = thumbs.get(url) or (asset_or_remote(it.get("assetUrl")) if it.get("assetUrl") else "")
        human, iso = fmt_date(it["publishOn"])
        cats = " · ".join(it.get("categories") or [])
        ex = clean_rich(BeautifulSoup(it.get("excerpt") or "", "lxml")) if it.get("excerpt") else ""
        cards.append(
            f'<article class="post-card"><a class="pc-media" href="{url}">' + (f'<img src="{src}" alt="" loading="lazy">' if src else "") + '</a>'
            f'<div class="pc-body"><p class="meta">{html.escape(cats)}</p><h2><a href="{url}">{html.escape(it["title"])}</a></h2>'
            f'<div class="rt ex">{ex}</div><p class="meta"><time datetime="{iso}">{human}</time></p>'
            f'<a class="more" href="{url}">Read more</a></div></article>')
    return f'<section class="sec t-white blog-list"><div class="sec-in wrap"><div class="posts">{"".join(cards)}</div></div></section>'


def render_blog_post(soup, path):
    it = next((i for i in blog_items() if i["fullUrl"] == path), None)
    w = soup.select_one(".blog-item-wrapper")
    title = ws(w.select_one(".entry-title").get_text()) if w else (it or {}).get("title", "")
    human, iso = fmt_date(it["publishOn"]) if it else ("", "")
    author = ((it or {}).get("author") or {}).get("displayName", "")
    cats = (it or {}).get("categories") or []
    tags = (it or {}).get("tags") or []
    layout = w.select_one(".blog-item-content .sqs-layout") if w else None
    body = render_classic_layout(layout, path) if layout else ""
    items = blog_items()
    idx = next((k for k, i in enumerate(items) if i["fullUrl"] == path), None)
    nav = ""
    if idx is not None:
        prev_ = items[idx + 1] if idx + 1 < len(items) else None
        next_ = items[idx - 1] if idx > 0 else None
        nav = '<nav class="post-nav">' + (f'<a class="pn-prev" href="{prev_["fullUrl"]}"><small>Previous</small>{html.escape(prev_["title"])}</a>' if prev_ else "<span></span>") \
              + (f'<a class="pn-next" href="{next_["fullUrl"]}"><small>Next</small>{html.escape(next_["title"])}</a>' if next_ else "<span></span>") + '</nav>'
    tagh = "".join(f'<span class="tag">{html.escape(t)}</span>' for t in tags)
    return (f'<section class="sec t-white blog-post"><div class="sec-in wrap narrow"><article>'
            f'<p class="meta">{html.escape(" · ".join(cats))}</p><h1>{html.escape(title)}</h1>'
            f'<p class="meta"><time datetime="{iso}">{human}</time>{(" · Written by " + html.escape(author)) if author else ""}</p>'
            f'<div class="post-body">{body}</div><div class="tags">{tagh}</div></article>{nav}'
            f'<p><a class="more" href="/blog">&larr; All posts</a></p></div></section>')


# ---------------------------------------------------------------- header / footer
def build_header(soup):
    h = soup.select_one("header")
    if not h:
        return ""
    logo = h.select_one(".header-display-desktop .header-title-logo img") or h.select_one(".header-title-logo img")
    logo_src = asset_or_remote(img_src(logo)) if logo else ""
    nav = []
    for item in h.select(".header-display-desktop .header-nav-list > .header-nav-item"):
        if "header-nav-item--folder" in item.get("class", []):
            title = ws(item.select_one(".header-nav-folder-title-text").get_text())
            subs = "".join(f'<li><a href="{html.escape(fix_href(a["href"]))}">{html.escape(ws(a.get_text()))}</a></li>'
                           for a in item.select(".header-nav-folder-item a"))
            nav.append(f'<li class="has-sub"><button type="button" aria-expanded="false">{html.escape(title)}</button><ul class="sub">{subs}</ul></li>')
        else:
            a = item.find("a")
            nav.append(f'<li><a href="{html.escape(fix_href(a["href"]))}">{html.escape(ws(a.get_text()))}</a></li>')
    socials = [(a.get("aria-label"), a.get("href")) for a in h.select(".header-display-desktop .header-actions-action--social a")]
    return {"logo": logo_src, "nav": "".join(nav), "social": social_links(socials)}


HEADER_HTML = """<header class="site-header" id="top">
  <div class="hd-in">
    <nav class="hd-nav" aria-label="Main"><ul>{nav}</ul></nav>
    <a class="hd-logo" href="/"><img src="{logo}" alt="Breaking Walls" width="1500" height="1500"></a>
    <div class="hd-actions"><div class="socials">{social}</div>{lang}</div>
    <button class="hd-burger" type="button" aria-label="Open menu" aria-expanded="false"><span></span><span></span></button>
  </div>
  <div class="hd-mobile" hidden><ul>{nav}</ul><div class="socials">{social}</div>{lang}</div>
</header>"""


def head_html(soup, path, title, desc, og_img, canonical, extra_css=""):
    fav = "/favicon.ico"
    t = html.escape(title)
    d = html.escape(desc or "")
    og = f'<meta property="og:image" content="{SITE_URL}{og_img}">' if og_img and og_img.startswith("/") else ""
    weglot = ""
    if WEGLOT_KEY:
        weglot = (f'<script src="https://cdn.weglot.com/weglot.min.js"></script>'
                  f'<script>Weglot.initialize({{api_key:"{WEGLOT_KEY}",hide_switcher:true}});</script>')
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t}</title>
<meta name="description" content="{d}">
<link rel="canonical" href="{canonical}">
<meta property="og:site_name" content="Breaking Walls">
<meta property="og:title" content="{t}">
<meta property="og:description" content="{d}">
<meta property="og:url" content="{canonical}">
<meta property="og:type" content="website">
{og}
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="{fav}">
<link rel="preload" href="/assets/fonts/poppins-latin-400-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="/assets/fonts/epilogue-latin-500-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/assets/css/site.css">
{weglot}
</head>"""


# ---------------------------------------------------------------- page build
def build_page(path, header):
    name = capname(path)
    raw = (CAP / "pages" / f"{name}.html").read_text()
    soup = BeautifulSoup(raw, "lxml")
    title = ws(soup.title.string if soup.title else "Breaking Walls")
    md = soup.find("meta", attrs={"name": "description"})
    desc = md.get("content", "") if md else ""
    ogm = soup.find("meta", attrs={"property": "og:image"})
    og_img = asset_or_remote(ogm["content"]) if ogm else ""
    canonical = SITE_URL + (path if path != "/" else "/")
    main = soup.select_one("main") or soup.body
    parts = []
    has_collection = False
    for sec in main.select("section.page-section"):
        if sec.find_parent("footer"):
            continue
        r = render_section(sec, path)
        if r is None:
            has_collection = True
            if path == "/blog":
                parts.append(render_blog_list(soup))
            elif path.startswith("/blog/"):
                parts.append(render_blog_post(soup, path))
            else:
                print("   ? unhandled section", sec.get("class"), path)
            continue
        parts.append(r)
    footer = ""
    f = soup.select_one("footer")
    if f:
        fs = [render_section(s, path) for s in f.select("section.page-section")]
        footer = f'<footer class="site-footer">{"".join(x for x in fs if x)}</footer>'
    hdr = ""
    has_header = soup.select_one("header .header-display-desktop") is not None
    if has_header and header:
        lang = '<div class="lang" data-lang><button type="button" aria-label="Language">EN</button></div>' if WEGLOT_KEY else ""
        hdr = HEADER_HTML.format(lang=lang, **header)
    body_cls = "has-header" if hdr else "no-header"
    page = (head_html(soup, path, title, desc, og_img, canonical)
            + f'\n<body class="{body_cls}">\n{hdr}\n<main>{"".join(parts)}</main>\n{footer}\n'
            + '<script src="/assets/js/site.js" defer></script>\n</body>\n</html>\n')
    # animated GIFs converted to MP4: swap <img> for a silent looping <video>
    def gifvid(m):
        attrs = m.group(2)
        alt = re.search(r'alt="([^"]*)"', attrs)
        st = re.search(r'style="([^"]*)"', attrs)
        return (f'<video src="{m.group(1)}" autoplay muted loop playsinline preload="metadata"'
                + (f' aria-label="{alt.group(1)}"' if alt and alt.group(1) else "")
                + (f' style="{st.group(1)}"' if st else "") + '></video>')
    page = re.sub(r'<img src="(/assets/img/[^"]+\.mp4)"([^>]*)>', gifvid, page)
    out = OUT / (path.strip("/") or "") / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page)
    print(f"  built {path} ({len(page)//1024} KB, {len(parts)} sections)")


def main():
    global A, WEGLOT_KEY
    if "--clean" in sys.argv:
        for sub in ["assets/img", "assets/files"]:
            shutil.rmtree(OUT / sub, ignore_errors=True)
    OUT.mkdir(exist_ok=True)
    A = Assets()
    home = BeautifulSoup((CAP / "pages" / "home.html").read_text(), "lxml")
    m = re.search(r'api_key["\']?\s*[:=]\s*["\'](wg_[0-9a-f]+)', str(home))
    if m:
        WEGLOT_KEY = m.group(1)
    header = build_header(home)
    for p in PAGES:
        build_page(p, header)
    # favicon
    for l in home.select("link[rel*=icon]"):
        loc = A.local(l.get("href"))
        if loc:
            shutil.copyfile(OUT / loc.lstrip("/"), OUT / "favicon.ico")
            break
    # videos
    vdir = OUT / "assets" / "video"
    vdir.mkdir(parents=True, exist_ok=True)
    if VIDEO_SRC.exists():
        for v in VIDEO_SRC.iterdir():
            if v.suffix in (".mp4", ".jpg") and not (vdir / v.name).exists():
                shutil.copyfile(v, vdir / v.name)
    print(f"done: {len(A.used)} assets, weglot={'yes' if WEGLOT_KEY else 'no'}")


if __name__ == "__main__":
    main()
