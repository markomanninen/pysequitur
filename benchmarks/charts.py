"""
Draws the charts of doc/performance.md from the measurements in benchmarks/results/:

    python benchmarks/charts.py

Each chart is written twice, for light and dark pages, as doc/images/NAME-light.svg
and NAME-dark.svg.
"""
import json
import math
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE / 'results'
OUT = HERE.parent / 'doc' / 'images'

THEMES = {
    'light': {'surface': '#fcfcfb', 'ink': '#0b0b0b', 'ink2': '#52514e', 'muted': '#898781', 'grid': '#e1e0d9',
              'axis': '#c3c2b7', 'series': ['#2a78d6', '#eb6834', '#1baf7a', '#eda100']},
    'dark': {'surface': '#1a1a19', 'ink': '#f0efec', 'ink2': '#c3c2b7', 'muted': '#898781', 'grid': '#2c2c2a',
             'axis': '#383835', 'series': ['#3987e5', '#d95926', '#199e70', '#c98500']},
}
FONT = "font-family='-apple-system, BlinkMacSystemFont, Segoe UI, Helvetica, Arial, sans-serif'"


def svg(width, height, theme, body):
    return ("<svg xmlns='http://www.w3.org/2000/svg' width='%d' height='%d' viewBox='0 0 %d %d' %s>"
            "<rect width='100%%' height='100%%' rx='8' fill='%s'/>%s</svg>\n"
            % (width, height, width, height, FONT, theme['surface'], ''.join(body)))


def text(x, y, s, fill, size=12, anchor='start', weight='normal'):
    return "<text x='%.1f' y='%.1f' fill='%s' font-size='%d' text-anchor='%s' font-weight='%s'>%s</text>" % (
        x, y, fill, size, anchor, weight, escape(s))


def size_label(chars):
    return '%g MB' % (chars / 1e6) if chars >= 1e6 else '%g KB' % (chars / 1e3)


def time_label(seconds):
    if seconds >= 1:
        return '%.2g s' % seconds if seconds < 10 else '%.0f s' % seconds
    return '%.2g ms' % (seconds * 1000) if seconds < 0.01 else '%.0f ms' % (seconds * 1000)


def scaling(theme):
    rows = json.loads((RESULTS / 'scaling.json').read_text())
    names = list(dict.fromkeys(r['implementation'] for r in rows))
    W, H, left, right, top, bottom = 760, 440, 64, 150, 56, 48
    xs = [1e3, 1e4, 1e5, 1.6e6]
    x0, x1 = math.log10(1e3), math.log10(1.6e6)
    y0, y1 = -3, 2  # 1 ms to 100 s
    X = lambda c: left + (math.log10(c) - x0) / (x1 - x0) * (W - left - right)  # noqa: E731
    Y = lambda s: top + (y1 - math.log10(s)) / (y1 - y0) * (H - top - bottom)  # noqa: E731
    body = [text(left, 26, 'Time to build the grammar against the length of the input', theme['ink'], 15, weight='600'),
            text(left, 44, 'Prefixes of 1.6 MB of Python source, log scales', theme['ink2'], 12)]
    for e in range(y0, y1 + 1):
        y = Y(10 ** e)
        body.append("<line x1='%d' x2='%d' y1='%.1f' y2='%.1f' stroke='%s' stroke-width='1'/>" % (
            left, W - right, y, y, theme['grid']))
        body.append(text(left - 8, y + 4, time_label(10 ** e), theme['muted'], 11, 'end'))
    for c in xs[:-1]:
        body.append(text(X(c), H - bottom + 18, size_label(c), theme['muted'], 11, 'middle'))
    body.append(text(X(1.6e6), H - bottom + 18, '1.6 MB', theme['muted'], 11, 'middle'))
    body.append("<line x1='%d' x2='%d' y1='%d' y2='%d' stroke='%s'/>" % (left, W - right, H - bottom, H - bottom, theme['axis']))
    labels = []
    for i, name in enumerate(names):
        points = [(r['chars'], r['seconds']) for r in rows if r['implementation'] == name]
        color = theme['series'][i]
        path = ' '.join('%s%.1f,%.1f' % ('M' if k == 0 else 'L', X(c), Y(s)) for k, (c, s) in enumerate(points))
        body.append("<path d='%s' fill='none' stroke='%s' stroke-width='2' stroke-linejoin='round'/>" % (path, color))
        for c, s in points:
            body.append("<circle cx='%.1f' cy='%.1f' r='4' fill='%s' stroke='%s' stroke-width='2'><title>%s: %s, %s</title></circle>"
                        % (X(c), Y(s), color, theme['surface'], escape(name), size_label(c), time_label(s)))
        c, s = points[-1]
        labels.append([Y(s), X(c), name, color, s])
    # direct labels at the line ends, nudged apart
    labels.sort()
    for k in range(1, len(labels)):
        labels[k][0] = max(labels[k][0], labels[k - 1][0] + 16)
    for y, x, name, color, s in labels:
        body.append("<line x1='%.1f' x2='%.1f' y1='%.1f' y2='%.1f' stroke='%s' stroke-width='2'/>" % (x + 8, x + 18, y, y, color))
        body.append(text(x + 22, y + 4, '%s, %s' % (name, time_label(s)), theme['ink'], 12))
    return svg(W, H, theme, body)


