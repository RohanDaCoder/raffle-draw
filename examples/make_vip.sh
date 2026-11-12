#!/usr/bin/env bash
# VIP pre-order tickets: gold theme, holder's name printed on each ticket.
#
# The pre-order list is examples/vip_list.json — a JSON map of holder name to
# ticket count. The ticket total follows the file automatically; numbering
# continues after the standard run (481+), so every stub in the mixing jar
# stays unique.
#
# Same format as the standard batch (4x10 grid, identical sizes and
# positions) — only the gold theme, the VIP title, the holder names and
# the 481+ numbering differ. 15 pre-orders = one short A4 sheet.
set -euo pipefail
cd "$(dirname "$0")/.."

python3 raffle_gen.py \
  --start 481 \
  --title "VIP TICKET" \
  --school "CIVIL AVIATION SCHOOL|& COLLEGE, KURMITOLA" \
  --class-line "Class 9 · Section D" \
  --party "2026|CLASS PARTY" \
  --price "10tk" \
  --logo examples/casck_logo.png \
  --logo-scale 1.3 \
  --split-stub \
  --theme gold \
  --names examples/vip_list.json \
  --name-label "" \
  --html dist/vip_tickets.html \
  --pdf  dist/vip_tickets.pdf \
  --preview dist/vip_preview.png
