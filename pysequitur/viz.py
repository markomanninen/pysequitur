# -*- coding: utf-8 -*-
# file: viz.py
"""
Visualizer: an interactive page that shows what repeats in a text, where, and
how the repeats nest.

    pysequitur-viz samples/iamsam.txt                  # open the app in a browser
    pysequitur-viz a.txt b.txt --tokens line           # several documents
    pysequitur-viz samples/iamsam.txt -o iamsam.html   # write a self-contained report
    pysequitur-viz                                     # paste or open texts in the app

The app is one HTML page with no external resources. As a report, the data is
embedded in it; as an app, a local server analyses what is pasted or opened.
"""
import argparse
import json
import os
import re
import sys
import threading
import webbrowser
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .analysis import TOKENIZATIONS, Analysis, _Boundary
from .sequiturpython.symbol import RuleIndex

# documents longer than this are shown truncated in the text view; the charts cover all of them
MAX_SHOWN = 300000

_ASTRAL = re.compile('[\U00010000-\U0010FFFF]')
_PLACEHOLDER = re.compile('__(TITLE|MODE|MODEL)__')


def _utf16_offsets(text):
    """
    Code point offset -> UTF-16 offset, as JavaScript strings count; None when
    they are the same, which they are unless the text has astral characters.
    """
    if not _ASTRAL.search(text):
        return None
    offsets = [0]
    position = 0
    for ch in text:
        position += 2 if ord(ch) > 0xFFFF else 1
        offsets.append(position)
    return offsets


def model(analysis, title=None, max_shown=MAX_SHOWN):
    """The analysis as the visualizer's data. Offsets and lengths are in UTF-16 units."""
    maps = [_utf16_offsets(d.text) for d in analysis.documents]

    def utf16(d, offset):
        return offset if maps[d] is None else maps[d][offset]

    documents = []
    for d, doc in enumerate(analysis.documents):
        shown = doc.text[:max_shown]
        documents.append({'name': doc.name, 'chars': utf16(d, len(doc.text)), 'text': shown,
                          'lines': doc.lines})

    rules = analysis.rules
    n = len(rules)
    body = [[]]
    chars = [0] * n
    for r in range(1, n):
        d, start, end = analysis._span(r, analysis.first[r])
        chars[r] = utf16(d, end) - utf16(d, start)
        body.append([value[1] if x is None else int(x) for x, value in analysis._parts(r, analysis.first[r])])
    chars[0] = sum(doc['chars'] for doc in documents)

    # the main rule as pieces [document, start, end, rule], rule 0 for text outside repeats
    root = []
    offset = 0
    for x in rules[0]:
        if type(x) is RuleIndex:
            d, start, end = analysis._span(x, offset)
            root.extend((d, utf16(d, start), utf16(d, end), int(x)))
            offset += analysis.length[x]
            continue
        if type(x) is not _Boundary:
            d, start, end = analysis._span(None, offset)
            start, end = utf16(d, start), utf16(d, end)
            if root and root[-1] == 0 and root[-4] == d and root[-2] == start:
                root[-2] = end
            else:
                root.extend((d, start, end, 0))
        offset += 1

    data = {
        'version': 1,
        'title': title or ', '.join(d.name for d in analysis.documents),
        'tokenization': analysis.tokenization,
        'ignoreCase': analysis.ignore_case,
        'summary': analysis.summary(),
        'docs': documents,
        'rules': {'body': body, 'chars': chars, 'tokens': analysis.length, 'occ': analysis.occurrences,
                  'depth': analysis.depth},
        'root': root,
        'shared': None,
    }
    if len(analysis.documents) > 1:
        data['rules']['docs'] = [[] if counts is None else [x for d, k in sorted(counts.items()) for x in (d, k)]
                                 for counts in analysis._per_document]
        data['shared'] = analysis.shared(min_chars=20, limit=30)
    return data


def _template():
    from importlib.resources import files
    return files('pysequitur').joinpath('viz_app.html').read_text(encoding='utf-8')


def _json(data):
    # '<' escaped so that no text in the data can close the script element holding it
    return json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')


def render_html(analysis=None, title=None, mode='report', max_shown=MAX_SHOWN):
    """The visualizer page: a report with the analysis embedded, or the app (mode='app')."""
    data = None if analysis is None else model(analysis, title, max_shown)
    values = {
        'TITLE': escape(data['title'] if data else title or 'Sequitur'),
        'MODE': mode,
        'MODEL': _json(data),
    }
    return _PLACEHOLDER.sub(lambda m: values[m.group(1)], _template())


