"""The dashboard stack stays no-build and fully local (docs/dashboard.md):
  * no package.json, lockfile, bundler or build config, and no node_modules, anywhere in the repo;
  * nothing in app/ (vendored files included) imports, loads, links or fetches a remote URL;
  * every import-map target and every relative import exists locally, and every bare import is
    in the import map;
  * app/vendor/VENDOR.md lists every vendored file with a SHA-256 that matches.
"""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
VENDOR = APP / "vendor"
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", "out", "data"}

BUILD_FILES = re.compile(
    r"^(package\.json|package-lock\.json|npm-shrinkwrap\.json|yarn\.lock|pnpm-lock\.yaml|bun\.lockb?|\.npmrc|\.yarnrc(\.yml)?"
    r"|(webpack|vite|rollup|esbuild|parcel|snowpack|postcss|tailwind|babel|svelte|astro|next|nuxt)\.config\.[cm]?[jt]s"
    r"|\.babelrc(\.json)?|tsconfig\.json|jsconfig\.json|deno\.json|\.parcelrc|gulpfile\.js|Gruntfile\.js)$")

REMOTE = r"(?:[a-zA-Z][a-zA-Z0-9+.-]*:)?//"          # http://, https://, ws://, protocol-relative //
PATTERNS = {
    "static import": re.compile(r"""(?:\bimport|\bexport)\s*(?:[\w*{}\s,$]+?\s*from\s*)?["']([^"']+)["']"""),
    "from clause": re.compile(r"""\bfrom\s*["']([^"']+)["']"""),
    "dynamic import": re.compile(r"""\bimport\s*\(\s*["'`]([^"'`]+)["'`]"""),
    "script src": re.compile(r"""<script[^>]*\bsrc\s*=\s*["']([^"']+)["']""", re.I),
    "link href": re.compile(r"""<link[^>]*\bhref\s*=\s*["']([^"']+)["']""", re.I),
    "css url()": re.compile(r"""url\(\s*["']?([^"')\s]+)"""),
    "css @import": re.compile(r"""@import\s+["']([^"']+)["']"""),
    "fetch": re.compile(r"""\bfetch\s*\(\s*["'`]([^"'`]+)["'`]"""),
    "worker": re.compile(r"""new\s+(?:Shared)?Worker\s*\(\s*["'`]([^"'`]+)["'`]"""),
}


def _walk(root):
    for p in root.rglob("*"):
        if any(part in SKIP_DIRS for part in p.relative_to(root).parts):
            continue
        yield p


def _code_files():
    return [p for p in APP.rglob("*") if p.is_file() and p.suffix in (".html", ".js", ".mjs", ".css")]


def _import_map():
    html = (APP / "index.html").read_text(encoding="utf-8")
    m = re.search(r'<script type="importmap">(.*?)</script>', html, re.S)
    assert m, "app/index.html has no import map"
    return json.loads(m.group(1))["imports"]


def test_no_package_manager_bundler_or_node_modules_anywhere():
    bad = [str(p.relative_to(ROOT)) for p in _walk(ROOT)
           if (p.is_dir() and p.name == "node_modules") or (p.is_file() and BUILD_FILES.match(p.name))]
    assert not bad, bad


def test_no_remote_url_is_imported_loaded_linked_or_fetched():
    hits = []
    for f in _code_files():
        text = f.read_text(encoding="utf-8", errors="replace")
        for kind, rx in PATTERNS.items():
            for m in rx.finditer(text):
                target = m.group(1).strip()
                if re.match(REMOTE, target) and not target.startswith("data:"):
                    hits.append(f"{f.relative_to(ROOT)}: {kind} {target}")
    for name, target in _import_map().items():
        if re.match(REMOTE, target):
            hits.append(f"import map {name} -> {target}")
    assert not hits, hits


def test_no_cdn_hosts_referenced_by_app_code():
    """App code (not the vendored files' comments) never names a CDN."""
    hosts = ("esm.sh", "unpkg.com", "jsdelivr", "cdnjs", "skypack", "googleapis", "gstatic", "cdn.tailwindcss.com")
    hits = [f"{f.relative_to(ROOT)}: {h}" for f in _code_files() if VENDOR not in f.parents
            for h in hosts if h in f.read_text(encoding="utf-8")]
    assert not hits, hits


def test_import_map_targets_and_relative_imports_exist():
    imap = _import_map()
    for name, target in imap.items():
        assert (APP / target).resolve().is_file(), (name, target)
    assert {"react", "react-dom/client", "htm"} <= set(imap)
    missing = []
    for f in _code_files():
        # ES modules only: the Tailwind browser build is a classic <script> (its "import" words are CSS)
        if f.suffix not in (".js", ".mjs") or f.name == "tailwindcss-browser.js":
            continue
        text = f.read_text(encoding="utf-8")
        for rx in (PATTERNS["from clause"], PATTERNS["static import"], PATTERNS["dynamic import"]):
            for m in rx.finditer(text):
                spec = m.group(1)
                if spec.startswith((".", "/")):
                    if not (f.parent / spec).resolve().is_file():
                        missing.append(f"{f.relative_to(ROOT)}: {spec}")
                elif spec not in imap:
                    missing.append(f"{f.relative_to(ROOT)}: bare import {spec!r} not in the import map")
    html = (APP / "index.html").read_text(encoding="utf-8")
    for rx in (PATTERNS["script src"], PATTERNS["link href"]):
        for m in rx.finditer(html):
            if not m.group(1).startswith("data:") and not (APP / m.group(1)).resolve().is_file():
                missing.append(f"index.html: {m.group(1)}")
    assert not missing, missing


def test_vendor_md_covers_every_vendored_file_with_matching_checksum():
    doc = (VENDOR / "VENDOR.md").read_text(encoding="utf-8")
    rows = {}
    for line in doc.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 5 and re.fullmatch(r"[0-9a-f]{64}", cells[4]):
            rows[cells[0]] = cells[4]
    files = sorted(p.name for p in VENDOR.iterdir() if p.is_file() and p.name != "VENDOR.md")
    assert sorted(rows) == files, (sorted(rows), files)
    for name, digest in rows.items():
        assert hashlib.sha256((VENDOR / name).read_bytes()).hexdigest() == digest, name
    for code in ("react.mjs", "react-dom-client.mjs", "htm.mjs", "tailwindcss-browser.js"):
        lic = {"react.mjs": "LICENSE-react", "react-dom-client.mjs": "LICENSE-react-dom",
               "htm.mjs": "LICENSE-htm", "tailwindcss-browser.js": "LICENSE-tailwindcss"}[code]
        assert (VENDOR / lic).is_file(), lic


def test_no_remote_font_or_stylesheet_and_a_dark_body_background_in_plain_css():
    css = (APP / "styles" / "theme.css").read_text(encoding="utf-8")
    assert "@font-face" not in css            # system font stack only: no font file to fetch
    assert re.search(r"html,\s*body\s*{[^}]*background:\s*var\(--bg\)", css)
    assert re.search(r"--bg:\s*#[0-9a-f]{6}", css)
