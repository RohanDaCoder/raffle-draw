#!/usr/bin/env python3
"""
raffle_gen.py — highly configurable, print-ready raffle ticket sheet generator.

Builds a millimetre-exact HTML sheet (CSS @page + grid) and renders a vector
PDF through headless Chromium (Playwright). HTML generation is pure stdlib;
Pillow is used only to shrink embedded logos when available.

Design goals:
  * the ticket grid fills the ENTIRE printable area of every sheet —
    cut lines are shared between neighbours, nothing is printed outside;
  * every visual dimension is configurable (page, margins, grid, colors,
    fonts, texts, numbering, logo, stub, themes).

Quick start:
    python raffle_gen.py --count 480 --pdf tickets.pdf

Full docs: README.md  |  --help for every option.
"""
import argparse
import base64
import io
import json
import math
import os
import sys
from html import escape as esc
from string import Template

VERSION = "1.3.0"

PAGE_SIZES = {  # width x height in mm, portrait
    "a3": (297.0, 420.0), "a4": (210.0, 297.0), "a5": (148.0, 210.0),
    "a6": (105.0, 148.0), "letter": (215.9, 279.4), "legal": (215.9, 355.6),
    "tabloid": (279.4, 431.8),
}

THEMES = {
    "festive": dict(
        font="'Inter','Segoe UI','Helvetica Neue',Arial,'Noto Sans SC',sans-serif",
        webfont="Inter:wght@400;600;700;800;900",
        stub_bg="linear-gradient(180deg, #1258a7 0%, #0d3f77 100%)",
        stub_text="#ffffff", stub_border_w=0.0, stub_sep="rgba(255,255,255,0.55)",
        cut="#9fb3c9", rule="#dbe7f4", muted="#46607a",
        ink="#0e2f52", title="#1258a7", accent="#1258a7",
        band_bg="#1258a7", band_text="#ffffff", band_border_w=0.0),
    "classic": dict(
        font="Georgia,'Times New Roman','Noto Serif SC',serif",
        webfont="",
        stub_bg="#1d3557", stub_text="#ffffff",
        stub_border_w=0.0, stub_sep="rgba(255,255,255,0.5)",
        cut="#b9c4d0", rule="#dfe5ec", muted="#5a6b7d",
        ink="#14263c", title="#1d3557", accent="#1d3557",
        band_bg="#1d3557", band_text="#ffffff", band_border_w=0.0),
    "carnival": dict(
        font="'Baloo 2','Trebuchet MS','Comic Sans MS',cursive",
        webfont="Baloo+2:wght@600;700;800",
        stub_bg="linear-gradient(180deg, #e63946 0%, #b02a37 100%)",
        stub_text="#ffffff", stub_border_w=0.0, stub_sep="rgba(255,255,255,0.55)",
        cut="#f3b8c0", rule="#fde5e8", muted="#8a4a52",
        ink="#4a1116", title="#c1121f", accent="#c1121f",
        band_bg="#c1121f", band_text="#ffffff", band_border_w=0.0),
    "bw": dict(
        font="'Helvetica Neue',Helvetica,Arial,sans-serif",
        webfont="",
        stub_bg="#ffffff", stub_text="#111111",
        stub_border_w=0.3, stub_sep="rgba(0,0,0,0.45)",
        cut="#999999", rule="#cccccc", muted="#444444",
        ink="#000000", title="#000000", accent="#000000",
        band_bg="#ffffff", band_text="#111111", band_border_w=0.3),
    "gold": dict(
        font="'Inter','Segoe UI','Helvetica Neue',Arial,'Noto Sans SC',sans-serif",
        webfont="Inter:wght@400;600;700;800;900",
        stub_bg="linear-gradient(180deg, #f2c94c 0%, #c9971c 100%)",
        stub_text="#2b2000",
        stub_border_w=0.0, stub_sep="rgba(43,32,0,0.4)",
        cut="#d9c47a", rule="#f0e3b8", muted="#6b5a26",
        ink="#2b2410", title="#9a7200", accent="#b8860b",
        band_bg="#c9971c", band_text="#2b2000", band_border_w=0.0),
}

# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def mm(v):
    return f"{v:.2f}".rstrip("0").rstrip(".")


def pt(v):
    return f"{v:.2f}".rstrip("0").rstrip(".")


def parse_page(spec):
    s = spec.strip().lower()
    if "x" in s:
        try:
            w, h = s.split("x", 1)
            pw, ph = float(w), float(h)
            if pw <= 0 or ph <= 0:
                raise ValueError
            return pw, ph
        except ValueError:
            sys.exit(f"error: bad custom page size '{spec}' (expected e.g. 210x297)")
    if s in PAGE_SIZES:
        return PAGE_SIZES[s]
    sys.exit(f"error: unknown page size '{spec}'. "
             f"Known: {', '.join(sorted(PAGE_SIZES))} or custom WxH in mm")


def lines(text):
    """Split on '|' into escaped lines joined by <br>."""
    return "<br>".join(esc(part) for part in text.split("|"))


