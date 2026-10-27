"""
Draws the article's header image from pysequitur's own analysis of "Pease
Porridge Hot": the text on a strip of paper, and an arc for every pair of
consecutive occurrences of each repeated phrase, the arcs of "pease porridge"
in amber.

    python doc/substack/make_header.py     # writes article_images/header.png
"""
import subprocess
import sys
import tempfile
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))

from pysequitur.analysis import Analysis  # noqa: E402

CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
W, H = 1456, 819
X0, ADVANCE = 66, 8.3
STRIP_TOP, BASELINE = 610, 642
PHRASE = 'pease porridge'


def band(a, b, c, d, color, opacity):
    """A band from the span a..b to the span c..d (x positions), rising above the strip."""
    def arc(x1, x2):
        r = (x2 - x1) / 2
        return r, min(r * 0.9, STRIP_TOP - 175)
    ro, ho = arc(a, d)
    ri, hi = arc(b, c)
    y = STRIP_TOP - 4
    return ("<path d='M%.1f,%d A%.1f,%.1f 0 0 1 %.1f,%d L%.1f,%d A%.1f,%.1f 0 0 0 %.1f,%d Z' fill='%s' "
            "fill-opacity='%.2f' stroke='%s' stroke-opacity='%.2f' stroke-width='1'/>"
            % (a, y, ro, ho, d, y, c, y, max(ri, 0.1), max(hi, 0.1), b, y, color, opacity, color, opacity + 0.15))


def main():
    path = ROOT / 'samples' / 'peaseporridge.txt'
    text = path.read_text().strip()
    analysis = Analysis.from_text(text, tokens='char')
    x = lambda i: X0 + i * ADVANCE  # noqa: E731

    bands = []
    rules = analysis.repeats(min_chars=3, limit=200)['repeats']
    for r in sorted(rules, key=lambda r: -r['chars']):
        spans = analysis.text_positions(r['rule'])
        for (_, s1, e1), (_, s2, e2) in zip(spans, spans[1:]):
            bands.append(band(x(s1), x(e1), x(s2), x(e2), '#f4efe4', 0.07 if r['chars'] > 20 else 0.11))
    starts = [i for i in range(len(text)) if text.startswith(PHRASE, i)]
    n = len(PHRASE)
    for s1, s2 in [(starts[0], starts[2]), (starts[0], starts[1]), (starts[1], starts[2])]:
        bands.append(band(x(s1), x(s1 + n), x(s2), x(s2 + n), '#f0a640', 0.2))

    glyphs = []
    for i, ch in enumerate(text):
        if ch == '\n':
            glyphs.append("<text x='%.1f' y='%d' class='sep'>/</text>" % (x(i) + 1, BASELINE))
        elif ch != ' ':
            amber = any(s <= i < s + n for s in starts)
            glyphs.append("<text x='%.1f' y='%d' class='%s'>%s</text>" % (x(i), BASELINE, 'hi' if amber else 'ch', escape(ch)))

    # a faint constellation for the agent, with a few lines reaching toward the arcs
    nodes = [(64, 236), (118, 204), (160, 262), (104, 300), (52, 350), (140, 360), (196, 318), (88, 404)]
    edges = [(0, 1), (1, 2), (2, 3), (3, 0), (3, 4), (3, 5), (5, 6), (2, 6), (4, 7), (5, 7)]
    reach = [(1, 420, 250), (6, 470, 330), (5, 300, 420)]
    agent = ''.join("<line x1='%d' y1='%d' x2='%d' y2='%d' class='edge'/>" % (*nodes[a], *nodes[b]) for a, b in edges)
    agent += ''.join("<line x1='%d' y1='%d' x2='%d' y2='%d' class='reach'/>" % (*nodes[k], tx, ty) for k, tx, ty in reach)
    agent += ''.join("<circle cx='%d' cy='%d' r='%d' class='node'/>" % (cx, cy, 4 if k % 3 else 6)
                     for k, (cx, cy) in enumerate(nodes))

    page = """<!doctype html><meta charset='utf-8'><style>
html,body{margin:0;background:#3a4756}
svg{display:block}
.ch{font:13.8px 'Courier New',monospace;fill:#3b3a36}
.hi{font:bold 13.8px 'Courier New',monospace;fill:#8a4f0c}
.sep{font:13.8px 'Courier New',monospace;fill:#a59f92}
.edge{stroke:#c9d3de;stroke-opacity:.28;stroke-width:1.2}
.reach{stroke:#c9d3de;stroke-opacity:.16;stroke-width:1;stroke-dasharray:2 5}
.node{fill:#dfe6ee;fill-opacity:.55}
</style>
<svg xmlns='http://www.w3.org/2000/svg' width='%d' height='%d'>
<defs>
 <radialGradient id='bg' cx='60%%' cy='45%%' r='80%%'><stop offset='0' stop-color='#4a5a6b'/><stop offset='1' stop-color='#2f3a47'/></radialGradient>
 <filter id='paper'><feTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='3' seed='4'/>
  <feColorMatrix values='0 0 0 0 .45  0 0 0 0 .40  0 0 0 0 .33  0 0 0 .10 0'/><feComposite in2='SourceGraphic' operator='in'/></filter>
 <filter id='grain'><feTurbulence type='fractalNoise' baseFrequency='.6' numOctaves='2' seed='9'/>
  <feColorMatrix values='0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 .035 0'/></filter>
</defs>
<rect width='100%%' height='100%%' fill='url(#bg)'/>
<rect width='100%%' height='100%%' filter='url(#grain)'/>
%s
<g>%s</g>
<g transform='rotate(-0.4 728 636)'>
 <rect x='%d' y='%d' width='%d' height='52' rx='2' fill='#ece5d6'/>
 <rect x='%d' y='%d' width='%d' height='52' rx='2' fill='#ece5d6' filter='url(#paper)'/>
</g>
%s
<text x='70' y='150' style="font:italic 104px 'Baskerville','Georgia',serif;fill:#f1e2c4;letter-spacing:1px">Sequitur</text>
</svg>""" % (W, H, agent, ''.join(bands), X0 - 22, STRIP_TOP, W - 2 * (X0 - 22), X0 - 22, STRIP_TOP,
              W - 2 * (X0 - 22), ''.join(glyphs))
    with tempfile.TemporaryDirectory() as tmp:
        page_path = Path(tmp) / 'header.html'
        page_path.write_text(page)
        out = HERE / 'article_images' / 'header.png'
        subprocess.run([CHROME, '--headless=new', '--force-device-scale-factor=2', '--hide-scrollbars',
                        '--window-size=%d,%d' % (W, H), '--screenshot=%s' % out, page_path.as_uri()],
                       check=True, capture_output=True)
    print(out)


if __name__ == '__main__':
    main()
