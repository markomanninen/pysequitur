"""
The visualizer: its data must describe the analysis exactly, the page must
embed it safely, and the page's own position logic, run in Node, must agree
with the Python analysis.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from pysequitur.analysis import Analysis
from pysequitur.viz import _template, main, make_server, model, render_html

from .support import ROOT, sample

EMOJI_TEXT = 'ok 🎉 ok 🎉 fine. ok 🎉 ok 🎉 fine! 𝔘𝔫𝔦𝔠𝔬𝔡𝔢 ok 🎉'


def utf16_slice(text, start, end):
    return text.encode('utf-16-le')[2 * start:2 * end].decode('utf-16-le')


def analyses():
    genesis, iamsam = sample('genesis1.txt'), sample('iamsam.txt')
    return {
        'iamsam words': Analysis.from_text(iamsam, tokens='word'),
        'genesis characters': Analysis.from_text(genesis, tokens='char'),
        'lines': Analysis.from_text(iamsam, tokens='line'),
        'documents': Analysis([('genesis', genesis), ('iamsam', iamsam), ('mix', iamsam[:600] + genesis[:900])]),
        'emoji': Analysis.from_text(EMOJI_TEXT, tokens='char'),
    }


def expand(data, r):
    return ''.join(x if isinstance(x, str) else expand(data, x) for x in data['rules']['body'][r])


class TestModel(unittest.TestCase):

    def test_pieces_tile_every_document(self):
        for name, a in analyses().items():
            data = model(a)
            root = data['root']
            for d, doc in enumerate(data['docs']):
                with self.subTest(analysis=name, document=doc['name']):
                    pieces = [root[i:i + 4] for i in range(0, len(root), 4) if root[i] == d]
                    self.assertEqual(pieces[0][1], 0)
                    self.assertEqual(pieces[-1][2], doc['chars'])
                    for left, right in zip(pieces, pieces[1:]):
                        self.assertEqual(left[2], right[1])
                    text = a.documents[d].text
                    self.assertEqual(''.join(utf16_slice(text, p[1], p[2]) for p in pieces), text)
                    for p in pieces:
                        if p[3]:
                            self.assertEqual(utf16_slice(text, p[1], p[2]), expand(data, p[3]))

    def test_rule_bodies_spell_the_rules(self):
        for name, a in analyses().items():
            data = model(a)
            for r in range(1, len(a.rules)):
                with self.subTest(analysis=name, rule=r):
                    text = expand(data, r)
                    self.assertEqual(text, a.text(r))
                    self.assertEqual(data['rules']['chars'][r], len(text.encode('utf-16-le')) // 2)

    def test_documents_and_truncation(self):
        a = analyses()['documents']
        data = model(a, max_shown=1000)
        self.assertEqual([d['name'] for d in data['docs']], ['genesis', 'iamsam', 'mix'])
        self.assertTrue(all(len(d['text']) <= 1000 for d in data['docs']))
        self.assertEqual(len(data['rules']['docs']), len(a.rules))
        self.assertTrue(data['shared']['phrases'])
        self.assertIsNone(model(analyses()['lines'])['shared'])


class TestPage(unittest.TestCase):

    def test_hostile_text_is_embedded_safely(self):
        text = 'a </script><script>alert(1)</script> __MODEL__ __TITLE__ <!-- b ' * 3
        page = render_html(Analysis.from_text(text, name='<b>title</b>'))
        self.assertEqual(page.count('</script>'), _template().count('</script>'))
        self.assertNotIn('<b>title</b>', page)
        embedded = re.search(r'<script type="application/json" id="model">(.*?)</script>', page, re.S).group(1)
        data = json.loads(embedded)
        self.assertEqual(data['docs'][0]['text'], text)
        self.assertEqual(data['title'], '<b>title</b>')

    def test_modes(self):
        self.assertIn('data-mode="report"', render_html(Analysis.from_text('abab')))
        app = render_html(None, mode='app')
        self.assertIn('data-mode="app"', app)
        self.assertIn('id="model">null</script>', app)

    def test_report_from_the_command_line(self):
        out = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, out)
        path = os.path.join(out, 'report.html')
        self.assertEqual(main([os.path.join(ROOT, 'iamsam.txt'), '-o', path]), 0)
        with open(path, encoding='utf-8') as f:
            self.assertIn('"tokenization":"word"', f.read())


@unittest.skipIf(shutil.which('node') is None, 'node is not installed')
class TestPageLogicInNode(unittest.TestCase):

    RUNNER = r'''
const fs = require('fs');
new Function(fs.readFileSync(process.argv[2], 'utf8'))();
const V = globalThis.SequiturViz, M = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const C = V.prepare(M), rules = [];
for (let r = 1; r < C.n; r++) rules.push(r);
const positions = V.positionsOf(C, rules), out = { positions: {}, texts: {}, chains: [], profiles: [] };
for (const r of rules) {
  out.positions[r] = Array.from(positions.get(r), V.decode);
  out.texts[r] = V.expand(C, r);
}
out.chains = JSON.parse(process.argv[4]).map(p => V.chainAt(C, p[0], p[1]));
out.profiles = M.docs.map((doc, d) => V.profile(C, d, 7).map(b => b.value));
console.log(JSON.stringify(out));
'''

    def run_core(self, data, samples):
        work = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, work)
        core = re.search(r'<script id="core">(.*?)</script>', _template(), re.S).group(1)
        paths = {}
        for name, content in (('core.js', core), ('model.json', json.dumps(data)), ('run.js', self.RUNNER)):
            paths[name] = os.path.join(work, name)
            with open(paths[name], 'w', encoding='utf-8') as f:
                f.write(content)
        result = subprocess.run(['node', paths['run.js'], paths['core.js'], paths['model.json'], json.dumps(samples)],
                                capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_page_logic_matches_the_analysis(self):
        for name, a in analyses().items():
            data = model(a)
            astral = name == 'emoji'
            samples = [(d, o) for d, doc in enumerate(a.documents) for o in range(0, len(doc.text), 7)]
            out = self.run_core(data, [] if astral else samples)
            with self.subTest(analysis=name):
                for r in range(1, len(a.rules)):
                    expected = []
                    for offset in a.positions(r):
                        d, start, _ = a._span(r, offset)
                        expected.append([d, len(a.documents[d].text[:start].encode('utf-16-le')) // 2])
                    self.assertEqual(out['positions'][str(r)], expected, 'rule %d' % r)
                    self.assertEqual(out['texts'][str(r)], a.text(r))
                if not astral:
                    for (d, o), chain in zip(samples, out['chains']):
                        self.assertEqual(chain[-1] if chain else 0, a._innermost(d, o, o + 1), 'offset %d' % o)
                    for d, doc in enumerate(a.documents):
                        expected = [s['repeated_fraction'] for s in a.profile(doc.name, segments=7)['segments']]
                        self.assertEqual([round(v, 4) for v in out['profiles'][d]], expected)


class TestServer(unittest.TestCase):

    def setUp(self):
        self.server = make_server(Analysis.from_text(sample('iamsam.txt')), port=0, max_chars=50000)
        self.url = 'http://127.0.0.1:%d' % self.server.server_address[1]
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, path, body=None, host=None):
        headers = {'Content-Type': 'application/json'}
        if host:
            headers['Host'] = host
        data = None if body is None else json.dumps(body).encode('utf-8')
        try:
            with urllib.request.urlopen(urllib.request.Request(self.url + path, data, headers), timeout=30) as r:
                return r.status, r.read().decode('utf-8')
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode('utf-8')

    def test_page(self):
        status, page = self.request('/')
        self.assertEqual(status, 200)
        self.assertIn('data-mode="app"', page)
        self.assertIn('"tokenization":"word"', page)

    def test_analyze(self):
        status, body = self.request('/api/analyze', {
            'documents': [{'name': 'a', 'text': 'abcabc abcabc'}, {'name': 'b', 'text': 'abcabc xyz'}],
            'tokens': 'char'})
        self.assertEqual(status, 200, body)
        data = json.loads(body)
        self.assertEqual([d['name'] for d in data['docs']], ['a', 'b'])
        self.assertEqual(data['tokenization'], 'char')

    def test_refusals(self):
        self.assertEqual(self.request('/', host='attacker.example')[0], 403)
        self.assertEqual(self.request('/api/analyze', {'documents': []}, host='attacker.example:80')[0], 403)
        self.assertEqual(self.request('/missing')[0], 404)
        self.assertEqual(self.request('/api/analyze', {'documents': []})[0], 400)
        self.assertEqual(self.request('/api/analyze', {'documents': [{'name': 'x'}]})[0], 400)
        self.assertEqual(self.request('/api/analyze', {'documents': [{'text': 'abc'}], 'tokens': 'sentence'})[0], 400)
        status, body = self.request('/api/analyze', {'documents': [{'text': 'x' * 50001}]})
        self.assertEqual(status, 400)
        self.assertIn('at most 50000', body)


if __name__ == '__main__':
    unittest.main()
