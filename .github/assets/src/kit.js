// Draws aurora connectors between elements of a figure page.
//   <body data-wires="a > b : label ; c >> d ; e ~> f">
//   a > b    solid gradient arrow          a >> b   thick gradient arrow (main flow)
//   a ~> b   dashed magenta arrow (feedback)   a -> b   volt arrow (control)
//   sides are picked from the boxes' positions; force them with a.r > b.l (t, r, b, l).
// Sets window.figureReady when done, which render.mjs waits for.

(function () {
  const NS = "http://www.w3.org/2000/svg";
  const canvas = document.querySelector(".canvas");

  function anchor(box, side, root) {
    const x = box.left - root.left, y = box.top - root.top;
    return {
      t: [x + box.width / 2, y], b: [x + box.width / 2, y + box.height],
      l: [x, y + box.height / 2], r: [x + box.width, y + box.height / 2],
    }[side];
  }

  function sides(a, b) {
    const dx = (b.left + b.width / 2) - (a.left + a.width / 2);
    const dy = (b.top + b.height / 2) - (a.top + a.height / 2);
    if (b.left >= a.right - 4) return ["r", "l"];
    if (b.right <= a.left + 4) return ["l", "r"];
    if (Math.abs(dy) >= Math.abs(dx) * 0.4) return dy > 0 ? ["b", "t"] : ["t", "b"];
    return dx > 0 ? ["r", "l"] : ["l", "r"];
  }

  function el(name, attrs, parent) {
    const e = document.createElementNS(NS, name);
    for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
    parent?.appendChild(e);
    return e;
  }

  function draw() {
    const root = canvas.getBoundingClientRect();
    const svg = el("svg", { class: "wires", viewBox: `0 0 ${root.width} ${root.height}` });
    canvas.prepend(svg);
    const defs = el("defs", {}, svg);
    const grad = el("linearGradient", { id: "aurora", gradientUnits: "userSpaceOnUse", x1: 0, y1: 0, x2: root.width, y2: root.height * 0.4 }, defs);
    for (const [o, c] of [[0, "#0aa2c6"], [0.5, "#6b4dff"], [1, "#e0429b"]]) el("stop", { offset: o, "stop-color": c }, grad);
    const glow = el("filter", { id: "wglow", x: "-20%", y: "-20%", width: "140%", height: "140%" }, defs);
    el("feGaussianBlur", { stdDeviation: 3.2 }, glow);
    const markers = { aurora: "url(#aurora)", feedback: "#e0429b", volt: "#86c400" };
    for (const [id, fill] of Object.entries(markers)) {
      const m = el("marker", { id: `arrow-${id}`, viewBox: "0 0 10 10", refX: 8.2, refY: 5, markerWidth: 7, markerHeight: 7, orient: "auto-start-reverse", markerUnits: "strokeWidth" }, defs);
      el("path", { d: "M1 1.2 9 5 1 8.8 2.6 5Z", fill: id === "aurora" ? "#6b4dff" : fill }, m);
    }

    const spec = (document.body.dataset.wires || "").split(";").map((s) => s.trim()).filter(Boolean);
    for (const line of spec) {
      const [pair, label] = line.split(":").map((s) => s?.trim());
      const m = pair.match(/^([\w.-]+)\s*(>>|~>|->|>)\s*([\w.-]+)$/);
      if (!m) { console.warn("bad wire", line); continue; }
      const [, from, kind, to] = m;
      const [aid, as] = from.split("."), [bid, bs] = to.split(".");
      const A = document.getElementById(aid), B = document.getElementById(bid);
      if (!A || !B) { console.warn("missing", aid, bid); continue; }
      const ra = A.getBoundingClientRect(), rb = B.getBoundingClientRect();
      const [sa, sb] = as && bs ? [as, bs] : sides(ra, rb);
      const p0 = anchor(ra, sa, root), p1 = anchor(rb, sb, root);
      const gap = 6;
      const off = { t: [0, -gap], b: [0, gap], l: [-gap, 0], r: [gap, 0] };
      p0[0] += off[sa][0]; p0[1] += off[sa][1]; p1[0] += off[sb][0] * 1.6; p1[1] += off[sb][1] * 1.6;
      const dist = Math.hypot(p1[0] - p0[0], p1[1] - p0[1]);
      const k = Math.max(28, Math.min(150, dist * 0.45));
      const dir = { t: [0, -1], b: [0, 1], l: [-1, 0], r: [1, 0] };
      const c0 = [p0[0] + dir[sa][0] * k, p0[1] + dir[sa][1] * k];
      const c1 = [p1[0] + dir[sb][0] * k, p1[1] + dir[sb][1] * k];
      const d = `M${p0} C${c0} ${c1} ${p1}`;
      const style = kind === "~>" ? "feedback" : kind === "->" ? "volt" : "aurora";
      const stroke = markers[style];
      const width = kind === ">>" ? 3.2 : 2;
      if (style === "aurora") el("path", { d, fill: "none", stroke, "stroke-width": width + 3, opacity: 0.22, filter: "url(#wglow)" }, svg);
      el("path", { d, fill: "none", stroke, "stroke-width": width, "stroke-linecap": "round", "stroke-dasharray": style === "feedback" ? "6 6" : "none", "marker-end": `url(#arrow-${style})` }, svg);
      el("circle", { cx: p0[0], cy: p0[1], r: kind === ">>" ? 4.2 : 3.2, fill: "#fff", stroke: style === "aurora" ? "#0aa2c6" : stroke, "stroke-width": 2 }, svg);
      if (label) {
        const t = 0.5, mt = 1 - t;
        const x = mt ** 3 * p0[0] + 3 * mt * mt * t * c0[0] + 3 * mt * t * t * c1[0] + t ** 3 * p1[0];
        const y = mt ** 3 * p0[1] + 3 * mt * mt * t * c0[1] + 3 * mt * t * t * c1[1] + t ** 3 * p1[1];
        const div = document.createElement("div");
        div.className = "wire-label";
        div.textContent = label;
        div.style.left = `${x}px`;
        div.style.top = `${y}px`;
        canvas.appendChild(div);
      }
    }
    window.figureReady = true;
  }

  (document.fonts?.ready ?? Promise.resolve()).then(() => requestAnimationFrame(() => requestAnimationFrame(draw)));
})();