def compare(theme):
    rows = [r for r in json.loads((RESULTS / 'compare.json').read_text()) if r['input'].startswith('Python source')]
    ok = sorted((r for r in rows if 'error' not in r), key=lambda r: r['seconds'])
    failed = [r for r in rows if 'error' in r]
    W, row_h, top, label_w, gap = 760, 28, 70, 230, 40
    panel = (W - label_w - gap - 32) / 2
    H = top + row_h * (len(ok) + len(failed)) + 24
    color = theme['series'][0]
    body = [text(16, 26, 'Building the grammar of 1.6 MB of Python source', theme['ink'], 15, weight='600'),
            text(16, 44, 'Median of three runs, each in a fresh process', theme['ink2'], 12)]
    panels = [('Seconds', 'seconds', label_w, lambda v: '%.2f' % v), ('Peak memory, MB', 'memory_mb', label_w + panel + gap,
                                                                   lambda v: '%.0f' % v)]
    for title, key, x0, fmt in panels:
        top_value = max(r[key] for r in ok)
        body.append(text(x0, top - 10, title, theme['ink2'], 12, weight='600'))
        width = panel - 44
        for k, r in enumerate(ok):
            y = top + k * row_h
            w = max(2, r[key] / top_value * width)
            body.append("<path d='M%.1f,%.1f h%.1f a4,4 0 0 1 4,4 v%d a4,4 0 0 1 -4,4 h-%.1f z' fill='%s'><title>%s: %s</title></path>"
                        % (x0, y + 4, w - 4, row_h - 16, w - 4, color, escape(r['implementation']), fmt(r[key])))
            body.append(text(x0 + w + 6, y + row_h / 2 + 4, fmt(r[key]), theme['ink'], 11))
        body.append("<line x1='%.1f' x2='%.1f' y1='%d' y2='%d' stroke='%s'/>" % (x0, x0, top, top + row_h * len(ok), theme['axis']))
    for k, r in enumerate(ok + failed):
        y = top + k * row_h + row_h / 2 + 4
        bold = r['implementation'].startswith('pysequitur') and 'before' not in r['implementation']
        body.append(text(label_w - 12, y, r['implementation'], theme['ink'], 12, 'end', '600' if bold else 'normal'))
        if 'error' in r:
            body.append(text(label_w, y, 'crashes', theme['ink2'], 12))
    return svg(W, H, theme, body)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, draw in [('scaling', scaling), ('compare', compare)]:
        for mode, theme in THEMES.items():
            (OUT / ('%s-%s.svg' % (name, mode))).write_text(draw(theme))
            print(OUT / ('%s-%s.svg' % (name, mode)))


if __name__ == '__main__':
    main()
