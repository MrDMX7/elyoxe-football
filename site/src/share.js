/* تيفو images (phase 3): story card for a result or a coming match (12, 60), phone wallpaper of a club's fixtures (44),
   and the Tifo studio banner (152). All drawn on canvas in the Tifo identity (night pitch, card mosaic, Kufi + Barlow),
   from same-origin logos so the canvas stays exportable. Shared with navigator.share when the phone supports files,
   otherwise downloaded. */
(function(){
  "use strict";
  var R = window.TR, NIGHT = "#0A2620", NIGHT2 = "#123A31", CHALK = "#F6F7F2", DUNE = "#B07A3B", PULSE = "#10A04B";
  function col(id, i){ var c = (window.TC || {})[id]; return c ? (c[i || 0] || c[0]) : (i ? "#F6F7F2" : "#5C6660"); }
  function img(src){ return new Promise(function(ok){ var i = new Image(); i.onload = function(){ ok(i); }; i.onerror = function(){ ok(null); }; i.src = src; }); }
  function fonts(){ return (document.fonts && document.fonts.ready) ? Promise.all([document.fonts.load('800 60px "Noto Kufi Arabic"'), document.fonts.load('700 60px "Barlow Condensed"'), document.fonts.load('400 30px "Readex Pro"')]).catch(function(){}) : Promise.resolve(); }
  function seed(n){ return function(){ n = (n * 16807) % 2147483647; return n / 2147483647; }; }
  // the stand: a band of cards in two clubs' colours, home on the right
  function stand(x, X, Y, W, H, cs, hid, aid, s){
    var rnd = seed(s || 7), cols = Math.ceil(W / cs), rows = Math.ceil(H / cs);
    for (var r = 0; r < rows; r++) for (var c = 0; c < cols; c++){
      var home = c >= cols / 2, id = home ? hid : aid, stripe = ((home ? cols - c : c) + r) % 7 < 2, k = 0.88 + rnd() * 0.2;
      x.globalAlpha = k > 1 ? 1 : k; x.fillStyle = aid == null ? col(hid, stripe ? 1 : 0) : col(id, stripe ? 1 : 0);
      x.fillRect(X + c * cs, Y + r * cs, cs - 3, cs - 3);
    }
    x.globalAlpha = 1;
  }
  function text(x, s, X, Y, font, color, align, dir){ x.font = font; x.fillStyle = color; x.textAlign = align || "center"; x.direction = dir || "rtl"; x.fillText(s, X, Y); }
  function fit(x, s, font, max){ var size = parseInt(font.match(/(\d+)px/)[1], 10); x.font = font; while (x.measureText(s).width > max && size > 20){ size -= 2; x.font = font.replace(/\d+px/, size + "px"); } return x.font; }
  function mark(x, X, Y, s){ var cl = [[CHALK, PULSE, DUNE], [CHALK, DUNE, PULSE], [PULSE, DUNE, CHALK]]; for (var r = 0; r < 3; r++) for (var c = 0; c < 3; c++){ x.fillStyle = cl[r][c]; x.fillRect(X + c * s * 1.2, Y + r * s * 1.2, s, s); } }
  function footer(x, W, H){ mark(x, W - 230, H - 130, 22); text(x, "تيفو", W - 330, H - 72, '800 64px "Noto Kufi Arabic"', CHALK, "right"); text(x, "tifo.elyoxe.com", 70, H - 78, '700 40px "Barlow Condensed"', "#B9C7C0", "left"); }
  // W1.10: the image travels with a line of text and a link (WhatsApp drops `url` when files are attached, so the link rides in `text`);
  // a cancelled share is just cancelled, a download happens only when the phone can't share files
  function out(canvas, name, text){
    text = text || (document.title.replace(/\s*\|\s*تيفو$/, "") + "\n" + location.origin + location.pathname + "?s=wa");
    return new Promise(function(ok){ canvas.toBlob(function(b){
      var f = new File([b], name, { type:"image/png" });
      if (navigator.canShare && navigator.canShare({ files:[f] })) navigator.share({ files:[f], text:text }).then(ok, function(e){ ok(); }); else { dl(); ok(); }
      function dl(){ var a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = name; document.body.appendChild(a); a.click(); setTimeout(function(){ URL.revokeObjectURL(a.href); a.remove(); }, 2000); }
    }, "image/png"); });
  }
  // story (1080x1920): result, live or coming match (+ probabilities for a coming one)
  function story(md){
    var W = 1080, H = 1920, c = document.createElement("canvas"); c.width = W; c.height = H; var x = c.getContext("2d");
    return fonts().then(function(){ return Promise.all([img("/logo/" + md.home.id + ".png"), img("/logo/" + md.away.id + ".png")]); }).then(function(L){
      x.fillStyle = NIGHT; x.fillRect(0, 0, W, H);
      stand(x, 0, 0, W, 560, 36, md.home.id, md.away.id, md.id % 997 + 3);
      x.fillStyle = NIGHT; x.fillRect(0, 560, W, H - 560);
      var comp = md.comp_name_ar || ""; text(x, comp, W / 2, 680, '400 40px "Readex Pro"', "#B9C7C0");
      if (L[0]) x.drawImage(L[0], W - 330, 760, 220, 220); if (L[1]) x.drawImage(L[1], 110, 760, 220, 220);
      text(x, md.home.name_ar || md.home.name, W - 220, 1060, fit(x, md.home.name_ar || md.home.name, '800 56px "Noto Kufi Arabic"', 420), CHALK);
      text(x, md.away.name_ar || md.away.name, 220, 1060, fit(x, md.away.name_ar || md.away.name, '800 56px "Noto Kufi Arabic"', 420), CHALK);
      var live = R.isLive(md);
      if (md.score){ text(x, String(md.score.home), W / 2 + 130, 960, '700 230px "Barlow Condensed"', live ? "#5BE08F" : CHALK); text(x, "-", W / 2, 940, '700 160px "Barlow Condensed"', "#B9C7C0"); text(x, String(md.score.away), W / 2 - 130, 960, '700 230px "Barlow Condensed"', live ? "#5BE08F" : CHALK); }
      else text(x, R.hhmm(md.kickoff_uae), W / 2, 930, '700 170px "Barlow Condensed"', CHALK);
      var st = live ? "مباشر " + (md.minute || "") + "'" : md.status === "finished" ? "انتهت" : R.dayLabel(R.ymd(md.kickoff_uae));
      text(x, st, W / 2, 1180, '800 46px "Noto Kufi Arabic"', live ? "#5BE08F" : DUNE);
      var y = 1300;
      if (md.status === "finished" || live){
        (md.events || []).filter(function(e){ return /goal/.test(e.type) && e.player; }).slice(0, 8).forEach(function(e){ var s = e.team === "home" ? e.minute + "'  " + e.player.name : e.player.name + "  " + e.minute + "'"; text(x, s, e.team === "home" ? W - 90 : 90, y, '400 36px "Readex Pro"', CHALK, e.team === "home" ? "right" : "left", "ltr"); y += 56; });
      } else if (md.probs){
        var p = md.probs, bw = W - 180, hx = 90;
        x.fillStyle = col(md.away.id); x.fillRect(hx, y, bw * p.away, 34); x.fillStyle = "#9BA39E"; x.fillRect(hx + bw * p.away + 4, y, bw * p.draw - 8, 34); x.fillStyle = col(md.home.id); x.fillRect(hx + bw * (p.away + p.draw), y, bw * p.home, 34);
        text(x, "فوز " + (md.home.name_ar || "") + " " + Math.round(p.home * 100) + "%", W - 90, y + 100, '400 36px "Readex Pro"', CHALK, "right");
        text(x, "فوز " + (md.away.name_ar || "") + " " + Math.round(p.away * 100) + "%", 90, y + 100, '400 36px "Readex Pro"', CHALK, "left");
        text(x, "تعادل " + Math.round(p.draw * 100) + "%", W / 2, y + 160, '400 36px "Readex Pro"', "#B9C7C0");
        text(x, "توقعات تيفو", W / 2, y + 240, '800 34px "Noto Kufi Arabic"', DUNE);
      }
      if (md.venue && md.venue.name_ar) text(x, md.venue.name_ar, W / 2, H - 260, '400 34px "Readex Pro"', "#B9C7C0");
      footer(x, W, H);
      var H0 = md.home.name_ar || md.home.name, A0 = md.away.name_ar || md.away.name;
      return window.TifoShare.out(c, "tifo-" + md.id + ".png", (md.score ? H0 + " " + md.score.home + " - " + md.score.away + " " + A0 : H0 + " ضد " + A0 + " " + R.hhmm(md.kickoff_uae)) + "\n" + location.origin + "/m/" + md.id + "/?s=wa");
    });
  }
  // phone wallpaper (1080x2340): the club's next matches on its own colours
  function wallpaper(t, next){
    var W = 1080, H = 2340, c = document.createElement("canvas"); c.width = W; c.height = H; var x = c.getContext("2d");
    return fonts().then(function(){ return img("/logo/" + t.id + ".png"); }).then(function(L){
      x.fillStyle = NIGHT; x.fillRect(0, 0, W, H); stand(x, 0, 0, W, 760, 40, t.id, null, t.id % 991 + 5);
      x.fillStyle = NIGHT; x.fillRect(W / 2 - 170, 470, 340, 340); if (L) x.drawImage(L, W / 2 - 140, 500, 280, 280);
      text(x, t.name, W / 2, 930, fit(x, t.name, '800 80px "Noto Kufi Arabic"', W - 160), CHALK);
      var y = 1060;
      next.slice(0, 5).forEach(function(m){
        var home = m.home.id === t.id, opp = home ? m.away : m.home;
        x.fillStyle = NIGHT2; x.fillRect(70, y, W - 140, 170);
        text(x, (home ? "ضد " : "في ملعب ") + (opp.name_ar || opp.name), W - 110, y + 75, fit(x, opp.name_ar || opp.name, '800 44px "Noto Kufi Arabic"', 560), CHALK, "right");
        text(x, (m.comp_name_ar || ""), W - 110, y + 135, '400 30px "Readex Pro"', "#B9C7C0", "right");
        text(x, R.hhmm(m.kickoff_uae), 110, y + 85, '700 70px "Barlow Condensed"', DUNE, "left");
        var dp = R.dayParts(R.ymd(m.kickoff_uae)); text(x, dp.date, 110, y + 140, '400 30px "Readex Pro"', "#B9C7C0", "left");
        y += 200;
      });
      footer(x, W, H);
      return window.TifoShare.out(c, "tifo-" + t.id + "-wallpaper.png");
    });
  }
  // Tifo studio banner (3000x1000, print-ready): the club's colours as a card mosaic with the fans' words
  function banner(id, words){
    var W = 3000, H = 1000, c = document.createElement("canvas"); c.width = W; c.height = H; var x = c.getContext("2d");
    return fonts().then(function(){ return img("/logo/" + id + ".png"); }).then(function(L){
      x.fillStyle = NIGHT; x.fillRect(0, 0, W, H); stand(x, 0, 0, W, H, 50, id, null, id % 983 + 11);
      x.fillStyle = "rgba(10,38,32,.86)"; x.fillRect(260, 250, W - 520, 500);
      if (L) x.drawImage(L, W - 700, 330, 340, 340);
      text(x, words || "", W / 2 - 180, 580, fit(x, words || "", '800 190px "Noto Kufi Arabic"', W - 1300), CHALK);
      return c;
    });
  }
  // 250: any section as a square card (title + its first lines)
  function card(title, lines){
    var W = 1080, H = 1080, c = document.createElement("canvas"); c.width = W; c.height = H; var x = c.getContext("2d");
    return fonts().then(function(){
      x.fillStyle = NIGHT; x.fillRect(0, 0, W, H); var cl = [CHALK, PULSE, DUNE]; for (var i = 0; i < 27; i++){ x.fillStyle = cl[i % 3]; x.globalAlpha = .9; x.fillRect(i * 40, 0, 36, 36); } x.globalAlpha = 1;
      text(x, title, W - 80, 170, fit(x, title, '800 64px "Noto Kufi Arabic"', W - 160), CHALK, "right");
      var y = 280; lines.slice(0, 8).forEach(function(l){ x.fillStyle = NIGHT2; x.fillRect(70, y - 52, W - 140, 78); text(x, l, W - 100, y, fit(x, l, '400 36px "Readex Pro"', W - 220), CHALK, "right"); y += 92; });
      footer(x, W, H); return window.TifoShare.out(c, "tifo-card.png");
    });
  }
  // 291: the coming round with Tifo odds; 314: the week's matches in the visitor's time zone with channels
  function listCard(title, sub, rows, name){
    var W = 1080, H = Math.max(1080, 320 + rows.length * 120 + 160), c = document.createElement("canvas"); c.width = W; c.height = H; var x = c.getContext("2d");
    return fonts().then(function(){ return Promise.all(rows.map(function(r){ return Promise.all([r.h ? img("/logo/" + r.h + ".png") : null, r.a ? img("/logo/" + r.a + ".png") : null]); })); }).then(function(L){
      x.fillStyle = NIGHT; x.fillRect(0, 0, W, H); var cl = [CHALK, PULSE, DUNE]; for (var i = 0; i < 27; i++){ x.fillStyle = cl[i % 3]; x.fillRect(i * 40, 0, 36, 36); }
      text(x, title, W - 70, 150, fit(x, title, '800 60px "Noto Kufi Arabic"', W - 140), CHALK, "right"); if (sub) text(x, sub, W - 70, 210, '400 32px "Readex Pro"', "#B9C7C0", "right");
      var y = 270; rows.forEach(function(r, i){ x.fillStyle = NIGHT2; x.fillRect(60, y, W - 120, 104);
        if (L[i][0]) x.drawImage(L[i][0], W - 140, y + 22, 60, 60); if (L[i][1]) x.drawImage(L[i][1], 80, y + 22, 60, 60);
        text(x, r.home, W - 160, y + 50, fit(x, r.home, '800 34px "Noto Kufi Arabic"', 300), CHALK, "right"); text(x, r.away, 160, y + 50, fit(x, r.away, '800 34px "Noto Kufi Arabic"', 300), CHALK, "left");
        text(x, r.mid, W / 2, y + 50, '700 40px "Barlow Condensed"', DUNE); if (r.low) text(x, r.low, W / 2, y + 88, '400 26px "Readex Pro"', "#B9C7C0");
        y += 120; });
      footer(x, W, H); return window.TifoShare.out(c, name || "tifo-list.png"); });
  }
  window.TifoShare = { story:story, wallpaper:wallpaper, banner:banner, out:out, card:card, listCard:listCard };
})();
