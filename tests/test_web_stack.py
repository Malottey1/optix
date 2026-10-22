"""The current dashboard (web/, Vite + React + TypeScript) stays local and pinned:
  * package.json pins every dependency to an exact version, and package-lock.json is committed;
  * node_modules and dist are never tracked by git;
  * nothing in web/src, web/index.html or a built web/dist imports, loads, links or fetches a remote
    URL, and app code never names a CDN; fonts are self-hosted (Fontsource), never a remote stylesheet;
  * the body background is set in plain CSS in index.html (no flash before the stylesheet);
  * web/public/data holds the engine's four output files, unedited copies of out/ when out/ exists.
"""
import json
import re
import subprocess
from pathlib import Path

from tests.test_ui_stack import PATTERNS, REMOTE

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
EXACT = re.compile(r"^\d+\.\d+\.\d+$")
CDN_HOSTS = ("esm.sh", "unpkg.com", "jsdelivr", "cdnjs", "skypack", "googleapis", "gstatic", "cdn.tailwindcss.com",
             "fonts.bunny", "typekit")
DATA_FILES = ("ui.json", "insights.jsonl", "claims.jsonl", "timeline.json")


def _files(root: Path, suffixes=(".html", ".js", ".mjs", ".ts", ".tsx", ".css")):
    return [p for p in root.rglob("*") if p.is_file() and p.suffix in suffixes and "node_modules" not in p.parts]


def _remote_hits(files):
    hits = []
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        for kind, rx in PATTERNS.items():
            for m in rx.finditer(text):
                target = m.group(1).strip()
                if re.match(REMOTE, target) and not target.startswith("data:"):
                    hits.append(f"{f.relative_to(ROOT)}: {kind} {target}")
    return hits


def test_dependencies_are_pinned_exactly_and_the_lockfile_is_committed():
    pkg = json.loads((WEB / "package.json").read_text())
    loose = {k: v for sect in ("dependencies", "devDependencies") for k, v in pkg.get(sect, {}).items() if not EXACT.match(v)}
    assert not loose, loose
    lock = json.loads((WEB / "package-lock.json").read_text())
    root = lock["packages"][""]
    assert root.get("dependencies") == pkg["dependencies"] and root.get("devDependencies") == pkg["devDependencies"]
    tracked = subprocess.run(["git", "ls-files", "web/package-lock.json"], cwd=ROOT, capture_output=True, text=True).stdout
    assert tracked.strip() == "web/package-lock.json"


def test_node_modules_and_dist_are_not_tracked():
    out = subprocess.run(["git", "ls-files", "web"], cwd=ROOT, capture_output=True, text=True).stdout.splitlines()
    bad = [p for p in out if "/node_modules/" in p or p.startswith("web/dist/")]
    assert not bad, bad[:5]


def test_no_remote_url_in_source_or_build():
    files = _files(WEB / "src") + [WEB / "index.html"]
    if (WEB / "dist").is_dir():                 # built output, when present (CI builds before the browser gate)
        files += _files(WEB / "dist")
    assert not _remote_hits(files), _remote_hits(files)


def test_app_code_names_no_cdn_and_fonts_are_self_hosted():
    hits = [f"{f.relative_to(ROOT)}: {h}" for f in _files(WEB / "src") + [WEB / "index.html"]
            for h in CDN_HOSTS if h in f.read_text(encoding="utf-8")]
    assert not hits, hits
    css = (WEB / "src" / "styles" / "index.css").read_text()
    imports = re.findall(r'@import\s+"([^"]+)"', css)
    assert imports and all(i.startswith(("@fontsource", "tailwindcss", "./")) for i in imports), imports


def test_plain_css_body_background_and_tokens():
    html = (WEB / "index.html").read_text()
    assert re.search(r"<style>\s*html,\s*body\s*{[^}]*background:\s*#[0-9a-f]{6}", html)
    tokens = (WEB / "src" / "styles" / "tokens.css").read_text()
    for t in ("--bg", "--surface-1", "--accent", "--pass", "--revise", "--block", "--home", "--away"):
        assert re.search(rf"{t}:\s*#[0-9a-f]{{6}}", tokens), t


def test_committed_data_is_the_engine_output():
    data = WEB / "public" / "data"
    for name in DATA_FILES:
        assert (data / name).is_file(), name
        out = ROOT / "out" / name
        if out.is_file():
            assert out.read_bytes() == (data / name).read_bytes(), f"{name}: rerun `npm run data` in web/"
    ui = json.loads((data / "ui.json").read_text())
    assert {"teams", "players", "ledger", "rewrites", "reasons", "evidence", "measured", "track"} <= set(ui)
