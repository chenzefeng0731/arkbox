# ArkBox · Arknights Gacha Archive

English | [中文](README.md)

A local-first gacha analyzer for *Arknights*: authorize once through the SKland app, read your
officially queryable pull records, and generate a shareable **poster** plus a responsive long-form
report (with your Doctor's tenure in the header). A separate "My Operators" command filters your
roster by class / rarity / level / potential / skin and renders a gallery page.

![demo poster](docs/demo-poster.png)

Unofficial fan tool, not affiliated with or endorsed by Hypergryph. Code is MIT; game data and
assets remain the property of their original owners.

## Before you start: what you need

| Dependency | Required? | Notes |
|---|---|---|
| Python 3.9+ | Yes | Built into macOS; on Windows install from [python.org](https://www.python.org/downloads/) (check "Add python.org to PATH") |
| SKland app | Yes (for login) | Installed on your phone with an Arknights character bound; scan the QR code to authorize. Not needed for offline analysis (`--records`) |
| Chrome / Edge / Chromium | Optional | Renders the poster PNG; without one you still get HTML and can screenshot it yourself |
| `pip3 install qrcode` | Optional | Renders the login QR code locally; without it, login falls back to a local HTML page (rendered via a public QR service — only a one-time scanId is sent) |

**Windows users**: replace `python3` with `python` or `py -3` in the commands; everything else is identical.

**Pure standard library, zero dependencies**: apart from the optional items above, no third-party
packages are installed. Every network call is spelled out in the source (see the "network egress
list" in SKILL.md). Credentials live only in `~/.arkbox/` (permission 600) and can be audited by anyone.

## Cross-platform

- Runs on macOS / Windows / Linux with Python 3.9+ and zero third-party runtime dependencies.
- PNG output needs a local Chrome / Edge / Chromium; when no browser is found it still produces HTML and never blocks the main flow.
- Login QR code: with `qrcode` installed you get a local PNG (`pip3 install qrcode`, recommended); otherwise a local HTML page (rendered via a public QR service — it only sends a one-time scanId, no account credentials), so a missing library never crashes the flow.
- Reachability of images, fonts and CDNs affects visuals only; data and HTML structure are identical on every platform.

## Install

Option 1: git clone (easiest to update later)

```bash
git clone https://github.com/chenzefeng0731/arkbox.git arkbox
cd arkbox
python3 install.py
```

Option 2: no git — the green **Code** button → **Download ZIP** on GitHub, unzip, enter the folder, run the same command.

The installer detects your agent's skills directory automatically and installs the skill there;
if nothing is detected it falls back to `~/.arkbox/skill/arkbox`, which works just as well —
point your agent at the `SKILL.md` inside and let it call `scripts/`, or run the CLI directly
(the true cross-agent common denominator is the Python CLI). To pick a location yourself,
pass `--target <dir>`; see `python3 install.py --help`.

After installing, just tell your agent:

> Use arkbox to analyze my Arknights pull records and make a poster and an HTML report

Or skip installation and run the script straight from the repo:

```bash
python3 skill/arkbox/scripts/ark_gacha.py analyze --poster --html
```

## First login

```bash
python3 skill/arkbox/scripts/skland_core.py login
```

Scan the QR code with the SKland app, or choose phone number + verification code in the terminal.
Credentials are stored in `~/.arkbox/credentials.json` (permission 600).

If something looks off, run:

```bash
python3 skill/arkbox/scripts/ark_doctor.py
```

Most "credential expired" situations do **not** need a re-login: ArkBox silently renews the
session with the saved `hg_token`; only when that token itself is invalidated do you have to
log in again.

**How long does one login last?** There is no official expiry promise. Community experience:
as long as you don't change your password, log out, or "remove devices" inside the SKland app,
one login keeps working; any of those invalidates it immediately. When it does expire,
`ark_doctor.py` will say so clearly — just run login again. Archives in `~/.arkbox/archive/`
are not affected.

## Common commands

```bash
# Preview with synthetic demo data (no login needed)
python3 skill/arkbox/scripts/ark_gacha.py analyze \
  --records fixtures/demo-records.jsonl --nick "Demo Doctor" --poster --html

# Poster + long HTML (the minimal universal deliverable)
python3 skill/arkbox/scripts/ark_gacha.py analyze --poster --html

# Build a publishable public site (Qoder Sites)
python3 skill/arkbox/scripts/ark_gacha.py analyze \
  --site --site-dir site --poster --quiet

# Offline analysis
python3 skill/arkbox/scripts/ark_gacha.py analyze \
  --records records.json --nick Doctor --poster --html
```

`--poster` keeps only the poster PNG by default and deletes its source HTML; add
`--keep-poster-source` if you want to edit the source.

## Tenure

The report header shows `Tenure 2024-07-14 · 834 days` (example) after your nickname, sourced
from SKland `status.registerTs`. Offline records without an account profile hide it gracefully,
so the gacha report is unaffected.

## Deliverables

- **Poster**: 1080×1440 logical size, rendered at 2x into a 2160×2880 PNG (crisp on high-DPI
  screens and resilient to social-media recompression), ready for social posts and comment sections.
- **Report**: published as a static site for Qoder users; everyone else gets a self-contained
  `report.html`.
- Poster source HTML, phone screenshots, Markdown and explanatory docs are not deliverables;
  they exist only as sources and for acceptance.

## Data & privacy

- **Shared artifacts (poster / HTML / site / gallery) never show your UID**: the UID never enters
  the report model and exists only in local credentials and archives; `--hide-nick` hides the
  nickname too.
- The public site pins the nickname to "Doctor", contains no UID, and sets `noindex` +
  `robots.txt` to block crawlers; the poster is a separate file and keeps the nickname.
- Only player fields needed for display are used; sanity, last-online, base status and
  recruitment state are never written into public artifacts.
- Raw pull records are archived under `~/.arkbox/archive/` and never uploaded.
- Credentials are the keys to your account — never share `~/.arkbox/credentials.json`. Log out
  with `skland_core.py logout`; to revoke access completely, remove the authorization in the
  SKland app's authorization management.

## Tests

```bash
# Unit & consistency self-test (offline, no credentials read)
python3 skill/arkbox/scripts/selftest.py

# End-to-end smoke (no login: full pipeline from fixtures to poster/report/site,
# asserts numbers and privacy)
python3 tests/e2e_check.py
```

Unit tests cover the gacha model, per-banner accounting, zero-6-star runs, titles, privacy,
site output, tenure and edge cases; the e2e smoke drives the real CLI. CI runs everything on
macOS / Windows / Linux × Python 3.9 / 3.12 on every push.

## Layout

```
skill/arkbox/          skill source (SKILL.md + scripts + references)
fixtures/              demo records (mirrors the real archive shape, no account info, timeline shifted)
tests/                 end-to-end smoke (e2e_check.py)
install.py             cross-platform installer
docs/                  design, acceptance, demo assets and publishing checklist
LICENSE                MIT (code only)
THIRD_PARTY_NOTICES.md game data / avatars / third-party components
docs/PUBLISHING.md    privacy / verification checklist before publishing
```

## Known limits

- SKland only returns records inside a queryable window, which cannot prove your account's full
  history; reports therefore say "within this archive".
- Standard / beginner banner history cannot be proven complete, so pulls are **never merged
  across banners**; the first segment may inherit pulls made before the archive began.
- Spark (shopping-point) rules differ across standard / beginner / limited banners and are not
  computed; limited-300 and collab-120 progress is shown within the archive only.
- Screenshot OCR and official record links that require a logged-in session / signature are not
  auto-imported; public JSON links work via `--records URL`.
- **Direct access to GitHub raw is unreliable in some regions (e.g. mainland China)**: operator
  metadata downloads fall back to a jsdelivr mirror automatically, and page avatars switch
  mirrors on failure; the pool-table mirror (PRTS) is usually reachable directly. When a fetch
  fails the tool degrades gracefully (banner type / rate-up shows "pending") — basic stats and
  report generation are unaffected.
- The APIs come from community reverse-engineering of SKland / the official site; official
  changes may break login or fetching. If that happens, please open an issue with your
  `ark_doctor.py` output attached.