def _name_count(v, who, path):
    """Coerce a JSON ticket count to a validated int >= 1."""
    if isinstance(v, bool):
        sys.exit(f"error: bad names JSON in {path!r}: ticket count for {who} "
                 "must be a whole number")
    if isinstance(v, int):
        n = v
    elif isinstance(v, float) and v.is_integer():
        n = int(v)
    elif isinstance(v, str) and v.strip().lstrip("+-").isdigit():
        n = int(v.strip())
    else:
        sys.exit(f"error: bad names JSON in {path!r}: ticket count for {who} "
                 f"must be a whole number, got {v!r}")
    if n < 1:
        sys.exit(f"error: bad names JSON in {path!r}: ticket count for {who} "
                 f"must be >= 1 (got {n}) — remove the entry to drop a pre-order")
    return n


def parse_names_json(path, data):
    """Expand names JSON into the per-ticket name list.

    Accepted shapes (entries are expanded in order, each repeated by its
    ticket count, so entry i's tickets get consecutive numbers):

      {"Topu": 5, "Faiyaz": 5}                      name -> ticket count map
      {"preorders": [{"name": "Topu", "tickets": 5}]}   wrapped list
      [{"name": "Topu", "tickets": 5}, "Rafi"]      list; a bare string = 1
      {"name": null, "tickets": 2}                  null/'-' name = blank
                                                     fill-in tickets

    Returns (expanded list of names / None, holder count).
    """
    def die(msg):
        sys.exit(f"error: bad names JSON in {path!r}: {msg}")

    if isinstance(data, dict):
        for key in ("preorders", "names", "vip", "list", "holders"):
            if key in data:
                if not isinstance(data[key], list):
                    die(f"'{key}' must be a list")
                data = data[key]
                break
        else:  # plain map: {"Topu": 5}
            data = [{"name": k, "tickets": v}
                    for k, v in data.items()
                    if k not in ("note", "comment", "$comment", "_comment")]

    if not isinstance(data, list):
        die('expected a name->count map, a list of entries, or {"preorders": [...]}')

    out = []
    for i, e in enumerate(data):
        if isinstance(e, str):
            name, n = (None if e.strip() == "-" else e), 1
        elif isinstance(e, dict):
            name = e.get("name")
            if name is None or str(name).strip() in ("", "-"):
                name = None
            else:
                name = str(name).strip()
            n = e.get("tickets", e.get("count", e.get("qty", 1)))
            n = _name_count(n, repr(name) if name else f"entry {i + 1}", path)
        else:
            die(f"entry {i + 1} must be a string or an object with "
                "'name'/'tickets'")
        out.extend([name] * n)
    return out, len(data)


def parse_names(path):
    """Read a holder-names file for named (VIP / pre-order) tickets.

    JSON (recommended): a name -> ticket-count map like {"Topu": 5}, or a
    list of {"name": ..., "tickets": ...} entries (see parse_names_json).
    Plain text (legacy): one holder per line, in ticket-number order —
    '#' lines are comments, '-' prints a blank fill-in ticket.

    Returns (list with one entry per ticket — name or None for a blank
    fill-in — plus the number of distinct holders).
    """
    if not path:
        return [], 0
    if not os.path.exists(path):
        print(f"warning: names file not found: {path!r}", file=sys.stderr)
        return [], 0
    raw = open(path, encoding="utf-8").read()
    try:
        data = json.loads(raw)
    except ValueError:
        if path.lower().endswith(".json"):
            sys.exit(f"error: {path!r} is not valid JSON")
        data = None
    if data is not None:
        return parse_names_json(path, data)

    out = []
    for ln in raw.splitlines():
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        out.append(None if s == "-" else s)
    return out, len(out)


def embed_logo(path, max_h=200):
    """Return a data URI for the logo, downscaled via Pillow when available."""
    lower = path.lower()
    if lower.endswith((".jpg", ".jpeg")):
        mime = "image/jpeg"
    else:
        mime = "image/png"
    data = open(path, "rb").read()
    try:
        from PIL import Image  # optional: shrink for lighter HTML
        im = Image.open(io.BytesIO(data))
        if im.height > max_h:
            w = round(im.width * max_h / im.height)
            im = im.resize((w, max_h), Image.LANCZOS)
        buf = io.BytesIO()
        if mime == "image/jpeg" and im.mode in ("RGBA", "P"):
            im = im.convert("RGB")
        im.save(buf, "PNG" if mime == "image/png" else "JPEG", optimize=True)
        data = buf.getvalue()
    except Exception:
        pass  # embed original bytes
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def image_size(path):
    """(width, height) of a PNG/JPEG/GIF via pure stdlib header parsing."""
    with open(path, "rb") as f:
        head = f.read(32)
        f.seek(0)
        data = f.read()
    if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) > 24:
        w = int.from_bytes(data[16:20], "big")
        h = int.from_bytes(data[20:24], "big")
        return w, h
    if data[:6] in (b"GIF87a", b"GIF89a") and len(data) > 10:
        return int.from_bytes(data[6:8], "little"), int.from_bytes(data[8:10], "little")
    if data[:2] == b"\xff\xd8":  # JPEG: walk markers to a frame header
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3):
                h = int.from_bytes(data[i + 5:i + 7], "big")
                w = int.from_bytes(data[i + 7:i + 9], "big")
                return w, h
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            seg = int.from_bytes(data[i + 2:i + 4], "big")
            i += 2 + seg
    return None


# --------------------------------------------------------------------------- #
# HTML build
# --------------------------------------------------------------------------- #

