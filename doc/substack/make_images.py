"""
Renders the article's images for Substack, which has no tables: the tables as
images, and screenshots of the visualizer. Each is an HTML page captured with
headless Chrome at twice the pixel density and trimmed.

    python doc/substack/make_images.py     (needs Pillow and Google Chrome)
"""
import html
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageChops

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = HERE / 'article_images'
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
sys.path.insert(0, str(ROOT))

from pysequitur.analysis import Analysis  # noqa: E402
from pysequitur.viz import write_html  # noqa: E402

PAGE = (249, 249, 247)  # the visualizer's light page colour

CSS = """
body { margin: 0; background: #fff; font: 17px/1.45 -apple-system, "Helvetica Neue", Arial, sans-serif; color: #1f2933; }
figure { margin: 0; padding: 28px 32px; width: 1040px; }
figcaption { font-weight: 600; font-size: 19px; margin-bottom: 14px; }
table { border-collapse: collapse; width: 100%; }
th, td { padding: 8px 12px; border-bottom: 1px solid #e3e8ee; text-align: left; vertical-align: top; }
th { font-size: 14px; text-transform: uppercase; letter-spacing: .03em; color: #52606d; border-bottom: 2px solid #9aa5b1; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
tr.hl td { background: #fbf6ec; }
td.bad { color: #b0412e; font-weight: 600; }
p.note { color: #616e7c; font-size: 14px; margin-top: 10px; }
"""


def capture(url, name, width, height, background='white'):
    with tempfile.TemporaryDirectory() as tmp:
        shot = Path(tmp) / 'shot.png'
        subprocess.run([CHROME, '--headless=new', '--hide-scrollbars', '--force-device-scale-factor=2',
                        '--virtual-time-budget=4000', '--window-size=%d,%d' % (width, height),
                        '--screenshot=%s' % shot, url], check=True, capture_output=True)
        image = Image.open(shot).convert('RGB')
    # cut the empty space below and to the right, keeping a margin
    box = ImageChops.difference(image, Image.new('RGB', image.size, background)).getbbox()
    image = image.crop((0, 0, min(image.width, box[2] + 64), min(image.height, box[3] + 56)))
    image.save(OUT / ('%s.png' % name))


def table(name, title, headers, rows, note, highlight=(), bad=(), text=()):
    """rows: lists of cells. The first column and those in text are text, the others numbers.
    bad: (row, column) pairs to mark."""
    def kind(c):
        return '' if c == 0 or c in text else 'num'
    head = '<tr>%s</tr>' % ''.join('<th class="%s">%s</th>' % (kind(c), html.escape(h)) for c, h in enumerate(headers))
    body = []
    for r, row in enumerate(rows):
        cells = ['<td class="%s%s">%s</td>' % (kind(c), ' bad' if (r, c) in bad else '', html.escape(str(value)))
                 for c, value in enumerate(row)]
        body.append('<tr%s>%s</tr>' % (' class="hl"' if r in highlight else '', ''.join(cells)))
    page = ('<!doctype html><meta charset="utf-8"><style>%s</style><figure><figcaption>%s</figcaption>'
            '<table><thead>%s</thead><tbody>%s</tbody></table><p class="note">%s</p></figure>'
            % (CSS, html.escape(title), head, ''.join(body), html.escape(note)))
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'table.html'
        path.write_text(page, encoding='utf-8')
        capture(path.as_uri(), name, 1104, 1200)


def screenshots():
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / 'revelation.html'
        write_html(Analysis.from_text((ROOT / 'samples' / 'revelation.txt').read_text(), name='revelation.txt',
                                      tokens='char'), report)
        # rule 652 is the refrain "he that hath an ear, let him hear what the Spirit saith unto the churches"
        capture(report.as_uri() + '#rule=652&theme=light&figure=overview', 'viz_overview', 1280, 1000, PAGE)
        capture(report.as_uri() + '#rule=652&theme=light&figure=phrase', 'viz_phrase', 1280, 940, PAGE)
        tasks = ROOT / 'benchmarks' / 'field_test' / 'tasks' / 'copied'
        report = Path(tmp) / 'copied.html'
        write_html(Analysis([('A.txt (Alice)', (tasks / 'A.txt').read_text()),
                             ('B.txt (Looking-Glass)', (tasks / 'B.txt').read_text())], tokens='word'), report)
        capture(report.as_uri() + '#theme=light&figure=shared', 'viz_shared', 1280, 1100, PAGE)


def tables():
    table('table_speed', 'Building the grammar, and how it compares with the C++ reference',
          ['Implementation', 'Language', 'Revelation, 46.5 KB', '1.6 MB of source', 'Its grammar'],
          [['Reference, Nevill-Manning', 'C++', '0.027 s', '0.42 s', 'the reference'],
           ['jsdw/cpp-sequitur', 'C++', '0.008 s', '0.39 s', '42 fewer symbols'],
           ['sequitur-rs', 'Rust', '0.006 s', '0.22 s', '42 fewer symbols'],
           ['Port by Eibe Frank, 1997', 'Java', '0.026 s', '0.37 s', 'different'],
           ['Version by Nevill-Manning', 'JavaScript', '0.081 s', '3.24 s', 'loses text'],
           ['pysequitur', 'Python', '0.061 s', '2.31 s', 'identical'],
           ['pysequitur on PyPy', 'Python', '0.24 s', '1.17 s', 'identical'],
           ['scikit-sequitur, compiled', 'Python', '0.079 s', '3.05 s', 'same size'],
           ['scikit-sequitur', 'Python', '0.093 s', '3.59 s', 'same size'],
           ['Port by Ravi Annaswamy, 2013', 'Python', 'crashes', 'crashes', '']],
          'Medians of three runs on an Apple M4 Pro, each in a fresh process, timing only the building of the grammar. '
          'The 1.6 MB input is Python standard library source, kept to ASCII so that every implementation reads the '
          'same symbols.',
          highlight=(5, 6), bad={(4, 4), (9, 2), (9, 3)}, text=(1, 4))
    table('table_agents', 'Right answers out of three, with the average cost and time of an answer',
          ['Question', 'Model', 'Text in question', 'Cost, time', "pysequitur's tools", 'Cost, time'],
          [['Revelation', 'Haiku 4.5', '0 of 3', '$0.21, 6 min', '3 of 3', '$0.03, 17 s'],
           ['Revelation', 'Opus 5.5', '3 of 3', '$2.50, 9.5 min', '3 of 3', '$0.10, 24 s'],
           ['Duplicated code', 'Haiku 4.5', '0 of 3', '$0.07, 43 s', '3 of 3', '$0.04, 34 s'],
           ['Duplicated code', 'Opus 5.5', '3 of 3', '$0.06, 10 s', '3 of 3', '$0.07, 16 s'],
           ['Copied passages', 'Haiku 4.5', '3 of 3', '$0.11, 91 s', '3 of 3', '$0.07, 71 s'],
           ['Copied passages', 'Opus 5.5', '3 of 3', '$0.10, 16 s', '3 of 3', '$0.07, 17 s']],
          'Claude Code agents with their own tools switched off. Without pysequitur the text was in the question; '
          'with it, only the tools could read the files. The share copied was 5 to 14 points off in Haiku\'s answers '
          'without tools, and exact with them.',
          highlight=(1,), bad={(0, 2), (2, 2)}, text=(1,))


if __name__ == '__main__':
    OUT.mkdir(exist_ok=True)
    tables()
    screenshots()
    print(sorted(p.name for p in OUT.iterdir()))
