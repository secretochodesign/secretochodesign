#!/usr/bin/env python3
"""Draws the profile's images in secretocho.design's own language: assets/<name>-dark.svg and assets/<name>-light.svg.

Run: uv run --with uharfbuzz==0.51.1 --with fonttools==4.63.0 tools/build.py

GitHub serves README images with `default-src 'none'`, so an SVG cannot load or embed a font. Every letter is therefore
an outline of Recursive 1.085 (SIL OFL), shaped by HarfBuzz at the site's axes (CASL 0, CRSV 0.5) and drawn once per
SVG as a <path> that <use> places. The name's mono-to-sans morph is nine outline states, stepped like the site's
title. Colours are the site's tokens; motion stops for visitors who ask for less of it.
"""
import hashlib
import html
import io
import pathlib
import urllib.request
import zipfile

import uharfbuzz as hb
from fontTools.pens.basePen import BasePen

ROOT = pathlib.Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
URL = "https://github.com/arrowtype/recursive/releases/download/v1.085/ArrowType-Recursive-1.085.zip"
SHA256 = "cbcbdf7a0e181d284a9235e09ed5f3873e527bc5dd1d977df71cdc1ff937da02"
MEMBER = "ArrowType-Recursive-1.085/Recursive_Desktop/Recursive_VF_1.085.ttf"
CACHE = ROOT / ".cache" / "ArrowType-Recursive-1.085.zip"
SITE = "https://secretocho.design"

# secretocho.design's tokens (src/styles/tokens.css), dark first
THEMES = {
    "dark": dict(s1="#151518", ln="#26262B", l2="#333339", ink="#EDEDEF", sub="#9B9BA3", fnt="#85858F", dim="#6B6B74",
                 em="#00FA92", emw="rgba(0,250,146,.08)", amb="#FFB224", pk="#F472B6", ax="#937B6B", sky="#38BDF8"),
    "light": dict(s1="#FFFFFF", ln="#DCE3EC", l2="#C5D0DC", ink="#0F172A", sub="#3B4759", fnt="#566175", dim="#94A3B8",
                  em="#00774F", emw="rgba(0,119,79,.08)", amb="#8A5300", pk="#B81A60", ax="#7A6254", sky="#0270A8"),
}


def source():
    if not CACHE.exists():
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_bytes(urllib.request.urlopen(URL).read())
    data = CACHE.read_bytes()
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise SystemExit("unexpected Recursive zip: delete .cache/ and run again")
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return z.read(MEMBER)


FACE = hb.Face(hb.Blob(source()))
FONT = hb.Font(FACE)
UPM = FACE.upem


class CompactPen(BasePen):
    """An SVG path in whole font units, relative after the first point: about half of SVGPathPen's bytes."""

    def __init__(self):
        super().__init__(None)
        self.out, self.at = [], (0, 0)

    def _p(self, pt):
        x, y = round(pt[0]), round(pt[1])
        d = f"{x - self.at[0]} {y - self.at[1]}"
        self.at = (x, y)
        return d.replace(" -", "-")

    def _moveTo(self, pt):
        x, y = round(pt[0]), round(pt[1])
        self.out.append(f"M{x} {y}".replace(" -", "-"))
        self.at = (x, y)

    def _lineTo(self, pt):
        self.out.append("l" + self._p(pt))

    def _qCurveToOne(self, p1, p2):
        a = self._rel(p1)
        self.out.append("q" + a + " " + self._p(p2))

    def _curveToOne(self, p1, p2, p3):
        a, b = self._rel(p1), self._rel(p2)
        self.out.append("c" + a + " " + b + " " + self._p(p3))

    def _rel(self, pt):  # a control point, relative to the current point, which does not move
        return f"{round(pt[0]) - self.at[0]} {round(pt[1]) - self.at[1]}".replace(" -", "-")

    def _closePath(self):
        self.out.append("z")