CSS_TMPL = Template("""
@page { size: ${pw}mm ${ph}mm; margin: 0; }

html, body {
  margin: 0;
  padding: 0;
  width: ${pw}mm;
  background: #ffffff;
  font-family: ${font};
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}

* { box-sizing: border-box; }

p, div, span { overflow-wrap: break-word; }

.page {
  width: ${pw}mm;
  height: ${ph}mm;
  position: relative;
  padding: ${margin}mm;
  background: #ffffff;
}

.grid {
  display: grid;
  grid-template-columns: repeat(${cols}, 1fr);
  border: ${cut_w}mm ${cut_style} ${cut_color};
}

.token {
  display: flex;
  max-width: 100%;
  border-right: ${cut_w}mm ${cut_style} ${cut_color};
  border-bottom: ${cut_w}mm ${cut_style} ${cut_color};
}
.token.last-col { border-right: none; }
.token.last-row { border-bottom: none; }
.token.stub-left { flex-direction: row-reverse; }

.main {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
  padding: ${mp_t}mm ${mp_r}mm ${mp_b}mm ${mp_l}mm;
  ${main_border_css}
}
.token.stub-left .main { padding: ${mp_t}mm ${mp_l}mm ${mp_b}mm ${mp_r}mm; }

.school {
  display: flex;
  align-items: center;
  gap: 1.1mm;
  max-width: 100%;
}
.logo {
  height: ${logo_h}mm;
  width: ${logo_w}mm;
  flex-shrink: 0;
  object-fit: contain;
  ${logo_bg}
}
.school-name {
  font-size: ${school_pt}pt;
  font-weight: 700;
  color: ${ink};
  line-height: 1.38;
  letter-spacing: 0.05em;
  word-spacing: 0.16em;
  white-space: nowrap;
}

.title {
  font-size: ${title_pt}pt;
  font-weight: 900;
  color: ${title_color};
  letter-spacing: 0.045em;
  line-height: 1;
  margin-top: 1.2mm;
  white-space: nowrap;
}

.class-line {
  font-size: ${class_pt}pt;
  font-weight: 700;
  color: ${ink};
  letter-spacing: 0.02em;
  line-height: 1.25;
  margin-top: 0.8mm;
  white-space: nowrap;
}

.foot { margin-top: auto; }
.foot .drow {
  text-align: right;
  margin-bottom: 0.4mm;
}
.band {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1.2mm;
  background: ${band_bg};
  color: ${band_text};
  border-radius: 1.1mm;
  padding: 0.55mm 1.3mm;
  margin-top: 0.6mm;
  overflow: hidden;
  ${band_border_css}
}
.band-price {
  font-size: ${band_price_pt}pt;
  font-weight: 800;
  letter-spacing: 0.03em;
  line-height: 1.1;
  white-space: nowrap;
  min-width: 0;
}
.band-no {
  display: flex;
  align-items: baseline;
  gap: 0.7mm;
  white-space: nowrap;
  min-width: 0;
}
.band-no-label {
  font-size: ${band_nol_pt}pt;
  font-weight: 700;
  letter-spacing: 0.14em;
  margin-right: -0.14em;
  opacity: 0.85;
  line-height: 1.1;
}
.band-num {
  font-size: ${band_num_pt}pt;
  font-weight: 900;
  line-height: 1.1;
  letter-spacing: 0.02em;
}
.drow {
  font-size: ${det_pt}pt;
  font-weight: 600;
  color: ${muted};
  line-height: 1.55;
  white-space: nowrap;
}
.drow .val {
  font-weight: 800;
  color: ${accent};
  letter-spacing: 0.03em;
}
.drow.name-row {
  font-size: ${name_pt}pt;
  font-weight: 700;
  color: ${ink};
  margin-top: 0.6mm;
}
.name-row .name-val {
  font-weight: 800;
  color: ${accent};
  letter-spacing: 0.03em;
}
.blank {
  display: inline-block;
  width: ${blank_w}mm;
  height: 1.05mm;
  border-bottom: 0.28mm solid ${muted};
  margin-left: 0.7mm;
}

.stub {
  flex: 0 0 ${stub_w}mm;
  width: ${stub_w}mm;
  background: ${stub_bg};
  color: ${stub_text};
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: space-between;
  padding: ${sp_t}mm 0.6mm 1.5mm;
  text-align: center;
  ${stub_border_css}
}
.stub-party {
  font-size: ${party_pt}pt;
  font-weight: 800;
  letter-spacing: 0.09em;
  line-height: 1.5;
}
.stub-party .yr { font-size: ${yr_pt}pt; letter-spacing: 0.12em; }
.stub-sep {
  width: 62%;
  border-top: 0.28mm solid ${stub_sep};
  margin: 1.0mm 0;
}
.stub-no {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.stub-no-label {
  font-size: ${nolabel_pt}pt;
  font-weight: 700;
  letter-spacing: 0.22em;
  opacity: 0.9;
  margin-bottom: 0.6mm;
  margin-right: -0.22em;
}
.stub-num {
  font-size: ${num_pt}pt;
  font-weight: 900;
  line-height: 1;
  letter-spacing: 0.02em;
}

/* Browser preview: scale a full page into the viewport (print unaffected) */
@media screen {
  html {
    height: auto;
    display: flex;
    justify-content: center;
    background: #ffffff;
  }
  body {
    transform-origin: top center;
    scale: min(1, calc(100vw / ${w_px}), calc(100vh / ${h_px}));
    margin: 0 auto;
    box-shadow: 0 0 40px rgba(14,47,82,0.18);
  }
}
""")

