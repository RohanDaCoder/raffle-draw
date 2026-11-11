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

480 two-part tickets · Class 9 · Section D · Tk 10 · Civil Aviation School & College, Kurmitola ·
12 full A4 sheets, festive aviation-blue theme matched to the school logo.

## Running the draw

With `--split-stub` every ticket is two parts sharing one number:

1. **Keep the sheets whole** until a ticket is sold — an unsold ticket never
   produces a stub, so the jar can only ever contain *bought* numbers.
2. **At sale**: cut the ticket off the sheet, separate body and stub along the
   middle dashed line (scissors, or fold-then-tear), give the buyer the body
   (it carries `No. XXX`), drop the stub in the jar immediately.
3. **Draw**: pull one stub, read the big number, match it against the buyer's
   body half, award the prize. For several prizes, keep drawing without
   putting stubs back — one ticket can win only once.
4. **Reconcile** (optional but wise): count the stubs in the jar at the end —
   stubs × ticket price should equal the cash collected.

Alternative (no tearing): keep one-piece tickets, have sellers write each sold
number on a list, and draw numbers from folded paper slips — but the two-part
ticket is the classic for a reason: no extra bookkeeping, no transcription
errors, and the jar stays self-auditing.

## Tiers: VIP pre-orders, teachers, …

Each tier is its own build with its own theme and price, on a **continuing
number range** — every stub in the jar stays unique, all tiers compete in the
same draw:

| Tier | Build | Numbers | Look |
|---|---|---|---|
| Standard | `examples/make_class9d.sh` | 001–480, Tk 10 | festive blue |
| VIP (pre-ordered, named) | `examples/make_vip.sh` | 481+, Tk 10 | gold, holder's name printed |
| Teachers (optional) | see below | after VIP, Tk 50 | e.g. `classic` |

**VIP**: edit `examples/vip_names.txt` — one name per line, in ticket-number
order (`#` comments, `-` = blank fill-in line). The ticket count comes
automatically from the number of names, so adding a pre-order is just adding
a line and pushing. CI ships both sets in every release and on the Pages site.
At the event, hand pre-orderers their named VIP ticket first; their stub goes
into the jar like any other.

**Teachers ticket** (when you decide to add it):

```bash
python raffle_gen.py --theme classic --title "TEACHERS TICKET" \
  --school "CIVIL AVIATION SCHOOL|& COLLEGE, KURMITOLA" \
  --class-line "Staff & Faculty" --party "2026|CLASS PARTY" \
  --price "Tk 50" --logo examples/casck_logo.png --split-stub \
  --start 493 --count 30 --html dist/teachers.html --pdf dist/teachers.pdf
```

Pick `--start` right after your VIP range ends, add the build to the workflow,
and it ships with the rest.

## Options

Everything is configurable. `python raffle_gen.py --help` shows the full list;
every long option can also be set in a JSON file passed with `--config`
(explicit command-line flags win).

| Group | Options |
|---|---|
| **Content** | `--title` · `--school "LINE1\|LINE2"` · `--class-line` · `--party "2026\|CLASS PARTY"` (stub text, year larger) · `--price "Tk 10"` / `--price none` · `--price-label` · `--draw-date "15 Dec 2026"` / `_` = blank line / omitted = hidden · `--draw-date-label` · `--logo FILE` · `--logo-scale X` · `--no-logo` · `--embed-logo/--no-embed-logo` (base64, default on) · `--number-label` · `--names FILE` (holder name per ticket) · `--name-label` |
| **Numbering** | `--count N` · `--sheets N` (N full sheets instead of a count) · `--start` · `--pad` (auto-widened if too small) · `--number-prefix/--number-suffix` |
| **Layout** | `--cols` / `--rows` (grid per sheet) · `--page a3\|a4\|a5\|a6\|letter\|legal\|tabloid` or `210x297` mm · `--margin` · `--stub-width` · `--stub-side right\|left` · `--split-stub` (two-part ticket: tear line + number on both halves) |
| **Style** | `--theme festive\|classic\|carnival\|bw\|gold` · `--accent/--ink/--muted/--cut-color` · `--cut-style dashed\|solid\|none` · `--cut-weight` · `--font-family` · `--webfonts/--no-webfonts` · `--font-scale` (auto-reduced when tickets are smaller than the reference 4×10 A4 design, or when a name row makes the stack taller than the cell) · `--blank-width` |
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
| `gold` | yellow-gold gradient stub, dark-brown text — premium VIP look |

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
   and the PDF, all viewable directly in the browser. Pages requires the repo
   to be **public** (or a paid plan for private repos) with Pages enabled in
   Settings → Pages → Source: GitHub Actions; without it the workflow still
   succeeds and the release page remains the direct preview.

Change what CI builds by editing the command inside `examples/make_class9d.sh`
(or point the workflow at your own script).

## Requirements

* Python 3.9+ (3.10+ for `--embed-logo` downscaling via optional Pillow)
* HTML output: standard library only
* PDF / PNG preview: `pip install playwright && python -m playwright install chromium`
* PDF metadata: optional `pikepdf`
