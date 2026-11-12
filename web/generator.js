/*
 * raffle-draw web generator — the layout engine of raffle_gen.py ported to
 * jsPDF, so tickets can be generated entirely in the browser (no server, no
 * login). Same millimetre math, same themes: phone-built sheets match the
 * CI/Playwright-built releases.
 *
 * Works as a browser global (RaffleGen) and in Node (module.exports) for
 * testing. MIT licensed — see repository.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    var j = require("./vendor/jspdf.umd.min.js");
    module.exports = factory(j.jsPDF || j.default || j);
  } else {
    root.RaffleGen = factory(root.jspdf && root.jspdf.jsPDF);
  }
})(typeof self !== "undefined" ? self : this, function (jsPDF) {
  "use strict";

  if (!jsPDF) throw new Error("jsPDF is not loaded");

  var PT2MM = 0.3528;        // 1 pt in mm
  var ASC = 0.75;            // helvetica ascent factor (calibrated: caps 0.738)

  // ------------------------------------------------------------------ themes
  var THEMES = {
    festive: {
      cut: [159, 179, 201], rule: [219, 231, 244], muted: [70, 96, 122],
      ink: [14, 47, 82], title: [18, 88, 167], accent: [18, 88, 167],
      stubTop: [18, 88, 167], stubBot: [13, 63, 119],
      stubText: [255, 255, 255], stubSep: [255, 255, 255], stubSepOpacity: 0.55,
      bandBg: [18, 88, 167], bandText: [255, 255, 255]
    },
    gold: {
      cut: [217, 196, 122], rule: [240, 227, 184], muted: [107, 90, 38],
      ink: [43, 36, 16], title: [154, 114, 0], accent: [184, 134, 11],
      stubTop: [242, 201, 76], stubBot: [201, 151, 28],
      stubText: [43, 32, 0], stubSep: [43, 32, 0], stubSepOpacity: 0.4,
      bandBg: [201, 151, 28], bandText: [43, 32, 0]
    }
  };

  // ------------------------------------------------------------ the presets
  var PRESETS = {
    normal: {
      theme: "festive", cols: 4, rows: 10, fontScale: 1, splitStub: true,
      stubWidth: 12, title: "RAFFLE DRAW",
      school: "CIVIL AVIATION SCHOOL|& COLLEGE, KURMITOLA",
      classLine: "Class 9 \u00B7 Section D", party: "2026|CLASS PARTY",
      price: "Tk 10", numberLabel: "NO.", logoScale: 1.3
    },
    vip: {
      theme: "gold", cols: 3, rows: 5, fontScale: 1.2, splitStub: true,
      stubWidth: 12, title: "VIP TICKET",
      school: "CIVIL AVIATION SCHOOL|& COLLEGE, KURMITOLA",
      classLine: "Class 9 \u00B7 Section D", party: "2026|CLASS PARTY",
      price: "Tk 10", numberLabel: "NO.",
      nameLabel: "", logoScale: 1.3
    }
  };

  // ---------------------------------------------------------------- helpers
  function lerpC(a, b, t) {
    return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
  }
  function setFill(doc, c) { doc.setFillColor(c[0] | 0, c[1] | 0, c[2] | 0); }

  function baselineOf(topMm, sizePt, lh) {
    var s = sizePt * PT2MM;
    return topMm + ((lh - 1) / 2) * s + ASC * s;
  }

  // width of a string at the CURRENT font/size, plus letterspacing (mm)
  function textW(doc, str, cs) {
    var w = doc.getTextWidth(str);
    if (cs && str.length > 1) w += cs * (str.length - 1);
    return w;
  }

  // anchored text draw: {size, bold, color, cs, align}
  function drawText(doc, str, x, baselineY, o) {
    doc.setFont("helvetica", o.bold ? "bold" : "normal");
    doc.setFontSize(o.size);
    doc.setTextColor(o.color[0] | 0, o.color[1] | 0, o.color[2] | 0);
    var w = textW(doc, str, o.cs || 0);
    var xx = x;
    if (o.align === "center") xx = x - w / 2;
    else if (o.align === "right") xx = x - w;
    if (o.cs) doc.text(str, xx, baselineY, { charSpace: o.cs });
    else doc.text(str, xx, baselineY);
    return w;
  }

  // school line: bold ink, 0.05em letterspacing, 0.16em word spacing, left
  function drawSchoolLine(doc, line, x, baselineY, sizePt, color) {
    doc.setFont("helvetica", "bold");
    doc.setFontSize(sizePt);
    doc.setTextColor(color[0] | 0, color[1] | 0, color[2] | 0);
    var cs = 0.05 * sizePt * PT2MM, ws = 0.16 * sizePt * PT2MM;
    var words = line.split(" ");
    var cx = x;
    for (var i = 0; i < words.length; i++) {
      if (words[i]) doc.text(words[i], cx, baselineY, { charSpace: cs });
      cx += textW(doc, words[i], cs);
      if (i < words.length - 1) cx += doc.getTextWidth(" ") + ws;
    }
  }
  function schoolLineW(doc, line, sizePt) {
    doc.setFont("helvetica", "bold");
    doc.setFontSize(sizePt);
    var cs = 0.05 * sizePt * PT2MM, ws = 0.16 * sizePt * PT2MM;
    var words = line.split(" ");
    var w = 0;
    for (var i = 0; i < words.length; i++) {
      w += textW(doc, words[i], cs);
      if (i < words.length - 1) w += doc.getTextWidth(" ") + ws;
    }
    return w;
  }

  function padNum(n, pad) { return String(n).padStart(pad, "0"); }

  // ------------------------------------------------------- layout (the port)
  function computeLayout(doc, o, count) {
    var th = THEMES[o.theme || "festive"];
    var pw = o.pageW || 210, ph = o.pageH || 297;
    var margin = o.margin != null ? o.margin : 6;
    var cols = o.cols || 4, rows = o.rows || 10;
    var perPage = cols * rows;
    var gridW = pw - 2 * margin;
    var tokenH = (ph - 2 * margin) / rows;
    var tokenW = gridW / cols;

    var names = o.names || [];
    var hasNames = names.length > 0;
    var fontScale = o.fontScale || 1;
    var logoScale = o.logoScale || 1;
    var logo = o.logo || null;
    var splitStub = !!o.splitStub;
    var stubWidth = o.stubWidth != null ? o.stubWidth : 12;

    var eff = fontScale * Math.min(1, tokenH / 28.5, tokenW / 49.5);
    eff = Math.max(0.35, eff);

    var price = o.price;
    var showPrice = price != null && price !== "" && price !== "none" && price !== "None";
    var drawDate = o.drawDate;
    var showDD = drawDate != null && drawDate !== "" && drawDate !== "none" && drawDate !== "None";

    var hasBand = showPrice || splitStub;   // footer band: price + matching no.
    var hasDD = showDD;                     // small date row above the band
    var schoolLines = o.school ? o.school.split("|") : [];

    // vertical auto-fit (port of the stack_a/stack_b shrink in raffle_gen.py)
    var schoolHPerEff = Math.max(6.2 * logoScale,
                                 schoolLines.length * 4.6 * PT2MM * 1.38);
    var stackA = schoolHPerEff + 11.5 * PT2MM + 7 * PT2MM * 1.25 +
                 (hasNames ? 9 * PT2MM * 1.3 : 0) +
                 (hasBand ? 6 * 1.6 * PT2MM * 1.1 : 0) +
                 (hasDD ? 6 * PT2MM * 1.55 : 0);
    var stackB = 1.2 + 0.8 + (hasNames ? 0.6 : 0) +
                 (hasBand ? 0.6 + 1.1 + 0.35 : 0) + (hasDD ? 0.4 : 0) + 1.3 + 1.2;
    if (stackA * eff + stackB > tokenH) eff = Math.max(0.4, (tokenH - stackB) / stackA);
    var pe = Math.max(0.55, eff);

    var start = o.start || 1;
    var pad = Math.max(o.pad || 3, String(Math.abs(start + count - 1)).length);
    function fmt(n) {
      return (o.numberPrefix || "") + padNum(n, pad) + (o.numberSuffix || "");
    }
    var lastNumStr = fmt(start + count - 1);
    var numBase = Math.min(16, Math.max(6, 42 / Math.max(1, lastNumStr.length)));
    var numPt = numBase * (stubWidth / 12) * eff;

    // ---- school block sizing (big logo shrinks the name)
    var mainW = tokenW - stubWidth - (2.0 + 1.6) * pe;
    var logoAspect = logo ? logo.aspect : 1;
    var logoH = logo ? 6.2 * eff * logoScale : 0;
    var logoWEff = logoH * logoAspect;
    var avail1x = mainW - 1.1 - 6.2 * eff * logoAspect;
    var avail = mainW - 1.1 - logoWEff;
    var schoolScale = Math.max(0.45, Math.min(1, avail / Math.max(avail1x, 1)));
    var schoolPt = 4.6 * eff * schoolScale;

    var mpL = 2.0 * pe, mpR = 1.6 * pe, mpT = 1.3 * pe, mpB = 1.2 * pe;
    var spT = 2.1 * pe;
    var bodyX0Off = mpL;                       // from ticket left
    var bodyX1Off = tokenW - stubWidth - mpR;  // from ticket left

    // width guards (helvetica is a touch wider than Inter — never overflow)
    var schoolNameX = bodyX0Off + (logo ? logoWEff + 1.1 : 0);
    var schoolAvail = bodyX1Off - schoolNameX;
    for (var si = 0; si < schoolLines.length; si++) {
      var lw = schoolLineW(doc, schoolLines[si], schoolPt);
      if (lw > schoolAvail && lw > 0) schoolPt *= schoolAvail / lw;
    }
    if (schoolPt < 3) schoolPt = 3;
    var titlePt = 11.5 * eff;
    var titleW = textW(doc, o.title || "", 0.045 * titlePt * PT2MM);
    if (titleW > bodyX1Off - bodyX0Off && titleW > 0) {
      titlePt *= (bodyX1Off - bodyX0Off) / titleW;
    }
    var classPt = 7 * eff;
    var detPt = 6 * eff;
    var partyPt = 4.8 * eff, yrPt = 5.6 * eff, noLabelPt = 4.2 * eff;

    // guard: stub number must fit the stub content width
    var stubContentW = stubWidth - 1.2;
    var numW = textW(doc, lastNumStr, 0.02 * numPt * PT2MM);
    if (numW > stubContentW && numW > 0) numPt *= stubContentW / numW;

    // ---- party lines: "2026|CLASS PARTY" -> year line + one line per word
    var partyLines = [];
    if (o.party) {
      var parts = o.party.indexOf("|") >= 0 ? o.party.split("|") : ["", o.party];
      if (parts[0]) partyLines.push({ t: parts[0], pt: yrPt, cs: 0.12 });
      parts.slice(1).join(" ").split(/\s+/).forEach(function (w) {
        if (w) partyLines.push({ t: w, pt: partyPt, cs: 0.09 });
      });
    }

    // ---- static detail rows: only the draw date stays a plain row; the
    // price moves into the footer band, and the number row is per-ticket
    var detRows = [];
    if (showDD) {
      detRows.push({ label: (o.drawDateLabel || "Draw Date") + ":", value: String(drawDate) });
    }
    var bandPricePt = detPt * 1.15, bandNolPt = detPt * 0.8,
        bandNumPt = detPt * 1.6;
    var bandPadX = 1.3, bandPadY = 0.55, bandGap = 0.6, bandR = 1.1;

    var availNameMm = Math.max(8, tokenW - stubWidth - (2.0 + 1.6) * pe - 1.0);
    var nameLabel = o.nameLabel != null ? o.nameLabel : "Name";

    return {
      th: th, doc: doc, count: count, start: start, pad: pad, fmt: fmt,
      margin: margin, cols: cols, rows: rows, perPage: perPage,
      gridW: gridW, tokenW: tokenW, tokenH: tokenH,
      pw: pw, ph: ph, eff: eff, pe: pe,
      names: names, hasNames: hasNames,
      logo: logo, logoH: logoH, logoWEff: logoWEff,
      schoolLines: schoolLines, schoolPt: schoolPt,
      title: o.title || "", titlePt: titlePt,
      classLine: o.classLine || "", classPt: classPt,
      detPt: detPt, detRows: detRows, splitStub: splitStub,
      hasBand: hasBand, priceStr: showPrice ? String(price) : "",
      bandPricePt: bandPricePt, bandNolPt: bandNolPt, bandNumPt: bandNumPt,
      bandPadX: bandPadX, bandPadY: bandPadY, bandGap: bandGap, bandR: bandR,
      partyLines: partyLines, yrPt: yrPt, partyPt: partyPt,
      noLabelPt: noLabelPt, numPt: numPt,
      numberLabel: o.numberLabel != null ? o.numberLabel : "NO.",
      nameLabel: nameLabel, availNameMm: availNameMm,
      mpL: mpL, mpR: mpR, mpT: mpT, mpB: mpB, spT: spT,
      bodyX0Off: bodyX0Off, bodyX1Off: bodyX1Off,
      stubWidth: stubWidth,
      cutWeight: o.cutWeight != null ? o.cutWeight : 0.25,
      cutDash: o.cutDash || [0.9, 0.7]
    };
  }

  // ---------------------------------------------------------- one ticket
  function drawTicket(doc, L, X, Y, numStr, name) {
    var th = L.th;
    var tokenW = L.tokenW, tokenH = L.tokenH, stubW = L.stubWidth;
    var stubX0 = X + tokenW - stubW;
    var bodyX0 = X + L.bodyX0Off, bodyX1 = X + L.bodyX1Off;

    // 1) stub gradient (1 mm strips keep the PDF tiny and the blend smooth)
    var nStr = Math.max(2, Math.ceil(tokenH));
    for (var i = 0; i < nStr; i++) {
      setFill(doc, lerpC(th.stubTop, th.stubBot, (i + 0.5) / nStr));
      doc.rect(stubX0, Y + (tokenH * i) / nStr, stubW, tokenH / nStr + 0.012, "F");
    }

    // 2) tear line (dashed, drawn on the white body side like the CLI)
    doc.setDrawColor(th.cut[0] | 0, th.cut[1] | 0, th.cut[2] | 0);
    doc.setLineWidth(L.cutWeight);
    doc.setLineDashPattern(L.cutDash, 0);
    doc.line(stubX0, Y, stubX0, Y + tokenH);
    doc.setLineDashPattern([], 0);

    // 3) school row: logo + two-line name, vertically centred on each other
    var cur = Y + L.mpT;
    var schoolH = 0;
    if (L.schoolLines.length || L.logo) {
      var lineH = L.schoolPt * 1.38 * PT2MM;
      var blockH = L.schoolLines.length * lineH;
      schoolH = Math.max(L.logo ? L.logoH : 0, blockH);
      if (L.logo) {
        try {
          doc.addImage(L.logo.data, "PNG", bodyX0, cur, L.logoWEff, L.logoH,
                       "cascklogo", "FAST");
        } catch (e) { /* keep drawing tickets without the logo */ }
      }
      var nameX = bodyX0 + (L.logo ? L.logoWEff + 1.1 : 0);
      for (var li = 0; li < L.schoolLines.length; li++) {
        var top = cur + (schoolH - blockH) / 2 + li * lineH;
        drawSchoolLine(doc, L.schoolLines[li], nameX,
                       baselineOf(top, L.schoolPt, 1.38), L.schoolPt, th.ink);
      }
      cur += schoolH;
    }

    // 4) title
    cur += 1.2;
    drawText(doc, L.title, bodyX0, baselineOf(cur, L.titlePt, 1),
             { size: L.titlePt, bold: true, color: th.title,
               cs: 0.045 * L.titlePt * PT2MM });
    cur += L.titlePt * PT2MM;

    // 5) class line
    if (L.classLine) {
      cur += 0.8;
      drawText(doc, L.classLine, bodyX0, baselineOf(cur, L.classPt, 1.25),
               { size: L.classPt, bold: true, color: th.ink,
                 cs: 0.02 * L.classPt * PT2MM });
      cur += L.classPt * 1.25 * PT2MM;
    }

    // 6) holder name row (VIP): big, accent colour, auto-shrunk to fit
    if (L.hasNames && name !== undefined) {
      if (name === null) {
        // blank fill-in ticket: label + underline
        cur += 0.6;
        var bBase = baselineOf(cur, 9 * L.eff, 1.55);
        var bx = bodyX0;
        if (L.nameLabel) {
          bx += drawText(doc, L.nameLabel + " ", bodyX0, bBase,
                         { size: 9 * L.eff, bold: true, color: th.ink });
        }
        doc.setDrawColor(th.muted[0] | 0, th.muted[1] | 0, th.muted[2] | 0);
        doc.setLineWidth(0.28);
        doc.line(bx + 0.7, cur + 9 * L.eff * PT2MM * 0.95,
                 bx + 0.7 + 13, cur + 9 * L.eff * PT2MM * 0.95);
        cur += 9 * L.eff * 1.55 * PT2MM;
      } else {
        cur += 0.6;
        var labelLen = L.nameLabel ? L.nameLabel.length + 1 : 0;
        var size = Math.min(9 * L.eff,
                            L.availNameMm / Math.max(1, (labelLen + name.length) * 0.194));
        size = Math.max(3.5, size);
        var cs = 0.03 * size * PT2MM;
        doc.setFont("helvetica", "bold");
        doc.setFontSize(size);
        var fullW = textW(doc, (L.nameLabel ? L.nameLabel + " " : "") + name, cs);
        while (fullW > L.bodyX1Off - L.bodyX0Off && size > 3.5) {
          size -= 0.25;
          doc.setFontSize(size);
          cs = 0.03 * size * PT2MM;
          fullW = textW(doc, (L.nameLabel ? L.nameLabel + " " : "") + name, cs);
        }
        var nBase = baselineOf(cur, size, 1.55);
        var nx = bodyX0;
        if (L.nameLabel) {
          nx += drawText(doc, L.nameLabel + " ", bodyX0, nBase,
                         { size: size, bold: true, color: th.ink, cs: cs });
        }
        drawText(doc, name, nx, nBase,
                 { size: size, bold: true, color: th.accent, cs: cs });
        cur += size * 1.55 * PT2MM;
      }
    }

    // 7) footer: optional draw-date row, then the price/number band —
    //    the buyer's half keeps its own block of theme colour after the
    //    stub is torn off (mirrors the .foot/.band CSS in raffle_gen.py)
    var dateRows = L.detRows;              // draw-date rows only
    if (L.hasBand) {
      var bandH = L.bandNumPt * 1.1 * PT2MM + L.bandPadY * 2;
      var bandY0 = Y + tokenH - L.mpB - bandH;
      var detRowH = L.detPt * 1.55 * PT2MM;
      for (var ri = 0; ri < dateRows.length; ri++) {
        var rb = baselineOf(bandY0 - 0.4 - (dateRows.length - ri) * detRowH,
                            L.detPt, 1.55);
        var rw = dateRows[ri].label
          ? textW(doc, dateRows[ri].label + " ", 0) : 0;
        rw += textW(doc, dateRows[ri].value, 0.03 * L.detPt * PT2MM);
        var rx = bodyX1 - rw;
        if (dateRows[ri].label) {
          rx += drawText(doc, dateRows[ri].label + " ", rx, rb,
                         { size: L.detPt, bold: false, color: th.muted });
        }
        drawText(doc, dateRows[ri].value, rx, rb,
                 { size: L.detPt, bold: true, color: th.accent,
                   cs: 0.03 * L.detPt * PT2MM });
      }
      doc.setFillColor(th.bandBg[0] | 0, th.bandBg[1] | 0, th.bandBg[2] | 0);
      doc.roundedRect(bodyX0, bandY0, bodyX1 - bodyX0, bandH,
                      L.bandR, L.bandR, "F");
      // width guard: shrink the band type if price + number don't fit
      var pPt = L.bandPricePt, nolPt = L.bandNolPt, nPt = L.bandNumPt;
      var priceW = L.priceStr ? textW(doc, L.priceStr, 0.03 * pPt * PT2MM) : 0;
      var nolW = L.splitStub ? textW(doc, "No.", 0.14 * nolPt * PT2MM) : 0;
      var numW = L.splitStub ? textW(doc, numStr, 0.02 * nPt * PT2MM) : 0;
      var need = priceW + (priceW && nolW ? 1.2 : 0) + nolW +
                 (nolW ? 0.7 : 0) + numW;
      var availW = (bodyX1 - bodyX0) - 2 * L.bandPadX;
      if (need > availW && need > 0) {
        var bf = availW / need;
        pPt *= bf; nolPt *= bf; nPt *= bf; numW *= bf;
      }
      if (L.priceStr) {
        drawText(doc, L.priceStr, bodyX0 + L.bandPadX,
                 baselineOf(bandY0 + (bandH - pPt * 1.1 * PT2MM) / 2, pPt, 1.1),
                 { size: pPt, bold: true, color: th.bandText,
                   cs: 0.03 * pPt * PT2MM });
      }
      if (L.splitStub) {
        var numX = bodyX1 - L.bandPadX;
        var numBase = baselineOf(bandY0 + (bandH - nPt * 1.1 * PT2MM) / 2,
                                 nPt, 1.1);
        drawText(doc, numStr, numX, numBase,
                 { size: nPt, bold: true, color: th.bandText,
                   cs: 0.02 * nPt * PT2MM, align: "right" });
        drawText(doc, "No.", numX - numW - 0.7, numBase,
                 { size: nolPt, bold: true, color: th.bandText,
                   cs: 0.14 * nolPt * PT2MM, align: "right" });
      }
    } else if (dateRows.length) {
      // no band (no price, no split number): date rows pinned to the bottom
      var detRowH2 = L.detPt * 1.55 * PT2MM;
      var top2 = Y + tokenH - L.mpB - dateRows.length * detRowH2;
      for (var rj = 0; rj < dateRows.length; rj++) {
        var rb2 = baselineOf(top2 + rj * detRowH2, L.detPt, 1.55);
        var rw2 = dateRows[rj].label
          ? textW(doc, dateRows[rj].label + " ", 0) : 0;
        rw2 += textW(doc, dateRows[rj].value, 0.03 * L.detPt * PT2MM);
        var rx2 = bodyX1 - rw2;
        if (dateRows[rj].label) {
          rx2 += drawText(doc, dateRows[rj].label + " ", rx2, rb2,
                          { size: L.detPt, bold: false, color: th.muted });
        }
        drawText(doc, dateRows[rj].value, rx2, rb2,
                 { size: L.detPt, bold: true, color: th.accent,
                   cs: 0.03 * L.detPt * PT2MM });
      }
    }

    // 8) stub text: party / separator / number, space-between like the CSS
    var stubCx = stubX0 + stubW / 2;
    var contentTop = Y + L.spT, contentBot = Y + tokenH - 1.5;
    var partyH = 0;
    for (var pi = 0; pi < L.partyLines.length; pi++) {
      partyH += L.partyLines[pi].pt * 1.5 * PT2MM;
    }
    var sepBoxH = L.partyLines.length ? 2.28 : 0; // 1.0 + 0.28 + 1.0
    var noLabelLineH = L.numberLabel ? L.noLabelPt * 1.2 * PT2MM : 0;
    var noH = (L.numberLabel ? noLabelLineH + 0.6 : 0) + L.numPt * PT2MM;
    var gap = Math.max(0, (contentBot - contentTop - partyH - sepBoxH - noH) / 2);

    var p = contentTop;
    for (var pj = 0; pj < L.partyLines.length; pj++) {
      var pl = L.partyLines[pj];
      drawText(doc, pl.t, stubCx, baselineOf(p, pl.pt, 1.5),
               { size: pl.pt, bold: true, color: th.stubText,
                 cs: pl.cs * pl.pt * PT2MM, align: "center" });
      p += pl.pt * 1.5 * PT2MM;
    }
    if (L.partyLines.length) {
      var sepY = p + gap + 1.14;
      doc.setGState(new doc.GState({ opacity: th.stubSepOpacity }));
      doc.setDrawColor(th.stubSep[0] | 0, th.stubSep[1] | 0, th.stubSep[2] | 0);
      doc.setLineWidth(0.28);
      var sepW = (stubW - 1.2) * 0.62;
      doc.line(stubCx - sepW / 2, sepY, stubCx + sepW / 2, sepY);
      doc.setGState(new doc.GState({ opacity: 1 }));
    }
    var noTop = p + (L.partyLines.length ? gap + sepBoxH + gap : 0);
    if (L.numberLabel) {
      drawText(doc, L.numberLabel, stubCx, baselineOf(noTop, L.noLabelPt, 1.2),
               { size: L.noLabelPt, bold: true, color: th.stubText,
                 cs: 0.22 * L.noLabelPt * PT2MM, align: "center" });
    }
    var numTop = noTop + (L.numberLabel ? noLabelLineH + 0.6 : 0);
    drawText(doc, numStr, stubCx, baselineOf(numTop, L.numPt, 1),
             { size: L.numPt, bold: true, color: th.stubText,
               cs: 0.02 * L.numPt * PT2MM, align: "center" });
  }

  // ---------------------------------------------------------- one sheet
  function drawSheet(doc, L, sheetIdx) {
    var m = L.margin;
    var sheetCount = Math.min(L.perPage, L.count - sheetIdx * L.perPage);
    var rowsS = Math.ceil(sheetCount / L.cols);
    var ghS = L.tokenH * rowsS;

    // dashed cut grid: outer rectangle + shared inner separators
    doc.setDrawColor(L.th.cut[0] | 0, L.th.cut[1] | 0, L.th.cut[2] | 0);
    doc.setLineWidth(L.cutWeight);
    doc.setLineDashPattern(L.cutDash, 0);
    doc.rect(m, m, L.gridW, ghS);
    var i, j;
    for (i = 1; i < L.cols; i++) {
      doc.line(m + i * L.tokenW, m, m + i * L.tokenW, m + ghS);
    }
    for (j = 1; j < rowsS; j++) {
      doc.line(m, m + j * L.tokenH, m + L.gridW, m + j * L.tokenH);
    }
    doc.setLineDashPattern([], 0);

    for (var k = 0; k < sheetCount; k++) {
      var X = m + (k % L.cols) * L.tokenW;
      var Y = m + Math.floor(k / L.cols) * L.tokenH;
      var gi = sheetIdx * L.perPage + k;
      var numStr = L.fmt(L.start + gi);
      var name = L.hasNames ? (gi < L.names.length ? L.names[gi] : undefined) : undefined;
      drawTicket(doc, L, X, Y, numStr, name);
    }
  }

  // ---------------------------------------------------------- public API
  async function generateBatch(opts, onProgress) {
    var o = opts || {};
    var names = o.names || [];
    var count = o.count != null ? o.count : (names.length || 40);
    if (!(count >= 1)) throw new Error("need at least one ticket");
    var cols = o.cols || 4;
    if (names.length > count) {
      console.warn("names list longer than count — extras ignored");
    }

    var doc = new jsPDF({ unit: "mm", format: "a4", compress: true });
    var L = computeLayout(doc, o, count);

    var sheets = Math.ceil(count / L.perPage);
    for (var s = 0; s < sheets; s++) {
      if (s > 0) doc.addPage();
      drawSheet(doc, L, s);
      if (onProgress) onProgress(s + 1, sheets);
      if (s < sheets - 1) await new Promise(function (r) { setTimeout(r, 0); });
    }

    var first = L.fmt(L.start), last = L.fmt(L.start + count - 1);
    var metaTitle = (o.title || "Raffle tickets") +
                    (o.classLine ? " - " + o.classLine : "");
    doc.setProperties({
      title: metaTitle,
      subject: count + " numbered raffle tickets (" + first + "-" + last +
               "), " + L.perPage + " per sheet" +
               (o.price ? ", price " + o.price : "") + ", dashed cut lines",
      author: o.school ? o.school.split("|")[0] : "raffle-draw",
      creator: "raffle-draw web generator (github.com/RohanDaCoder/raffle-draw)"
    });
    return doc;
  }

  function expandHolders(rows) {
    var out = [];
    (rows || []).forEach(function (r) {
      var n = Math.max(1, Math.floor(Number(r.tickets) || 1));
      for (var i = 0; i < n; i++) out.push(r.name);
    });
    return out;
  }

  function summarize(opts) {
    var o = opts || {};
    var perPage = (o.cols || 4) * (o.rows || 10);
    var count = o.count != null ? o.count : (o.names ? o.names.length : 0);
    var start = o.start || 1;
    var pad = Math.max(o.pad || 3, String(Math.abs(start + count - 1)).length);
    return {
      count: count, perPage: perPage,
      sheets: count > 0 ? Math.ceil(count / perPage) : 0,
      full: count > 0 && count % perPage === 0,
      first: padNum(start, pad),
      last: padNum(start + count - 1, pad)
    };
  }

  return {
    generateBatch: generateBatch, expandHolders: expandHolders,
    summarize: summarize, PRESETS: PRESETS, THEMES: THEMES
  };
});
