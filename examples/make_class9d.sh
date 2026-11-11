#!/usr/bin/env bash
# Reproduce the Class 9 · Section D batch:
# 480 two-part tickets (001-480), Tk 10, CASCK branding, festive aviation blue.
# --split-stub: tear line between body and stub, number on BOTH halves —
# the stub drops into the mixing jar at sale time, the buyer keeps the body.
set -euo pipefail
cd "$(dirname "$0")/.."

python3 raffle_gen.py \
  --count 480 \
  --title "RAFFLE DRAW" \
  --school "CIVIL AVIATION SCHOOL|& COLLEGE, KURMITOLA" \
  --class-line "Class 9 · Section D" \
  --party "2026|CLASS PARTY" \
  --price "Tk 10" \
  --logo examples/casck_logo.png \
  --logo-scale 1.2 \
  --split-stub \
  --html dist/raffle_tickets.html \
  --pdf  dist/raffle_tickets.pdf \
  --preview dist/preview.png
