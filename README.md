# raffle-draw

Print-ready **raffle ticket sheets** — millimetre-exact, zero wasted paper, fully configurable.

A single Python file builds an A4 (or any size) HTML sheet whose ticket grid fills the
entire printable area — cut lines are shared between neighbours and nothing is printed
outside the grid — then renders a **vector PDF** through headless Chromium.

```
┌──────────────────────────────── A4 ────────────────────────────────┐
│ ┌────────────┬────────────┬────────────┬────────────┐             │
│ │ ticket 001 │ ticket 002 │ ticket 003 │ ticket 004 │             │
│ ├────────────┼────────────┼────────────┼────────────┤             │
│ │ ticket 005 │ ...        │            │            │  40 per     │
│ └────────────┴────────────┴────────────┴────────────┘  sheet      │
└───────────────────────────────────────────────────────────────────┘
```

## Quick start

```bash
# HTML only — pure stdlib, nothing to install
python raffle_gen.py --count 480 --html tickets.html

# Vector PDF + PNG preview (needs a one-time browser install)
pip install playwright pillow pikepdf
python -m playwright install chromium
python raffle_gen.py --count 480 --pdf tickets.pdf --preview page1.png
```

Open `tickets.html` in any browser and print from there, or print the PDF —
either way **print at 100% scale (Actual Size)** and cut along the dashed lines.

## The example batch

`examples/make_class9d.sh` reproduces the batch these sheets were built for:

```bash
bash examples/make_class9d.sh     # -> dist/raffle_tickets.{html,pdf}, dist/preview.png
```

480 tickets · Class 9 · Section D · Tk 10 · Civil Aviation School & College, Kurmitola ·
12 full A4 sheets, festive aviation-blue theme matched to the school logo.

## Options

Everything is configurable. `python raffle_gen.py --help` shows the full list;
every long option can also be set in a JSON file passed with `--config`
(explicit command-line flags win).

| Group | Options |
|---|---|
| **Content** | `--title` · `--school "LINE1\|LINE2"` · `--class-line` · `--party "2026\|CLASS PARTY"` (stub text, year larger) · `--price "Tk 10"` / `--price none` · `--price-label` · `--draw-date "15 Dec 2026"` / `_` = blank line / omitted = hidden · `--draw-date-label` · `--logo FILE` · `--no-logo` · `--embed-logo/--no-embed-logo` (base64, default on) · `--number-label` |
| **Numbering** | `--count N` · `--sheets N` (N full sheets instead of a count) · `--start` · `--pad` (auto-widened if too small) · `--number-prefix/--number-suffix` |
| **Layout** | `--cols` / `--rows` (grid per sheet) · `--page a3\|a4\|a5\|a6\|letter\|legal\|tabloid` or `210x297` mm · `--margin` · `--stub-width` · `--stub-side right\|left` |
| **Style** | `--theme festive\|classic\|carnival\|bw` · `--accent/--ink/--muted/--cut-color` · `--cut-style dashed\|solid\|none` · `--cut-weight` · `--font-family` · `--webfonts/--no-webfonts` · `--font-scale` (auto-reduced when tickets are smaller than the reference 4×10 A4 design) · `--blank-width` |
| **Output** | `--html` · `--pdf` · `--preview` (PNG of sheet 1) · `--quiet` |

Notes:

* Multi-line texts use `|` as the line separator, e.g. `--school "SCHOOL A|& COLLEGE"`.
* Option values that start with `-` need `=` syntax: `--number-suffix=-Z`.
* If the ticket count is not a multiple of `--cols`, the final sheet's last row
  has empty cells; prefer counts divisible by `cols × rows` for perfectly full sheets
  (e.g. 480 = 12 × 40).
* The default 6 mm margin is a safe hardware no-print zone for most printers;
  raise it if your printer clips edges.

### Themes

| Theme | Look |
|---|---|
| `festive` | aviation blue gradient stub, Inter, blue title (default) |
| `classic` | flat navy stub, Georgia serif |
| `carnival` | red gradient stub, Baloo 2 rounded font |
| `bw` | black & white — white stub with black outline, cheap to photocopy |

Any single colour can be overridden, e.g. `--theme festive --accent "#b8860b"`.

## CI: release on every commit

`.github/workflows/release.yml` runs on every push to `main`:

1. installs Python + Playwright/Chromium,
2. runs `examples/make_class9d.sh`,
3. publishes a **GitHub Release** tagged `build-<run number>` with
   `raffle_tickets.pdf`, `raffle_tickets.html` and `preview.png` attached —
   the preview image renders right inside the release notes,
4. deploys a **GitHub Pages** live preview at
   `https://<user>.github.io/raffle-draw/` — page-1 image, the printable HTML,
   and the PDF, all viewable directly in the browser.

Change what CI builds by editing the command inside `examples/make_class9d.sh`
(or point the workflow at your own script).

## Requirements

* Python 3.9+ (3.10+ for `--embed-logo` downscaling via optional Pillow)
* HTML output: standard library only
* PDF / PNG preview: `pip install playwright && python -m playwright install chromium`
* PDF metadata: optional `pikepdf`
