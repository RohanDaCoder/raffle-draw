#!/usr/bin/env bash
# VIP pre-order tickets: gold theme, holder's name printed on each ticket.
#
# The pre-order list is examples/vip_list.json — a JSON map of holder name to
# ticket count. The ticket total follows the file automatically; numbering
# continues after the standard run (481+), so every stub in the mixing jar
# stays unique.
#
# 15 pre-orders = one perfectly full 3x5 A4 sheet (no wasted paper). If the
# list grows past 15, raise --rows to the next multiple of 3 to keep full
# sheets (e.g. 18 tickets -> --rows 6), or keep 5 and accept a short last
# sheet.
set -euo pipefail
cd "$(dirname "$0")/.."

python3 raffle_gen.py \
  --start 481 \
  --title "VIP TICKET" \
  --school "CIVIL AVIATION SCHOOL|& COLLEGE, KURMITOLA" \
  --class-line "Class 9 · Section D" \
  --party "2026|CLASS PARTY" \
  --price "Tk 10" \
  --logo examples/casck_logo.png \
  --logo-scale 1.3 \
  --split-stub \
  --theme gold \
  --cols 3 --rows 5 \
  --font-scale 1.2 \
  --names examples/vip_list.json \
  --name-label "" \
  --html dist/vip_tickets.html \
  --pdf  dist/vip_tickets.pdf \
  --preview dist/vip_preview.png
