# raffle-draw

Print-ready **raffle ticket sheets** — millimetre-exact, zero wasted paper, fully configurable.

A single Python file builds an A4 (or any size) HTML sheet whose ticket grid fills the
entire printable area — cut lines are shared between neighbours and nothing is printed
outside the grid — then renders a **vector PDF** through headless Chromium.

Each ticket pairs a white body with a coloured stub for the jar. The body ends in a
rounded **footer band** printed in the theme colour: price on the left, the matching
ticket number on the right. The stub is torn off and dropped in the jar at sale time,
so the band is what the buyer actually keeps — the buyer's half keeps its own block of
colour instead of going bland after the tear.

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

480 two-part tickets · Class 9 · Section D · 10tk · Civil Aviation School & College, Kurmitola ·
12 full A4 sheets, festive aviation-blue theme matched to the school logo.

## Generate tickets from the website

The GitHub Pages site is a **full ticket generator that runs in the browser** —
built for exactly the case where you are on someone else's phone with no
GitHub login: open the site, set the numbers, tap download.

**<https://rohandacoder.github.io/raffle-draw/>**

* **Standard** — pick the first number and the count (defaults: 001–480,
  12 sheets). If the range would collide with the VIP numbers 481–495 the
  page warns you before you print duplicates into the jar.
* **VIP** — an editor prefilled from `examples/vip_list.json`: add or remove
  holders, change counts, and each holder's number range is shown live
  (default: Topu 481–485 · Faiyaz 486–490 · Nakkhatra 491–495).
* **Ready-made files** — the CI-built Playwright PDFs are linked on the same
  page, so the canonical batches are always one tap away.

Everything happens client-side: `web/generator.js` is the same millimetre
layout engine as `raffle_gen.py`, ported to jsPDF (vendored in `web/vendor/`,
MIT) — no server, no account, and generation keeps working on a flaky
connection once the page has loaded. Phone-generated sheets match the
CI-built releases: same grid, themes, tear lines and numbering.

Serve it locally exactly like CI does:

```bash
mkdir /tmp/raffle-site && cp -r web/* examples/vip_list.json /tmp/raffle-site/ &&
  cd /tmp/raffle-site && python3 -m http.server
```

## Running the draw

With `--split-stub` every ticket is two parts sharing one number:

1. **Keep the sheets whole** until a ticket is sold — an unsold ticket never
   produces a stub, so the jar can only ever contain *bought* numbers.
2. **At sale**: cut the ticket off the sheet, separate body and stub along the
   middle dashed line (scissors, or fold-then-tear), give the buyer the body
   (the footer band carries `No. XXX`), drop the stub in the jar immediately.
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
| Standard | `examples/make_class9d.sh` | 001–480, 10tk | festive blue |
| VIP (pre-ordered, named) | `examples/make_vip.sh` | 481–495 (3 holders × 5), 10tk | gold, holder's name printed |
| Teachers (optional) | see below | after VIP, 50tk | e.g. `classic` |

**VIP**: the pre-order list is `examples/vip_list.json` — a JSON map of holder
to ticket count:

```json
{
  "Topu": 5,
  "Faiyaz": 5,
  "Nakkhatra": 5
}
```

Numbers are assigned in file order — Topu gets 481–485, Faiyaz 486–490,
Nakkhatra 491–495 — and the ticket total follows the file automatically, so
adding a pre-order is just adding a line and pushing. A list form works too:
`[{"name": "Topu", "tickets": 5}]` (bare strings mean one ticket), and
`{"name": null, "tickets": 2}` prints blank fill-in tickets. The VIP build
uses a 3×5 grid, so the current 15 pre-orders fill **exactly one A4 sheet
with nothing wasted**; if the list grows past 15, raise `--rows` to the next
multiple of 3 to keep full sheets. CI ships both sets in every release and on
the Pages site. At the event, hand pre-orderers their named VIP ticket first;
their stub goes into the jar like any other.

**Teachers ticket** (when you decide to add it):

```bash
python raffle_gen.py --theme classic --title "TEACHERS TICKET" \
  --school "CIVIL AVIATION SCHOOL|& COLLEGE, KURMITOLA" \
  --class-line "Staff & Faculty" --party "2026|CLASS PARTY" \
  --price "50tk" --logo examples/casck_logo.png --split-stub \
  --start 496 --count 30 --html dist/teachers.html --pdf dist/teachers.pdf
```

Pick `--start` right after your VIP range ends, add the build to the workflow,
and it ships with the rest.

## Options

Everything is configurable. `python raffle_gen.py --help` shows the full list;
every long option can also be set in a JSON file passed with `--config`
(explicit command-line flags win).

| Group | Options |
|---|---|
| **Content** | `--title` · `--school "LINE1\|LINE2"` · `--class-line` · `--party "2026\|CLASS PARTY"` (stub text, year larger) · `--price "10tk"` / `--price none` (footer band; the value is printed as-is, label-free) · `--draw-date "15 Dec 2026"` / `_` = blank line / omitted = hidden · `--draw-date-label` · `--logo FILE` · `--logo-scale X` · `--no-logo` · `--embed-logo/--no-embed-logo` (base64, default on) · `--number-label` · `--names FILE` (VIP holder names: JSON `{"Topu": 5}` map or list of `{"name", "tickets"}`; legacy one-per-line text also works) · `--name-label` |
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
2. runs `examples/make_class9d.sh` and `examples/make_vip.sh`,
3. publishes a **GitHub Release** tagged `build-<run number>` with
   `raffle_tickets.pdf`/`.html`/`preview.png` and the VIP
   `vip_tickets.pdf`/`.html`/`vip_preview.png` attached —
   the preview image renders right inside the release notes,
4. deploys the **GitHub Pages site** — the in-browser ticket generator from
   `web/` (standard + VIP, custom counts and holders, PDFs made on the
   phone) plus the CI-built print files — at
   `https://<user>.github.io/raffle-draw/`. Pages requires the repo to be
   **public** (or a paid plan for private repos) with Pages enabled in
   Settings → Pages → Source: GitHub Actions; without it the workflow still
   succeeds and the release page remains the direct preview.

Change what CI builds by editing the command inside `examples/make_class9d.sh`
(or point the workflow at your own script).

## Requirements

* Python 3.9+ (3.10+ for `--embed-logo` downscaling via optional Pillow)
* HTML output: standard library only
* PDF / PNG preview: `pip install playwright && python -m playwright install chromium`
* PDF metadata: optional `pikepdf`