class Svg:
    """One image: glyph runs placed by <use>, shapes, and the CSS both themes share."""

    def __init__(self, name, w, h, title, desc):
        self.name, self.w, self.h, self.title, self.desc = name, w, h, title, desc
        self.glyphs, self.parts, self.css = {}, [], []

    def glyph(self, gid, axes):
        key = (gid, axes)
        if key not in self.glyphs:
            FONT.set_variations(dict(axes))
            pen = CompactPen()
            FONT.draw_glyph_with_pen(gid, pen)
            self.glyphs[key] = (f"g{len(self.glyphs)}", "".join(pen.out))
        return self.glyphs[key][0]

    @staticmethod
    def shape(text, mono, wght):
        axes = (("MONO", mono), ("wght", wght), ("CASL", 0), ("CRSV", 0.5), ("slnt", 0))
        FONT.set_variations(dict(axes))
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(FONT, buf, {"kern": True})
        return axes, list(zip(buf.glyph_infos, buf.glyph_positions))

    @staticmethod
    def width(text, size, mono=1, wght=400, track=0.0):
        _, run = Svg.shape(text, mono, wght)
        return (sum(p.x_advance for _, p in run) + track * UPM * (len(run) - 1)) * size / UPM

    def text(self, s, x, y, size, cls, mono=1, wght=400, track=0.0, anchor="start", each=None, attrs=""):
        """Places a run of glyphs with its baseline at y; returns its width. each(i) may give a glyph its own attributes."""
        axes, run = self.shape(s, mono, wght)
        k = size / UPM
        w = self.width(s, size, mono, wght, track)
        x0 = x - w if anchor == "end" else x - w / 2 if anchor == "middle" else x
        uses, at = [], 0.0
        for i, (info, pos) in enumerate(run):
            if s[info.cluster] != " ":
                extra = each(i) if each else ""
                uses.append(f'<use href="#{self.glyph(info.codepoint, axes)}" x="{round(at + pos.x_offset)}"{extra}/>')
            at += pos.x_advance + track * UPM
        self.parts.append(f'<g class="{cls}"{attrs} transform="translate({x0:.1f} {y}) scale({k:.5f} -{k:.5f})">{"".join(uses)}</g>')
        return w

    def add(self, s):
        self.parts.append(s)

    def render(self, theme):
        t = THEMES[theme]
        defs = "".join(f'<path id="{i}" d="{d}"/>' for i, d in self.glyphs.values())
        tokens = ";".join(f"--{k}:{v}" for k, v in t.items())
        css = (f"svg{{{tokens}}}"
               ".ink{fill:var(--ink)}.sub{fill:var(--sub)}.fnt{fill:var(--fnt)}.dim{fill:var(--dim)}.em{fill:var(--em)}"
               ".amb{fill:var(--amb)}.pk{fill:var(--pk)}.ax{fill:var(--ax)}.sky{fill:var(--sky)}"
               ".pn{fill:var(--s1);stroke:var(--ln)}.rule{stroke:var(--ln)}.dash{stroke:var(--l2);stroke-dasharray:2 4}"
               + "".join(self.css)
               + "@media (prefers-reduced-motion:reduce){*{animation:none!important}}")
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" width="{self.w}" height="{self.h}" '
                f'role="img" aria-labelledby="t d"><title id="t">{html.escape(self.title)}</title>'
                f'<desc id="d">{html.escape(self.desc)}</desc><style>{css}</style><defs>{defs}</defs>{"".join(self.parts)}</svg>\n')


# ── shared parts ─────────────────────────────────────────────────────────────────────────────────────────────────────────