def write_html(analysis, path, title=None, max_shown=MAX_SHOWN):
    """Write a self-contained report; returns its size in bytes."""
    page = render_html(analysis, title=title, max_shown=max_shown).encode('utf-8')
    with open(path, 'wb') as f:
        f.write(page)
    return len(page)


def make_server(analysis=None, host='127.0.0.1', port=8765, max_chars=5000000, title=None):
    """The app's HTTP server, not yet started. Port 0 picks a free port."""
    page = render_html(analysis, title=title, mode='app').encode('utf-8')

    class Handler(BaseHTTPRequestHandler):
        server_version = 'pysequitur-viz'

        def log_message(self, format, *args):
            pass

        def _local(self):
            # the page talks to its own origin only; another Host header means a
            # rebound DNS name, so refuse it
            host = (self.headers.get('Host') or '').rsplit(':', 1)[0].strip('[]').lower()
            return host in ('127.0.0.1', 'localhost', '::1')

        def _send(self, code, body, content_type):
            self.send_response(code)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(body)

        def _error(self, code, message):
            self._send(code, json.dumps({'error': message}).encode('utf-8'), 'application/json')

        def do_GET(self):
            if not self._local():
                return self._error(403, 'forbidden host')
            if self.path.split('?')[0] in ('/', '/index.html'):
                return self._send(200, page, 'text/html; charset=utf-8')
            self._error(404, 'not found')

        def do_POST(self):
            if not self._local():
                return self._error(403, 'forbidden host')
            if self.path != '/api/analyze':
                return self._error(404, 'not found')
            length = int(self.headers.get('Content-Length') or 0)
            if length > 4 * max_chars + 65536:
                return self._error(413, 'the input is larger than this server accepts (--max-chars)')
            try:
                request = json.loads(self.rfile.read(length).decode('utf-8'))
                documents = []
                for i, doc in enumerate(request['documents']):
                    if not isinstance(doc.get('text'), str):
                        raise ValueError('document %d has no text' % (i + 1))
                    documents.append((doc.get('name') or 'document %d' % (i + 1), doc['text']))
                if not documents:
                    raise ValueError('no documents')
                size = sum(len(text) for _, text in documents)
                if size > max_chars:
                    raise ValueError('the input has %d characters; this server analyses at most %d (--max-chars)'
                                     % (size, max_chars))
                analysis = Analysis(documents, tokens=request.get('tokens', 'word'),
                                    ignore_case=bool(request.get('ignore_case')))
            except (KeyError, TypeError, ValueError, AttributeError) as e:
                return self._error(400, str(e.args[0]) if e.args else 'bad request')
            self._send(200, _json(model(analysis)).encode('utf-8'), 'application/json')

    return ThreadingHTTPServer((host, port), Handler)


def serve(analysis=None, host='127.0.0.1', port=8765, open_browser=True, max_chars=5000000, title=None):
    server = make_server(analysis, host, port, max_chars, title)
    url = 'http://%s:%d/' % (host, server.server_address[1])
    print('Sequitur visualizer at %s (Ctrl+C to stop)' % url)
    if open_browser:
        threading.Timer(0.3, webbrowser.open, [url]).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main(argv=None):
    parser = argparse.ArgumentParser(prog='pysequitur-viz', description='See what repeats in texts, and where.')
    parser.add_argument('files', nargs='*', help='text files to analyse; omit to paste or open texts in the app')
    parser.add_argument('-t', '--tokens', choices=TOKENIZATIONS, default='word',
                        help="'word' for prose, 'line' for code and logs, 'char' for text without spaces")
    parser.add_argument('-i', '--ignore-case', action='store_true')
    parser.add_argument('-o', '--output', metavar='HTML', help='write a self-contained report instead of serving')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--no-browser', action='store_true', help='do not open a browser')
    parser.add_argument('--max-chars', type=int, default=5000000, help='largest input the app analyses')
    args = parser.parse_args(argv)
    analysis = None
    if args.files:
        documents = []
        for path in args.files:
            with open(path, encoding='utf-8', errors='replace') as f:
                documents.append((os.path.basename(path), f.read()))
        analysis = Analysis(documents, tokens=args.tokens, ignore_case=args.ignore_case)
    title = ', '.join(os.path.basename(f) for f in args.files) or None
    if args.output:
        if analysis is None:
            parser.error('give the files to write a report of')
        size = write_html(analysis, args.output, title=title)
        print('Wrote %s (%d KB)' % (args.output, size // 1024))
        return 0
    serve(analysis, port=args.port, open_browser=not args.no_browser, max_chars=args.max_chars, title=title)
    return 0


if __name__ == '__main__':
    sys.exit(main())
