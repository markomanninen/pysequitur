"""The MCP server, called through an MCP client in-process and over stdio."""
import asyncio
import logging
import os
import shutil
import sys
import tempfile
import unittest

try:
    from mcp import Client, StdioServerParameters
    from pysequitur.mcp_server import create_server
except ImportError:  # the mcp extra is not installed
    Client = None

from .support import ROOT, sample

# the server logs every failed call; the failures here are deliberate
logging.getLogger('mcp').setLevel(logging.WARNING)

TOOLS = {'analyze', 'list_repeats', 'get_rule', 'find_phrase', 'shared_phrases', 'repetition_profile',
         'get_grammar', 'render_visualization', 'list_analyses'}


@unittest.skipIf(Client is None, 'the mcp extra is not installed')
class TestTools(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        shutil.copy(os.path.join(ROOT, 'iamsam.txt'), self.root)
        self.server = create_server([self.root])

    def call(self, tool, **arguments):
        async def go():
            async with Client(self.server) as client:
                return await client.call_tool(tool, arguments)
        return asyncio.run(go())

    def ok(self, tool, **arguments):
        result = self.call(tool, **arguments)
        self.assertFalse(result.is_error, result.content)
        return result.structured_content

    def error(self, tool, **arguments):
        result = self.call(tool, **arguments)
        self.assertTrue(result.is_error)
        return result.content[0].text

    def test_tools_are_described(self):
        async def go():
            async with Client(self.server) as client:
                return (await client.list_tools()).tools, client.instructions
        tools, instructions = asyncio.run(go())
        self.assertEqual({t.name for t in tools}, TOOLS)
        for tool in tools:
            with self.subTest(tool=tool.name):
                self.assertTrue(tool.description)
                self.assertTrue(tool.output_schema)
                # only the report tool writes anything
                self.assertEqual(tool.annotations.read_only_hint, tool.name != 'render_visualization')
        self.assertIn('analysis_id', instructions)

    def test_render_visualization(self):
        analysis = self.ok('analyze', path='iamsam.txt')['analysis_id']
        report = self.ok('render_visualization', analysis_id=analysis)
        self.assertEqual(report['path'], os.path.join(os.path.realpath(self.root), analysis + '.html'))
        with open(report['path'], encoding='utf-8') as f:
            page = f.read()
        self.assertEqual(len(page.encode('utf-8')), report['bytes'])
        self.assertIn('data-mode="report"', page)
        self.assertIn('exists', self.error('render_visualization', analysis_id=analysis))
        self.ok('render_visualization', analysis_id=analysis, overwrite=True)
        self.ok('render_visualization', analysis_id=analysis, path='nested.html')
        self.assertIn('outside', self.error('render_visualization', analysis_id=analysis, path='/tmp/x.html'))
        self.assertIn('ending in .html', self.error('render_visualization', analysis_id=analysis, path='x.py'))
        self.assertIn('No such directory', self.error('render_visualization', analysis_id=analysis, path='no/x.html'))

    def test_text_and_follow_up_queries(self):
        text = sample('iamsam.txt')
        summary = self.ok('analyze', text=text, name='Green Eggs')
        analysis = summary['analysis_id']
        self.assertTrue(analysis.startswith('green-eggs-'))
        self.assertEqual(summary['documents'][0]['chars'], len(text))
        self.assertTrue(summary['top_repeats'] and summary['longest_repeats'])

        listing = self.ok('list_repeats', analysis_id=analysis, contains='eggs', sort_by='length')
        self.assertTrue(all('eggs' in r['text'] for r in listing['repeats']))
        rule = listing['repeats'][0]['rule']

        detail = self.ok('get_rule', analysis_id=analysis, rule=rule, max_positions=3)
        self.assertEqual(''.join(p['text'] for p in detail['body']), detail['text'])
        self.assertEqual(len(detail['positions']), min(3, detail['occurrences']))

        found = self.ok('find_phrase', analysis_id=analysis, phrase='Sam-I-am')
        self.assertEqual(found['occurrences'], text.count('Sam-I-am'))

        profile = self.ok('repetition_profile', analysis_id=analysis, segments=5)
        self.assertEqual(len(profile['segments']), 5)

        grammar = self.call('get_grammar', analysis_id=analysis, max_rules=3)
        self.assertTrue(grammar.content[0].text.startswith('S → '))

        held = self.ok('list_analyses')
        self.assertEqual([a['analysis_id'] for a in held['result']], [analysis])

    def test_files_under_the_root(self):
        summary = self.ok('analyze', path='iamsam.txt', tokens='line')
        self.assertEqual(summary['tokenization'], 'line')
        self.assertEqual(summary['documents'][0]['name'], 'iamsam.txt')
        self.ok('analyze', path=os.path.join(self.root, 'iamsam.txt'))
        message = self.error('analyze', path=os.path.join(ROOT, 'README.md'))
        self.assertIn('outside the directories', message)
        self.assertIn('outside the directories', self.error('analyze', path='../' * 12 + 'etc/hosts'))
        self.assertIn('No such file', self.error('analyze', path='missing.txt'))
        # relative paths are looked up in every root
        other = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, other)
        shutil.copy(os.path.join(ROOT, 'genesis1.txt'), other)
        self.server = create_server([self.root, other])
        self.assertEqual(self.ok('analyze', path='genesis1.txt')['documents'][0]['chars'],
                         len(sample('genesis1.txt')))

    def test_documents_and_shared_phrases(self):
        documents = [{'name': 'genesis', 'text': sample('genesis1.txt')},
                     {'path': 'iamsam.txt'},
                     {'name': 'mix', 'text': sample('iamsam.txt')[:900] + sample('genesis1.txt')[:700]}]
        summary = self.ok('analyze', documents=documents)
        self.assertEqual([d['name'] for d in summary['documents']], ['genesis', 'iamsam.txt', 'mix'])
        shared = self.ok('shared_phrases', analysis_id=summary['analysis_id'], min_chars=30)
        self.assertTrue(shared['phrases'])
        self.assertTrue(all(len(p['documents']) >= 2 for p in shared['phrases']))
        self.assertEqual(len(shared['overlaps']), 6)

    def test_errors(self):
        self.assertIn('Unknown analysis_id', self.error('list_repeats', analysis_id='nope'))
        self.assertIn('exactly one', self.error('analyze', text='abc', path='iamsam.txt'))
        self.assertIn('exactly one', self.error('analyze'))
        self.assertIn('exactly one of text or path', self.error('analyze', documents=[{'name': 'x'}]))
        analysis = self.ok('analyze', text='abcabcabc')['analysis_id']
        self.assertIn('no rule', self.error('get_rule', analysis_id=analysis, rule=999))
        self.assertIn('two or more documents', self.error('shared_phrases', analysis_id=analysis))
        self.assertIn('no document', self.error('repetition_profile', analysis_id=analysis, document='x'))
        self.error('analyze', text='abc', tokens='sentence')

    def test_size_limit(self):
        self.server = create_server([self.root], max_chars=100)
        self.assertIn('at most 100', self.error('analyze', text='x' * 101))

    def test_least_recently_used_analysis_is_dropped(self):
        self.server = create_server([self.root], max_analyses=2)
        first = self.ok('analyze', text='abab')['analysis_id']
        second = self.ok('analyze', text='cdcd')['analysis_id']
        self.ok('list_repeats', analysis_id=first)  # first is now the most recently used
        self.ok('analyze', text='efef')
        self.ok('list_repeats', analysis_id=first)
        self.assertIn('Unknown analysis_id', self.error('list_repeats', analysis_id=second))


@unittest.skipIf(Client is None, 'the mcp extra is not installed')
class TestStdio(unittest.TestCase):

    def test_analyze_over_stdio(self):
        server = StdioServerParameters(command=sys.executable, args=['-m', 'pysequitur.mcp_server', '--root', ROOT],
                                       cwd=ROOT)

        async def go():
            async with Client(server) as client:
                summary = await client.call_tool('analyze', {'path': 'genesis1.txt'})
                grammar = await client.call_tool('get_grammar', {
                    'analysis_id': summary.structured_content['analysis_id'], 'max_rules': 2})
                return summary, grammar
        summary, grammar = asyncio.run(go())
        self.assertFalse(summary.is_error, summary.content)
        self.assertEqual(summary.structured_content['documents'][0]['name'], 'genesis1.txt')
        self.assertIn('R1', grammar.content[0].text)


if __name__ == '__main__':
    unittest.main()
