#!/usr/bin/env bash
# VIP pre-order tickets: gold theme, holder's name printed on each ticket.
# Numbering continues after the standard run (481+), so every stub in the
# mixing jar stays unique. Ticket count comes from the names file.
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
  --names examples/vip_names.txt \
  --name-label "" \
  --html dist/vip_tickets.html \
  --pdf  dist/vip_tickets.pdf \
  --preview dist/vip_preview.png