TOKEN_TMPL = """    <div class="token{cls}">
      <div class="main">
{school}        <div class="title">{title}</div>
{class_line}@@NAMEROW@@{rule_details}      </div>
      <div class="stub">
{stub_party}{stub_sep}{stub_no}      </div>
    </div>"""


def build_html(a, th):
    pw, ph = a["page_size"]
    margin = a["margin"]
    cols, rows = a["cols"], a["rows"]
    per_page = cols * rows
    count = a["count"]

    grid_w = pw - 2 * margin
    token_h = (ph - 2 * margin) / rows
    token_w = grid_w / cols

    # auto-shrink type when tickets get smaller than the reference design
    eff = a["font_scale"] * min(1.0, token_h / 28.5, token_w / 49.5)
    eff = max(0.35, eff)

    # vertical auto-fit: the name row (and the footer band) make the
    # content stack taller than the fixed cell; scale everything down so the
    # tallest possible ticket still fits its cell.
    names_list = a.get("names_list") or []
    has_names = bool(names_list)
    has_price = a["price"] not in ("", "none", "None")
    dd = a["draw_date"]
    has_dd = dd is not None and dd not in ("", "none", "None")
    has_band = has_price or a["split_stub"]
    school_lines = (a["school"].count("|") + 1) if a["school"] else 0
    school_h_per_eff = max(6.2 * a["logo_scale"],
                           school_lines * 4.6 * 0.3528 * 1.38)
    stack_a = (school_h_per_eff
               + 11.5 * 0.3528            # title, line-height 1
               + 7 * 0.3528 * 1.25        # class line
               + (9 * 0.3528 * 1.3 if has_names else 0)
               + (6 * 1.6 * 0.3528 * 1.1 if has_band else 0)  # band number line
               + (6 * 0.3528 * 1.55 if has_dd else 0))         # date row
    stack_b = (1.2 + 0.8 + (0.6 if has_names else 0)
               + (0.6 + 0.55 * 2 + 0.35 if has_band else 0)   # band gap + pad + border
               + (0.4 if has_dd else 0)
               + 1.3 + 1.2)
    if stack_a * eff + stack_b > token_h:
        eff = max(0.4, (token_h - stack_b) / stack_a)

    pe = max(0.55, eff)

    pad = a["pad"]
    first_n, last_n = a["start"], a["start"] + count - 1
    if pad < len(str(abs(last_n))):
        pad = len(str(abs(last_n)))

    def fmt(n):
        return f"{a['number_prefix']}{n:0{pad}d}{a['number_suffix']}"

    last_num_str = fmt(last_n)
    num_base = min(16.0, max(6.0, 42.0 / max(1, len(last_num_str))))
    num_pt = num_base * (a["stub_width"] / 12.0) * eff

    # ---- logo
    # When embedding, the data URI goes into the CSS ONCE (not per ticket) and
    # tickets reference it via a background-image div — keeps 480-ticket HTML
    # at ~200 KB instead of ~20 MB.
    logo_html = ""
    logo_bg = ""
    aspect = 1
    if a["logo"] and not a["no_logo"]:
        if os.path.exists(a["logo"]):
            if a["embed_logo"]:
                uri = embed_logo(a["logo"])
                size = image_size(a["logo"]) or (1, 1)
                aspect = size[0] / max(1, size[1])
                logo_bg = (f'background: url("{uri}") center / contain no-repeat;')
                logo_html = '<div class="logo"></div>'
            else:
                logo_html = (f'<img class="logo" src="file://{os.path.abspath(a["logo"])}" '
                             f'alt="logo" style="width:auto;max-width:100%;">')
        else:
            print(f"warning: logo file not found: {a['logo']!r} — continuing without it",
                  file=sys.stderr)

    # ---- school block (logo + name); shrink the name when a big logo eats width
    main_w = token_w - a["stub_width"] - (2.0 + 1.6) * pe
    logo_w_eff = 6.2 * eff * a["logo_scale"] * aspect
    avail_1x = main_w - 1.1 - 6.2 * eff * aspect
    avail = main_w - 1.1 - logo_w_eff
    school_scale = max(0.45, min(1.0, avail / max(avail_1x, 1)))
    school_html = ""
    if a["school"]:
        name_html = f'<div class="school-name">{lines(a["school"])}</div>'
        inner = (logo_html + name_html) if logo_html else name_html
        school_html = f"        <div class=\"school\">{inner}</div>\n"
    elif logo_html:
        school_html = f'        <div class="school">{logo_html}</div>\n'

    # ---- footer: optional draw-date row, then the price/number band that
    # gives the buyer's half its own block of theme colour (the stub is torn
    # off and dropped in the jar; the band is what the buyer keeps looking at)
    date_row = ""
    if has_dd:
        if dd in ("_", "blank"):
            date_row = (f'          <div class="drow">{esc(a["draw_date_label"])}:'
                        f'<span class="blank"></span></div>\n')
        else:
            date_row = (f'          <div class="drow">{esc(a["draw_date_label"])}: '
                        f'<span class="val">{esc(dd)}</span></div>\n')
    band_html = ""
    if has_band:
        price_span = (f'<span class="band-price">{esc(a["price"])}</span>'
                      if has_price else "")
        # {num} is expanded after .format() like the stub number
        no_span = ("<span class=\"band-no\"><span class=\"band-no-label\">No.</span>"
                   "<span class=\"band-num\">{num}</span></span>"
                   if a["split_stub"] else "")
        band_html = f'        <div class="band">{price_span}{no_span}</div>\n'
    if date_row or band_html:
        rule_details = ('        <div class="foot">\n'
                        + date_row + band_html + '        </div>\n')
    else:
        rule_details = "\n"

    class_line = (f'        <div class="class-line">{lines(a["class_line"])}</div>\n'
                  if a["class_line"] else "")

    # ---- stub
    party = a["party"]
    stub_party = ""
    if party:
        if "|" in party:
            yr, rest = party.split("|", 1)
        else:
            yr, rest = "", party
        parts = []
        if yr:
            parts.append(f'<span class="yr">{esc(yr)}</span>')
        parts += [esc(w) for w in rest.split()]
        stub_party = f'        <div class="stub-party">{"<br>".join(parts)}</div>\n'
    stub_sep = '        <div class="stub-sep"></div>\n' if stub_party else ""
    stub_no = '        <div class="stub-no">\n'
    if a["number_label"]:
        stub_no += f'          <div class="stub-no-label">{esc(a["number_label"])}</div>\n'
    stub_no += '          <div class="stub-num">{num}</div>\n        </div>\n'

    stub_border_css = ""
    boundary = "left" if a["stub_side"] == "right" else "right"
    if th["stub_border_w"] > 0 and not a["split_stub"]:
        stub_border_css = (f"border-{boundary}: {mm(th['stub_border_w'])}mm "
                           f"solid {th['ink']};")
    band_border_css = ""
    if th["band_border_w"] > 0:
        band_border_css = (f"border: {mm(th['band_border_w'])}mm "
                           f"solid {th['ink']};")
    # Tear line between the buyer's half and the jar stub. Drawn on the WHITE
    # body element, not on the gradient stub: a dashed border on a gradient
    # background forces Chromium to emit thousands of tiny path segments
    # (8 MB PDFs instead of ~1 MB).
    main_border_css = ""
    if a["split_stub"]:
        side = "right" if a["stub_side"] == "right" else "left"
        main_border_css = (f"border-{side}: {mm(a['cut_weight'])}mm "
                           f"{a['cut_style']} {th['cut']};")

    css = CSS_TMPL.substitute(
        pw=mm(pw), ph=mm(ph), margin=mm(margin),
        cols=cols,
        cut_w=mm(a["cut_weight"]), cut_style=a["cut_style"], cut_color=th["cut"],
        font=th["font"],
        mp_t=mm(1.3 * pe), mp_r=mm(1.6 * pe), mp_b=mm(1.2 * pe), mp_l=mm(2.0 * pe),
        main_border_css=main_border_css,
        logo_h=mm(6.2 * eff * a["logo_scale"]),
        logo_w=mm(6.2 * eff * a["logo_scale"] * (aspect if logo_bg else 1)),
        logo_bg=logo_bg,
        school_pt=pt(4.6 * eff * school_scale),
        ink=th["ink"], title_color=th["title"], title_pt=pt(11.5 * eff),
        class_pt=pt(7.0 * eff),
        rule_color=th["rule"], det_pt=pt(6.0 * eff), muted=th["muted"],
        accent=th["accent"], blank_w=mm(a["blank_width"]),
        band_bg=th["band_bg"], band_text=th["band_text"],
        band_border_css=band_border_css,
        band_price_pt=pt(6.0 * 1.15 * eff), band_nol_pt=pt(6.0 * 0.8 * eff),
        band_num_pt=pt(6.0 * 1.6 * eff),
        stub_w=mm(a["stub_width"]), stub_bg=th["stub_bg"], stub_text=th["stub_text"],
        stub_border_css=stub_border_css,
        sp_t=mm(2.1 * pe), party_pt=pt(4.8 * eff), yr_pt=pt(5.6 * eff),
        stub_sep=th["stub_sep"], nolabel_pt=pt(4.2 * eff), num_pt=pt(num_pt),
        name_pt=pt(9.0 * eff),
        w_px=round(pw / 25.4 * 96), h_px=round(ph / 25.4 * 96),
    )

    # ---- sheets
    label_txt = (esc(a["name_label"]) + " ") if a["name_label"] else ""
    label_len = len(a["name_label"]) + 1 if a["name_label"] else 0
    avail_name_mm = max(8.0, token_w - a["stub_width"] - (2.0 + 1.6) * pe - 1.0)

    def name_row(gi):
        if gi >= len(names_list):
            return ""
        nm = names_list[gi]
        if nm is None:
            return (f'        <div class="drow name-row">{label_txt}'
                    f'<span class="blank"></span></div>\n')
        # shrink long names so they never leave the ticket (VIP holder names
        # print large: base 9pt, second only to the title)
        size = min(9.0 * eff,
                   avail_name_mm / max(1.0, (label_len + len(nm)) * 0.194))
        size = max(3.5, size)
        return (f'        <div class="drow name-row" style="font-size: {pt(size)}pt">'
                f'{label_txt}<span class="name-val">{esc(nm)}</span></div>\n')

    sheets = math.ceil(count / per_page)
    pages = []
    for s in range(sheets):
        sheet_count = min(per_page, count - s * per_page)
        rows_s = math.ceil(sheet_count / cols)
        gh_s = token_h * rows_s
        toks = []
        for i in range(sheet_count):
            classes = ""
            if i % cols == cols - 1:
                classes += " last-col"
            if i // cols == rows_s - 1:
                classes += " last-row"
            if a["stub_side"] == "left":
                classes += " stub-left"
            tok = TOKEN_TMPL.format(
                cls=classes,
                school=school_html,
                title=esc(a["title"]),
                class_line=class_line,
                rule_details=rule_details,
                stub_party=stub_party, stub_sep=stub_sep, stub_no=stub_no,
            )
            # {num} sits inside the stub_no value, so expand it after .format()
            tok = tok.replace("{num}", fmt(a["start"] + s * per_page + i))
            tok = tok.replace("@@NAMEROW@@", name_row(s * per_page + i))
            toks.append(tok)
        pages.append(
            '  <div class="page">\n'
            f'    <div class="grid" style="height: {mm(gh_s)}mm; '
            f'grid-template-rows: repeat({rows_s}, 1fr);">\n'
            + "\n".join(toks) + "\n    </div>\n  </div>"
        )

    font_link = ""
    if th["webfont"] and a["webfonts"]:
        font_link = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
                     '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
                     f'<link href="https://fonts.googleapis.com/css2?family={th["webfont"]}" '
                     'rel="stylesheet">\n')

    doc_title = " — ".join(x for x in (a["title"], a["class_line"]) if x)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{esc(doc_title)}</title>
{font_link}<style>{css}</style>
</head>
<body>
{chr(10).join(pages)}
</body>
</html>
"""


# --------------------------------------------------------------------------- #
# PDF / preview rendering (Playwright)
# --------------------------------------------------------------------------- #

def _launch(html_path):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("error: --pdf/--preview need Playwright.  Install with:\n"
                 "  pip install playwright && python -m playwright install chromium")
    import re
    m = re.search(r"@page\s*{[^}]*size:\s*([\d.]+)mm\s+([\d.]+)mm",
                  open(html_path, encoding="utf-8").read())
    pw = round(float(m.group(1)) / 25.4 * 96) if m else 794
    ph = round(float(m.group(2)) / 25.4 * 96) if m else 1123
    ctx = sync_playwright().start()
    browser = ctx.chromium.launch()
    page = browser.new_page(viewport={"width": pw, "height": ph},
                            device_scale_factor=2)
    page.goto("file://" + os.path.abspath(html_path))
    page.wait_for_load_state("networkidle")
    page.evaluate("document.fonts.ready")
    page.wait_for_timeout(250)
    return ctx, browser, page


def render_pdf(html_path, pdf_path):
    ctx, browser, page = _launch(html_path)
    page.pdf(path=pdf_path, print_background=True, prefer_css_page_size=True)
    browser.close()
    ctx.stop()


def render_preview(html_path, png_path):
    ctx, browser, page = _launch(html_path)
    page.locator(".page").first.screenshot(path=png_path)
    browser.close()
    ctx.stop()


def set_metadata(pdf_path, title, author, subject):
    try:
        import pikepdf
    except ImportError:
        return
    with pikepdf.open(pdf_path, allow_overwriting_input=True) as pdf:
        pdf.docinfo["/Title"] = title
        pdf.docinfo["/Author"] = author
        pdf.docinfo["/Subject"] = subject
        pdf.docinfo["/Creator"] = "raffle-draw (github.com/RohanDaCoder/raffle-draw)"
        pdf.docinfo["/Producer"] = "raffle-draw"
        pdf.save(pdf_path)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def build_parser():
    ap = argparse.ArgumentParser(
        prog="raffle_gen.py",
        description="Print-ready raffle ticket sheet generator "
                    "(mm-exact HTML + vector PDF via headless Chromium).",
        epilog="""examples:
  %(prog)s --count 480 --pdf tickets.pdf
  %(prog)s --theme bw --no-logo --price "Tk 10" --pdf tickets.pdf
  %(prog)s --page letter --cols 5 --rows 8 --count 200 --preview p.png
  %(prog)s --config myraffle.json --pdf tickets.pdf
  %(prog)s --theme gold --title "VIP TICKET" --names vip_list.json \\
      --name-label "" --start 481 --pdf vip.pdf

