/* Chess between two TBClients (CR78 stage 8) - the rules, in the browser.
 * Over the air only the moves (UCI, "e2e4", "e7e8q"); both sides run this
 * code on the same list of moves, so both see the same board. The client
 * (peerfun.py) checks only whose turn it is.
 *
 * Board: 64 squares, index = rank * 8 + file, a1 = 0, h8 = 63.
 * White pieces "PNBRQK", black "pnbrqk", "" empty. */
"use strict";

const Chess = (() => {
  const START = "RNBQKBNRPPPPPPPP" + "".padEnd(32, ".") + "pppppppprnbqkbnr";
  const FILES = "abcdefgh";
  const white = (p) => p !== "" && p === p.toUpperCase();
  const colorOf = (p) => (p === "" ? null : white(p) ? "w" : "b");
  const sq = (s) => FILES.indexOf(s[0]) + 8 * (Number(s[1]) - 1);
  const name = (i) => FILES[i % 8] + (Math.floor(i / 8) + 1);

  function start() {
    return { b: [...START].map((c) => (c === "." ? "" : c)), turn: "w",
             castle: { K: true, Q: true, k: true, q: true }, ep: -1 };
  }

  function attacked(st, i, by) {          // is square i attacked by colour `by`?
    const b = st.b, f = i % 8, r = Math.floor(i / 8);
    const at = (ff, rr) => (ff >= 0 && ff < 8 && rr >= 0 && rr < 8 ? b[rr * 8 + ff] : null);
    const is = (p, t) => p && colorOf(p) === by && p.toLowerCase() === t;
    const pr = by === "w" ? r - 1 : r + 1;            // pawns attack forward
    if (is(at(f - 1, pr), "p") || is(at(f + 1, pr), "p")) return true;
    for (const [df, dr] of [[1, 2], [2, 1], [-1, 2], [-2, 1], [1, -2], [2, -1], [-1, -2], [-2, -1]])
      if (is(at(f + df, r + dr), "n")) return true;
    for (let df = -1; df <= 1; df++) for (let dr = -1; dr <= 1; dr++)
      if ((df || dr) && is(at(f + df, r + dr), "k")) return true;
    const rays = [[1, 0, "rq"], [-1, 0, "rq"], [0, 1, "rq"], [0, -1, "rq"],
                  [1, 1, "bq"], [1, -1, "bq"], [-1, 1, "bq"], [-1, -1, "bq"]];
    for (const [df, dr, ts] of rays) {
      let ff = f + df, rr = r + dr;
      while (ff >= 0 && ff < 8 && rr >= 0 && rr < 8) {
        const p = b[rr * 8 + ff];
        if (p) { if (colorOf(p) === by && ts.includes(p.toLowerCase())) return true; break; }
        ff += df; rr += dr;
      }
    }
    return false;
  }

  function pseudo(st) {                    // moves without looking at check
    const out = [], b = st.b, me = st.turn;
    const add = (from, to, promo) => out.push(name(from) + name(to) + (promo || ""));
    for (let i = 0; i < 64; i++) {
      const p = b[i];
      if (!p || colorOf(p) !== me) continue;
      const f = i % 8, r = Math.floor(i / 8), t = p.toLowerCase();
      const free = (ff, rr) => ff >= 0 && ff < 8 && rr >= 0 && rr < 8 && !b[rr * 8 + ff];
      const enemy = (ff, rr) => ff >= 0 && ff < 8 && rr >= 0 && rr < 8 && b[rr * 8 + ff]
        && colorOf(b[rr * 8 + ff]) !== me;
      if (t === "p") {
        const dir = me === "w" ? 1 : -1, last = me === "w" ? 7 : 0, home = me === "w" ? 1 : 6;
        const push = (to) => (Math.floor(to / 8) === last ? ["q", "r", "b", "n"].forEach((x) => add(i, to, x)) : add(i, to));
        if (free(f, r + dir)) {
          push(i + 8 * dir);
          if (r === home && free(f, r + 2 * dir)) add(i, i + 16 * dir);
        }
        for (const df of [-1, 1]) {
          const to = (r + dir) * 8 + f + df;
          if (enemy(f + df, r + dir)) push(to);
          else if (f + df >= 0 && f + df < 8 && to === st.ep) add(i, to);
        }
      } else if (t === "n" || t === "k") {
        const steps = t === "n" ? [[1, 2], [2, 1], [-1, 2], [-2, 1], [1, -2], [2, -1], [-1, -2], [-2, -1]]
          : [[1, 0], [-1, 0], [0, 1], [0, -1], [1, 1], [1, -1], [-1, 1], [-1, -1]];
        for (const [df, dr] of steps)
          if (free(f + df, r + dr) || enemy(f + df, r + dr)) add(i, (r + dr) * 8 + f + df);
        if (t === "k") {                     // castling: rights, empty, not through check
          const them = me === "w" ? "b" : "w", base = me === "w" ? 0 : 56;
          const [ks, qs] = me === "w" ? ["K", "Q"] : ["k", "q"];
          if (i === base + 4 && !attacked(st, i, them)) {
            if (st.castle[ks] && !b[base + 5] && !b[base + 6] && !attacked(st, base + 5, them)
                && !attacked(st, base + 6, them)) add(i, base + 6);
            if (st.castle[qs] && !b[base + 3] && !b[base + 2] && !b[base + 1]
                && !attacked(st, base + 3, them) && !attacked(st, base + 2, them)) add(i, base + 2);
          }
        }
      } else {
        const dirs = t === "r" ? [[1, 0], [-1, 0], [0, 1], [0, -1]]
          : t === "b" ? [[1, 1], [1, -1], [-1, 1], [-1, -1]]
            : [[1, 0], [-1, 0], [0, 1], [0, -1], [1, 1], [1, -1], [-1, 1], [-1, -1]];
        for (const [df, dr] of dirs) {
          let ff = f + df, rr = r + dr;
          while (free(ff, rr)) { add(i, rr * 8 + ff); ff += df; rr += dr; }
          if (enemy(ff, rr)) add(i, rr * 8 + ff);
        }
      }
    }
    return out;
  }

  function apply(st, uci) {                // the position after a move (no checks)
    const n = { b: st.b.slice(), turn: st.turn === "w" ? "b" : "w", castle: { ...st.castle }, ep: -1 };
    const from = sq(uci.slice(0, 2)), to = sq(uci.slice(2, 4)), promo = uci[4];
    const p = n.b[from], t = p.toLowerCase();
    if (t === "p" && to === st.ep && !n.b[to]) n.b[to + (white(p) ? -8 : 8)] = "";   // en passant
    if (t === "p" && Math.abs(to - from) === 16) n.ep = (from + to) / 2;
    if (t === "k" && Math.abs(to - from) === 2) {                                    // castling
      const rf = to > from ? from + 3 : from - 4, rt = to > from ? from + 1 : from - 1;
      n.b[rt] = n.b[rf]; n.b[rf] = "";
    }
    n.b[to] = promo ? (white(p) ? promo.toUpperCase() : promo) : p;
    n.b[from] = "";
    for (const [i, k] of [[4, "KQ"], [0, "Q"], [7, "K"], [60, "kq"], [56, "q"], [63, "k"]])
      if (from === i || to === i) for (const c of k) n.castle[c] = false;
    return n;
  }

  function king(st, color) { return st.b.indexOf(color === "w" ? "K" : "k"); }
  function inCheck(st, color) { return attacked(st, king(st, color), color === "w" ? "b" : "w"); }

  function legal(st) {
    return pseudo(st).filter((m) => !inCheck(apply(st, m), st.turn));
  }

  /* Replay a game: {st, ok (all moves legal), last, status: play|check|mate|stalemate} */
  function play(moves) {
    let st = start(), ok = true;
    for (const m of moves) {
      if (!legal(st).includes(m)) ok = false;   // shown anyway - both sides see the same
      st = apply(st, m);
    }
    const moves2 = legal(st), check = inCheck(st, st.turn);
    const status = moves2.length ? (check ? "check" : "play") : (check ? "mate" : "stalemate");
    return { st, ok, last: moves[moves.length - 1] || "", status, legal: moves2 };
  }

  const GLYPH = { K: "♔", Q: "♕", R: "♖", B: "♗", N: "♘", P: "♙",
                  k: "♚", q: "♛", r: "♜", b: "♝", n: "♞", p: "♟" };
  return { play, sq, name, GLYPH, colorOf };
})();