def panel(svg, w, h, accent):
    """The site's panel: a hairline box with bracket corners (hud.css .br), 14 px arms, 2 px thick."""
    svg.add(f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="2" class="pn"/>')
    arms = "".join(f"M{x} {y + dy * 14}V{y}H{x + dx * 14}" for x, y, dx, dy in
                   [(1, 1, 1, 1), (w - 1, 1, -1, 1), (1, h - 1, 1, -1), (w - 1, h - 1, -1, -1)])
    svg.add(f'<path d="{arms}" fill="none" stroke="var(--{accent})" stroke-width="2"/>')


def status(svg, kind, x, y, size=12):
    """LIVE dot, IN BUILD gear, SHIPPED check, then the word (hud.css .st), right-aligned at x; returns its left edge."""
    word, colour = {"live": ("LIVE", "em"), "build": ("IN BUILD", "amb"), "shipped": ("SHIPPED", "em"),
                    "open": ("OPEN TO ROLES", "em")}[kind]
    w = svg.text(word, x, y, size, colour, wght=600, track=0.1, anchor="end")
    u = size / 12  # the icons are drawn for 12 px labels
    cx, cy = x - w - 12 * u, y - size * 0.36
    if kind in ("live", "open"):
        svg.add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{7 * u:.1f}" fill="var(--em)" opacity=".18" class="glow"/>'
                f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{3.5 * u:.1f}" fill="var(--em)"/>')
        svg.css.append("@keyframes glow{50%{opacity:.02}}.glow{animation:glow 2.4s ease-in-out infinite}")
    elif kind == "build":
        teeth = "".join(f'<rect x="-1.4" y="-7" width="2.8" height="3.2" transform="rotate({a})"/>' for a in range(0, 360, 45))
        svg.add(f'<g transform="translate({cx:.1f} {cy:.1f}) scale({u:.2f})" fill="var(--amb)"><g class="gear">{teeth}'
                f'<circle r="4.6" fill="none" stroke="var(--amb)" stroke-width="2.4"/></g></g>')
        svg.css.append("@keyframes gear{to{transform:rotate(360deg)}}.gear{animation:gear 7s linear infinite}")
    else:
        svg.add(f'<path d="M{cx - 5 * u:.1f} {cy:.1f}l{3.4 * u:.1f} {3.6 * u:.1f}l{6.6 * u:.1f}-{7.2 * u:.1f}" fill="none" stroke="var(--em)" stroke-width="{2.2 * u:.1f}"/>')
    return cx - 9 * u


def strip(svg, w, y, left, right_kind=None, right_text=None, size=12, pad=24):
    """The title sheet's strip (case.css .cs-tb .s): a label, a dashed rule, a status; then a hairline under it."""
    lw = svg.text(left, pad, y, size, "fnt", wght=500, track=0.1) if left else -14
    if right_kind:
        edge = status(svg, right_kind, w - pad, y, size)
    elif right_text:
        edge = w - pad - svg.text(right_text, w - pad, y, size, "fnt", wght=500, track=0.1, anchor="end") - 12
    else:
        edge = w - pad + 2
    if edge - (pad + lw + 14) > 24:
        svg.add(f'<path d="M{pad + lw + 14:.1f} {y - size * 0.36:.1f}H{edge - 2:.1f}" class="dash"/>')
    svg.add(f'<path d="M1 {y + size * 1.7:.0f}H{w - 1}" class="rule"/>')


def fit(text, size, maxw, **kw):
    """The largest size up to `size` at which the text fits maxw."""
    while Svg.width(text, size, **kw) > maxw and size > 10:
        size -= 1
    return size


def wrap(text, size, maxw, **kw):
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if line and Svg.width(trial, size, **kw) > maxw:
            lines.append(line)
            line = word
        else:
            line = trial
    return lines + [line]


# ── the images ───────────────────────────────────────────────────────────────────────────────────────────────────────────

def header():
    W, H = 1000, 312
    svg = Svg("header", W, H, "Abdullah Kahvecioglu: Design Engineer · AI-Native Product Builder",
              "Belgrade, Serbia (CET). Now Lead Design Engineer at DC Development. Open to design engineer roles. secretocho.design")
    panel(svg, W, H, "em")
    strip(svg, W, 40, "~/SECRETOCHODESIGN", "open")
    morph(svg, [("Abdullah Kahvecioglu", 34, 150)], 68)
    svg.text("Design Engineer · AI-Native Product Builder", 36, 196, 25, "sub", mono=0, wght=450, track=-0.02)
    svg.add(f'<path d="M1 228H{W - 1}M300 228V{H - 1}M700 228V{H - 1}" class="rule"/>')
    for x, label, value, cls in HEADER_CELLS:
        svg.text(label, x + 24, 258, 11.5, "fnt", wght=500, track=0.1)
        w = svg.text(value, x + 24, 288, 19, cls, mono=0, wght=450, track=-0.02)
        assert w < (300 if x != 300 else 400) - 40, f"header cell '{value}' is {w:.0f} px"
    return svg


HEADER_CELLS = [(0, "BASED", "Belgrade, Serbia · CET", "ink"), (300, "NOW", "Lead Design Engineer, DC Development", "ink"),
                (700, "SITE", "secretocho.design", "em")]


def morph(svg, lines, size):
    """The name compiles from mono to sans in eight steps, as the site's titles do (case.css cs-m): nine outline states.
    State i shows from its step to the next (steps(8) over .64 s after .12 s); the sans state is the resting one, so
    without motion only it is drawn."""
    for i in range(9):
        for text, x, y in lines:
            svg.text(text, x, y, size, f"ink m{i}", mono=1 - i / 8, wght=650, track=-0.04)
    span, step = 1.2, 0.64 / 8
    for i in range(9):
        a = 0 if i == 0 else 0.12 + i * step
        b = 0.12 + (i + 1) * step
        pa, pb = a / span * 100, b / span * 100
        if i < 8:
            svg.css.append(f".m{i}{{opacity:0;animation:m{i} {span}s step-end}}"
                           f"@keyframes m{i}{{0%{{opacity:{1 if i == 0 else 0}}}{pa:.2f}%{{opacity:1}}{pb:.2f}%,100%{{opacity:0}}}}")
        else:
            svg.css.append(f".m8{{animation:m8 {span}s step-end}}@keyframes m8{{0%{{opacity:0}}{pa:.2f}%,100%{{opacity:1}}}}")


# ── the narrow images: GitHub on a phone shows the README about 350 px wide, so these draw at 600 units with larger type ──
NW = 600


def header_narrow():
    H = 560
    svg = Svg("header-narrow", NW, H, "Abdullah Kahvecioglu: Design Engineer · AI-Native Product Builder",
              "Belgrade, Serbia (CET). Now Lead Design Engineer at DC Development. Open to design engineer roles. secretocho.design")
    panel(svg, NW, H, "em")
    strip(svg, NW, 46, "", "open", size=20)
    morph(svg, [("Abdullah", 28, 160), ("Kahvecioglu", 28, 236)], 76)
    for i, line in enumerate(["Design Engineer ·", "AI-Native Product Builder"]):
        svg.text(line, 30, 292 + i * 38, 31, "sub", mono=0, wght=450, track=-0.02)
    for i, (_, label, value, cls) in enumerate(HEADER_CELLS):
        y = 368 + i * 64
        svg.add(f'<path d="M1 {y}H{NW - 1}" class="rule"/>')
        svg.text(label, 30, y + 26, 16, "fnt", wght=500, track=0.1)
        assert svg.text(value, 30, y + 54, 24, cls, mono=0, wght=450, track=-0.02) < NW - 60, value
    return svg


SESSION = [
    ("whoami", [("Abdullah Kahvecioglu · design engineer · Belgrade, CET", "ink")]),
    ("ls ~/work", [("novi-kvadrat/  probababy/  sultana-express/  axel-properties/  nk-design-system/  lab/", "em")]),
    ("cat ~/method | head -1", [("AI writes the code. Taste decides what ships.", "ink")]),
    ("status", [("● open to design engineer roles · remote, or relocation for the right team", "ink")]),
]
SESSION_NARROW = [
    ("whoami", [("Abdullah Kahvecioglu", "ink"), ("design engineer · Belgrade, CET", "ink")]),
    ("ls ~/work", [("novi-kvadrat/  probababy/", "em"), ("sultana-express/  lab/", "em"), ("axel-properties/", "em"),
                   ("nk-design-system/", "em")]),
    ("cat ~/method | head -1", [("AI writes the code.", "ink"), ("Taste decides what ships.", "ink")]),
    ("status", [("● open to design engineer roles", "ink"), ("  remote, or relocation", "ink")]),
]


def console(narrow=False):
    W, step, size, top = (NW, 34, 20, 112) if narrow else (1000, 28, 15.5, 96)
    session = SESSION_NARROW if narrow else SESSION
    H = top + step * sum(1 + len(o) for _, o in session) + 22
    svg = Svg("console-narrow" if narrow else "console", W, H, "A console session",
              "whoami: Abdullah Kahvecioglu, design engineer, Belgrade, CET. ls ~/work: novi-kvadrat, probababy, sultana-express, "
              "axel-properties, nk-design-system, lab. The method: AI writes the code. Taste decides what ships. Status: open to "
              "design engineer roles, remote, or relocation for the right team.")
    panel(svg, W, H, "l2")
    if narrow:
        strip(svg, W, 46, "_> CONSOLE", size=18)
    else:
        strip(svg, W, 40, "_> CONSOLE", right_text="SECRETOCHO.DESIGN")
    svg.css.append("@keyframes hide{0%,100%{opacity:0}}.h{animation:hide var(--t) step-end}"
                   "@keyframes blink{50%{opacity:0}}")
    x0, cw = (28 if narrow else 36), Svg.width("_> ", size)
    y, t = top, 0.7
    for cmd, outputs in session:
        svg.text("_>", x0, y, size, "em h", wght=500, attrs=f' style="--t:{t:.2f}s"')
        start = t
        svg.text(cmd, x0 + cw, y, size, "ink", wght=500, each=lambda i, s=start: f' class="h" style="--t:{s + 0.06 * (i + 1):.2f}s"')
        t = start + 0.06 * len(cmd) + 0.3
        y += step
        for line, cls in outputs:
            if line.startswith("● "):  # Recursive has no bullet: the site's LIVE dot
                svg.add(f'<circle cx="{x0 + cw + size * .28:.1f}" cy="{y - size * .36:.1f}" r="{size * .23:.1f}" fill="var(--em)" class="h" style="--t:{t:.2f}s"/>')
                line = "  " + line[2:]
            assert svg.text(line, x0 + cw, y, size, f"{cls} h", attrs=f' style="--t:{t:.2f}s"') < W - x0 - cw - 20, line
            y += step
        t += 0.7
    svg.text("_>", x0, y, size, "em h", wght=500, attrs=f' style="--t:{t:.2f}s"')
    svg.add(f'<rect x="{x0 + cw:.1f}" y="{y - size * .9:.1f}" width="{size * .58:.1f}" height="{size * 1.1:.1f}" fill="var(--em)" class="cur" style="--t:{t:.2f}s"/>')
    svg.css.append(".cur{animation:hide var(--t) step-end,blink 1.1s step-end var(--t) infinite}")
    return svg


STAGES = [("prompt", "the idea, in words"), ("research", "many research files"), ("leaders", "how the best do it"),
          ("analysis", "their approaches"), ("compare", "against the project"), ("evaluate", "what fits, what not"),
          ("master plan", "the whole build"), ("phase plan", "one phase at a time"), ("build", "agents write code"),
          ("test", "code tests, eye test")]


def method():
    W, H, bw, bh, gap = 1000, 362, 160, 72, 32
    svg = Svg("method", W, H, "The method: ten stages, from prompt to test",
              "Prompt, research, leaders, analysis, compare, evaluate, master plan, phase plan, build, test. "
              "Nothing merges until every gate is green.")
    panel(svg, W, H, "l2")
    strip(svg, W, 40, "METHOD · TEN STAGES", right_text="AI WRITES THE CODE · TASTE DECIDES WHAT SHIPS")
    col = lambda c: 36 + c * (bw + gap)
    rows = [88, 200]
    cycle, first, each = 12.0, 0.6, 0.8
    pct = lambda s: s / cycle * 100
    flows = []
    for i, (name, note) in enumerate(STAGES):
        r, c = divmod(i, 5)
        c = c if r == 0 else 4 - c
        x, y = col(c), rows[r]
        on = pct(first + i * each)
        svg.css.append(f"@keyframes s{i}{{0%,{on - .01:.2f}%{{stroke:var(--l2);fill:var(--s1)}}{on:.2f}%,96%{{stroke:var(--em);fill:var(--emw)}}"
                       f"100%{{stroke:var(--l2);fill:var(--s1)}}}}.s{i}{{animation:s{i} {cycle}s linear infinite}}")
        svg.add(f'<rect x="{x + .5}" y="{y + .5}" width="{bw - 1}" height="{bh - 1}" rx="2" fill="var(--emw)" stroke="var(--em)" class="s{i}"/>')
        svg.text(f"{i + 1:02d}", x + 14, y + 22, 11, "fnt", wght=500, track=0.1)
        svg.text(name, x + 14, y + 45, 16, "ink", wght=500)
        assert svg.text(note, x + 14, y + 62, 12.5, "fnt", mono=0, wght=400, track=-0.01) < bw - 24, note
        if i < 9:  # the connector to the next stage
            nr, nc = divmod(i + 1, 5)
            nc = nc if nr == 0 else 4 - nc
            if nr != r:
                flows.append(f"M{x + bw / 2} {y + bh + 4}V{rows[nr] - 6}")
            elif r == 0:
                flows.append(f"M{x + bw + 5} {y + bh / 2}H{col(nc) - 7}")
            else:
                flows.append(f"M{x - 5} {y + bh / 2}H{col(nc) + bw + 7}")
    # after test, the gate: merge only when every gate is green
    x, y = col(0), rows[1] + bh
    flows.append(f"M{x + bw / 2} {y + 4}V{y + 26}")
    gate = pct(first + 10 * each)
    svg.css.append(f"@keyframes gt{{0%,{gate - .01:.2f}%{{stroke:var(--l2);fill:var(--s1)}}{gate:.2f}%,96%{{stroke:var(--em);fill:var(--emw)}}"
                   f"100%{{stroke:var(--l2);fill:var(--s1)}}}}.gt{{animation:gt {cycle}s linear infinite}}")
    svg.add(f'<rect x="{x + .5}" y="{y + 32.5}" width="{bw - 1}" height="31" rx="15.5" fill="var(--emw)" stroke="var(--em)" class="gt"/>')
    svg.add(f'<path d="M{x + 22} {y + 48}l3.4 3.6l6.6-7.2" fill="none" stroke="var(--em)" stroke-width="2.2"/>')
    svg.text("MERGE", x + 42, y + 52.5, 12, "em", wght=600, track=0.1)
    note = svg.text("nothing merges until every gate is green: unit and end-to-end tests, visual baselines, tested SQL proofs",
                    x + bw + 22, y + 53, 14, "sub", mono=0, wght=400, track=-0.01)
    assert x + bw + 22 + note < W - 24, f"the gate note is {note:.0f} px"
    svg.add(f'<path d="{"".join(flows)}" fill="none" stroke="var(--em)" stroke-width="1.5" stroke-dasharray="4 4" class="flow"/>')
    svg.css.append("@keyframes flow{to{stroke-dashoffset:-8}}.flow{animation:flow .6s linear infinite}")
    return svg


def method_narrow():
    """The ten stages as one column, read top to bottom, with the gate at the foot."""
    W, bh, gap, top, x = NW, 78, 26, 110, 28
    H = top + 10 * (bh + gap) + 150
    svg = Svg("method-narrow", W, H, "The method: ten stages, from prompt to test",
              "Prompt, research, leaders, analysis, compare, evaluate, master plan, phase plan, build, test. "
              "Nothing merges until every gate is green.")
    panel(svg, W, H, "l2")
    strip(svg, W, 46, "METHOD · TEN STAGES", size=18)
    cycle, first, each = 12.0, 0.6, 0.8
    pct = lambda t: t / cycle * 100
    flows = []
    for i, (name, note) in enumerate(STAGES):
        y = top + i * (bh + gap)
        on = pct(first + i * each)
        svg.css.append(f"@keyframes s{i}{{0%,{on - .01:.2f}%{{stroke:var(--l2);fill:var(--s1)}}{on:.2f}%,96%{{stroke:var(--em);fill:var(--emw)}}"
                       f"100%{{stroke:var(--l2);fill:var(--s1)}}}}.s{i}{{animation:s{i} {cycle}s linear infinite}}")
        svg.add(f'<rect x="{x + .5}" y="{y + .5}" width="{W - 2 * x - 1}" height="{bh - 1}" rx="2" fill="var(--emw)" stroke="var(--em)" class="s{i}"/>')
        svg.text(f"{i + 1:02d}", x + 22, y + 48, 18, "fnt", wght=500, track=0.1)
        svg.text(name, x + 84, y + 36, 24, "ink", wght=500)
        svg.text(note, x + 84, y + 62, 19, "fnt", mono=0, wght=400, track=-0.01)
        flows.append(f"M{x + 40} {y + bh + 4}V{y + bh + gap - 4}")
    y = top + 10 * (bh + gap)
    gate = pct(first + 10 * each)
    svg.css.append(f"@keyframes gt{{0%,{gate - .01:.2f}%{{stroke:var(--l2);fill:var(--s1)}}{gate:.2f}%,96%{{stroke:var(--em);fill:var(--emw)}}"
                   f"100%{{stroke:var(--l2);fill:var(--s1)}}}}.gt{{animation:gt {cycle}s linear infinite}}")
    svg.add(f'<rect x="{x + .5}" y="{y + .5}" width="200" height="43" rx="21.5" fill="var(--emw)" stroke="var(--em)" class="gt"/>')
    svg.add(f'<path d="M{x + 28} {y + 22}l5 5.3l9.7-10.6" fill="none" stroke="var(--em)" stroke-width="3"/>')
    svg.text("MERGE", x + 58, y + 29, 18, "em", wght=600, track=0.1)
    for i, line in enumerate(["nothing merges until every gate is green:", "tests, visual baselines, tested SQL proofs"]):
        assert svg.text(line, x, y + 84 + i * 30, 20, "sub", mono=0, wght=400, track=-0.01) < W - 2 * x, line
    svg.add(f'<path d="{"".join(flows)}" fill="none" stroke="var(--em)" stroke-width="2" stroke-dasharray="5 5" class="flow"/>')
    svg.css.append("@keyframes flow{to{stroke-dashoffset:-10}}.flow{animation:flow .6s linear infinite}")
    return svg


def card_narrow(slug, kicker, state, name, accent, summary, facts, stack, href):
    """A phone shows two cards in a row at about 170 px each: the status, the name and the way in, at a size that reads."""
    W, H = 300, 230
    svg = Svg(f"card-{slug}-narrow", W, H, f"{name}: {summary}", f"Case study: {SITE}{href}")
    panel(svg, W, H, accent)
    strip(svg, W, 38, kicker.split(" · ")[0], state, size=18, pad=20)
    size = 40
    while len(lines := wrap(name, size, W - 40, mono=0, wght=650, track=-0.04)) > 2:
        size -= 2
    for i, line in enumerate(lines):
        svg.text(line, 20, 118 + i * (size + 4), size, "ink", mono=0, wght=650, track=-0.04)
    svg.text("open →", 20, H - 22, 20, accent, wght=600)
    return svg


CARDS = [
    ("novi-kvadrat", "01 · SOLE DESIGNER AND DEVELOPER", "live", "Novi Kvadrat", "em",
     "A five-language property platform for Serbia, built end to end: marketplaces, portal, admin and studios.",
     [("5", "languages"), ("3", "in-browser studios"), ("RLS", "on every table")], "Next.js · Supabase · PostGIS · MapLibre",
     "/work/novi-kvadrat/"),
    ("probababy", "02 · BUILT ALONE, END TO END", "live", "ProbaBaby", "pk",
     "A twins-first baby tracker for iPhone, iPad and Apple Watch, built alone from prototype to App Store.",
     [("32", "languages"), ("17", "widgets"), ("8", "Live Activities")], "Swift · SwiftUI · SwiftData · Supabase",
     "/work/probababy/"),
    ("sultana-express", "03 · CO-FOUNDER AND CTO · SIDE PROJECT", "build", "Sultana Express", "amb",
     "A B2B sourcing marketplace for Turkish manufacturing, rebuilt from a no-code prototype as a platform.",
     [("38", "Go modules"), ("556", "API operations"), ("45", "decision records")],
     "Go · Next.js · Kubernetes · NATS JetStream", "/work/sultana-express/"),
    ("axel-properties", "04 · DESIGN LEAD", "shipped", "Axel Properties", "ax",
     "A brand system for a riverside development, from the mark on its construction grid to signage.",
     [("38", "guideline sections"), ("42", "delivered assets"), ("15", "primary colours")],
     "Brand · Illustrator · Framer · React", "/work/axel-properties/"),
    ("novi-kvadrat-design-system", "05 · DESIGNER AND DEVELOPER OF THE SYSTEM", "live", "Novi Kvadrat Design System", "em",
     "One design system for a property platform, from the mark to the tokens, in light and dark.",
     [("187", "colour roles"), ("21", "type steps"), ("W3C", "DTCG tokens")], "Figma · design tokens · CSS · Tailwind",
     "/work/novi-kvadrat-design-system/"),
    ("lab", "06 · OPEN CODE", "live", "SecretoCho Lab", "sky",
     "Twenty-eight code components for Framer, each with a live demo, its docs and its source.",
     [("28", "components"), ("28", "live demos"), ("3D", "Three.js and WebGL")], "React · TypeScript · Three.js · WebGL",
     "/lab/"),
]


def card(slug, kicker, state, name, accent, summary, facts, stack, href):
    W, H = 500, 316
    svg = Svg(f"card-{slug}", W, H, f"{name}: {summary}",
              f"{kicker.split(' · ', 1)[1].capitalize()}. " + ". ".join(f"{v} {l}" for v, l in facts) + f". {stack}. Case study: {SITE}{href}")
    panel(svg, W, H, accent)
    strip(svg, W, 36, kicker, state, size=11)
    size = fit(name, 34, W - 48, mono=0, wght=650, track=-0.04)
    svg.text(name, 24, 104, size, "ink", mono=0, wght=650, track=-0.04)
    lines = wrap(summary, 16, W - 48, mono=0, wght=400, track=-0.02)
    assert len(lines) <= 2, f"{name}: summary is {len(lines)} lines"
    for i, line in enumerate(lines):
        svg.text(line, 24, 138 + i * 23, 16, "sub", mono=0, wght=400, track=-0.02)
    svg.add(f'<path d="M1 190H{W - 1}M{W / 3:.1f} 190V266M{2 * W / 3:.1f} 190V266M1 266H{W - 1}" class="rule"/>')
    for i, (value, label) in enumerate(facts):
        x = 20 + i * W / 3
        svg.text(value, x, 226, 24, "ink", wght=650)
        assert svg.text(label, x, 252, 12.5, "fnt", mono=0, wght=400, track=-0.01) < W / 3 - 28, label
    svg.text(stack, 24, 296, 12, "fnt", wght=400, track=0.02)
    svg.text("open case →" if href.startswith("/work") else "open lab →", W - 24, 296, 12, accent, wght=600, anchor="end")
    return svg


def main():
    ASSETS.mkdir(exist_ok=True)
    images = [header(), header_narrow(), console(), console(narrow=True), method(), method_narrow()]
    images += [card(*c) for c in CARDS] + [card_narrow(*c) for c in CARDS]
    for svg in images:
        for theme in THEMES:
            out = ASSETS / f"{svg.name}-{theme}.svg"
            out.write_text(svg.render(theme))
        print(f"assets/{svg.name}-*.svg: {out.stat().st_size:,} bytes, {len(svg.glyphs)} glyph outlines")


if __name__ == "__main__":
    main()