tips:
  * multi-line texts: separate lines with '|'  (e.g. --school "SCHOOL A|& COLLEGE")
  * --draw-date "_" prints a blank fill-in line; omit it to hide the row
  * --price none hides the price row
  * --names FILE prints a holder name on each ticket (VIP / pre-orders):
    JSON (recommended) — a name -> ticket-count map like {"Topu": 5} or a
    list of {"name": ..., "tickets": ...} entries; a legacy one-name-per-line
    text file also works; count defaults to the total ticket count
  * values that start with '-' need '=' syntax:  --number-suffix=-Z
  * PDF/preview need:  pip install playwright && python -m playwright install chromium
""",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    ap.add_argument("--config", metavar="JSON",
                    help="JSON file with any option below (long-option names as keys); "
                         "explicit command-line flags win")

    g = ap.add_argument_group("content")
    g.add_argument("--title", default="RAFFLE DRAW", help="main title (default: %(default)s)")
    g.add_argument("--school", default="", metavar="TEXT",
                   help='school/organisation name; "|" splits lines (logo shown beside it)')
    g.add_argument("--class-line", default="", dest="class_line", metavar="TEXT",
                   help='line under the title, e.g. "Class 9 · Section D"')
    g.add_argument("--party", default="", metavar="YEAR|TEXT",
                   help='stub text, e.g. "2026|CLASS PARTY" (year shown larger)')
    g.add_argument("--price", default="", metavar="TEXT",
                   help='price value shown in the footer band, e.g. "Tk 10";'
                        ' empty or "none" hides the band')
    g.add_argument("--draw-date", default=None, dest="draw_date", metavar="TEXT",
                   help='date value; "_" = blank fill-in line; "none"/omitted hides the row')
    g.add_argument("--draw-date-label", default="Draw Date", dest="draw_date_label",
                   metavar="TEXT")
    g.add_argument("--logo", default="", metavar="PATH", help="logo image (PNG/JPG)")
    g.add_argument("--logo-scale", type=float, default=1.0, dest="logo_scale",
                   metavar="X", help="logo size multiplier; base height is 6.2 mm "
                   "before auto-shrink (default %(default)s)")
    g.add_argument("--no-logo", dest="no_logo", action="store_true",
                   help="never draw a logo")
    g.add_argument("--embed-logo", dest="embed_logo", action=argparse.BooleanOptionalAction,
                   default=True,
                   help="embed logo as base64 so the HTML is one self-contained file "
                        "(default: %(default)s)")
    g.add_argument("--number-label", default="NO.", dest="number_label", metavar="TEXT",
                   help='label above the stub number; "" hides it')
    g.add_argument("--names", default="", metavar="FILE",
                   help="holder names for named (VIP) tickets: JSON — either a "
                        "name -> ticket-count map like {\"Topu\": 5} or a list "
                        "of {\"name\": ..., \"tickets\": ...} entries (also "
                        "wrapped as {\"preorders\": [...]}); a one-name-per-line "
                        "text file still works. Tickets are numbered in file "
                        "order; count defaults to the total")
    g.add_argument("--name-label", default="Name", dest="name_label", metavar="TEXT",
                   help='label before the holder name; "" shows the name alone '
                        '(default %(default)s)')

    g = ap.add_argument_group("numbering")
    g.add_argument("--count", type=int, default=None, metavar="N",
                   help="total number of tickets (default 40, unless --sheets given)")
    g.add_argument("--sheets", type=int, default=None, metavar="N",
                   help="alternative to --count: N full sheets of cols x rows tickets")
    g.add_argument("--start", type=int, default=1, metavar="N",
                   help="first ticket number (default %(default)s)")
    g.add_argument("--pad", type=int, default=3, metavar="N",
                   help="zero-padding width (default %(default)s; widened automatically)")
    g.add_argument("--number-prefix", default="", dest="number_prefix", metavar="TEXT")
    g.add_argument("--number-suffix", default="", dest="number_suffix", metavar="TEXT")

    g = ap.add_argument_group("layout")
    g.add_argument("--cols", type=int, default=4, metavar="N",
                   help="ticket columns per sheet (default %(default)s)")
    g.add_argument("--rows", type=int, default=10, metavar="N",
                   help="ticket rows per sheet (default %(default)s)")
    g.add_argument("--page", default="a4", metavar="SIZE",
                   help="a3|a4|a5|a6|letter|legal|tabloid or custom WxH mm "
                        "(default %(default)s)")
    g.add_argument("--margin", type=float, default=6.0, metavar="MM",
                   help="sheet margin in mm (default %(default)s — keep inside your "
                        "printer's hardware no-print zone)")
    g.add_argument("--stub-width", type=float, default=12.0, dest="stub_width",
                   metavar="MM", help="number-stub width (default %(default)s)")
    g.add_argument("--stub-side", default="right", choices=["right", "left"],
                   help="which side of the ticket carries the stub (default %(default)s)")
    g.add_argument("--split-stub", dest="split_stub", action=argparse.BooleanOptionalAction,
                   default=False,
                   help="two-part ticket: dashed tear line between body and stub, "
                        "number on BOTH halves — at sale time the stub drops into "
                        "the jar and the buyer keeps the body (default: %(default)s)")

    g = ap.add_argument_group("style")
    g.add_argument("--theme", default="festive", choices=sorted(THEMES),
                   help="colour theme (default %(default)s)")
    g.add_argument("--accent", default=None, metavar="COLOR",
                   help="override accent colour (price value, highlights)")
    g.add_argument("--ink", default=None, metavar="COLOR",
                   help="override main text colour")
    g.add_argument("--muted", default=None, metavar="COLOR",
                   help="override secondary text colour")
    g.add_argument("--cut-color", default=None, dest="cut_color", metavar="COLOR",
                   help="override cut-line colour")
    g.add_argument("--cut-style", default="dashed", choices=["dashed", "solid", "none"],
                   dest="cut_style", help="cut-line style (default %(default)s)")
    g.add_argument("--cut-weight", type=float, default=0.25, dest="cut_weight",
                   metavar="MM", help="cut-line thickness (default %(default)s)")
    g.add_argument("--font-family", default=None, dest="font_family", metavar="STACK",
                   help="override the theme font stack completely")
    g.add_argument("--webfonts", dest="webfonts", action=argparse.BooleanOptionalAction,
                   default=True,
                   help="load theme webfont from Google Fonts (default: %(default)s)")
    g.add_argument("--font-scale", type=float, default=1.0, dest="font_scale",
                   metavar="X", help="multiply all font sizes (default %(default)s; "
                   "auto-reduced when tickets are smaller than the reference design)")
    g.add_argument("--blank-width", type=float, default=13.0, dest="blank_width",
                   metavar="MM", help="fill-in line width for blank fields")

    g = ap.add_argument_group("output")
    g.add_argument("--html", default="", metavar="PATH", help="write HTML sheet")
    g.add_argument("--pdf", default="", metavar="PATH", help="write vector PDF (Playwright)")
    g.add_argument("--preview", default="", metavar="PATH",
                   help="write PNG preview of sheet 1 (Playwright)")
    g.add_argument("--quiet", "-q", action="store_true", help="suppress the summary")

    g = ap.add_argument_group("info")
    g.add_argument("--list-themes", action="store_true", help="print themes and exit")
    g.add_argument("--list-pages", action="store_true", help="print page sizes and exit")
    return ap


def apply_config(ap, args):
    if not args.config:
        return
    with open(args.config, encoding="utf-8") as f:
        conf = json.load(f)
    dests = {a.dest for a in ap._actions} - {"config", "help"}
    argv = sys.argv[1:]
    for k, v in conf.items():
        if k not in dests:
            print(f"warning: unknown config key '{k}' ignored", file=sys.stderr)
            continue
        opts = [o for a in ap._actions if a.dest == k for o in a.option_strings]
        if any(o in argv for o in opts):
            continue  # explicit CLI flag wins
        setattr(args, k, v)


def main():
    ap = build_parser()
    args = ap.parse_args()

    if args.list_themes:
        for name, t in sorted(THEMES.items()):
            print(f"{name:10} stub {t['stub_bg'][:40]:42} font {t['font'].split(',')[0]}")
        return
    if args.list_pages:
        for name, (w, h) in sorted(PAGE_SIZES.items()):
            print(f"{name:8} {w:g} x {h:g} mm")
        return

    apply_config(ap, args)

    args.names_list, n_holders = parse_names(args.names)

    per_page = args.cols * args.rows
    if args.count is None:
        if args.names_list:
            args.count = len(args.names_list)
        elif args.sheets:
            args.count = args.sheets * per_page
        else:
            args.count = 40
    if args.count < 1:
        sys.exit("error: --count must be >= 1"
                 + (" (names file has no entries)" if args.names else ""))
    if args.names_list and len(args.names_list) > args.count:
        print(f"warning: names file has {len(args.names_list)} entries but only "
              f"{args.count} tickets — extras ignored", file=sys.stderr)
    if args.cols < 1 or args.rows < 1:
        sys.exit("error: --cols and --rows must be >= 1")
    if args.count % args.cols:
        print(f"note: count {args.count} is not a multiple of {args.cols} columns — "
              f"the last row of the final sheet will have empty cells", file=sys.stderr)

    args.page_size = parse_page(args.page)

    th = dict(THEMES[args.theme])
    if args.accent:
        th["accent"] = args.accent
    if args.ink:
        th["ink"] = args.ink
        th["title"] = args.ink
    if args.muted:
        th["muted"] = args.muted
    if args.cut_color:
        th["cut"] = args.cut_color
    if args.font_family:
        th["font"] = args.font_family

    a = vars(args)

    # figure out where the HTML lives
    tmp_dir = None
    html_path = args.html
    if not html_path and (args.pdf or args.preview):
        if not args.embed_logo and args.logo and not args.no_logo:
            print("note: no --html given — embedding the logo so the sheet is "
                  "self-contained", file=sys.stderr)
            args.embed_logo = True
        import tempfile
        tmp_dir = tempfile.mkdtemp(prefix="raffle_")
        html_path = os.path.join(tmp_dir, "sheet.html")

    html = build_html(a, th)
    os.makedirs(os.path.dirname(os.path.abspath(html_path)), exist_ok=True)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    if args.pdf:
        os.makedirs(os.path.dirname(os.path.abspath(args.pdf)), exist_ok=True)
        render_pdf(html_path, args.pdf)
        pad = max(args.pad, len(str(abs(args.start + args.count - 1))))
        first = f"{args.start:0{pad}d}"
        last = f"{args.start + args.count - 1:0{pad}d}"
        set_metadata(
            args.pdf,
            title=" — ".join(x for x in (args.title, args.class_line) if x) or "Raffle tickets",
            author=(args.school.split("|")[0].strip() if args.school else "raffle-draw"),
            subject=(f"{args.count} numbered raffle tickets ({first}–{last}), "
                     f"{per_page} per sheet, "
                     + (f"price {args.price}, " if args.price not in ("", "none") else "")
                     + f"{args.cut_style} cut lines"),
        )

    if args.preview:
        os.makedirs(os.path.dirname(os.path.abspath(args.preview)), exist_ok=True)
        render_preview(html_path, args.preview)

    if tmp_dir:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)

    if not args.quiet:
        sheets = math.ceil(args.count / per_page)
        pad = max(args.pad, len(str(abs(args.start + args.count - 1))))
        named = ""
        if args.names_list:
            named = (f", {n_holders} holder{'s' if n_holders != 1 else ''}, "
                     f"{len(args.names_list)} named tickets")
        print(f"{args.count} tickets ({args.start:0{pad}d}–{args.start + args.count - 1:0{pad}d})"
              f"{named} on {sheets} sheet{'s' if sheets != 1 else ''} of {args.cols}x{args.rows}"
              f" ({args.page} {args.page_size[0]:g}x{args.page_size[1]:g}mm,"
              f" margin {args.margin:g}mm, theme {args.theme})")
        for label, p in (("html", args.html), ("pdf", args.pdf), ("preview", args.preview)):
            if p:
                print(f"  {label:8} -> {p}")


if __name__ == "__main__":
    main()
