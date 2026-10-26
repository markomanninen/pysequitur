"""Public API behaviour: printing, resolving and streaming."""
import contextlib
import io
import os
import re
import unittest

from pysequitur import Sequencer, Sequencer2, Sequencer3, print_grammar
from pysequitur.sequiturpython.symbol import RuleIndex

from .support import ROOT, sample, time_limit, CYCLIC_INPUT


def printed(sequencer):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        print_grammar(sequencer)
    return out.getvalue()


class TestPrintGrammar(unittest.TestCase):

    def test_readme_example(self):
        with open(os.path.join(ROOT, 'README.md')) as f:
            readme = f.read()
        expected = re.search(r'should output:\s*<pre><code>\n(.*?)</code></pre>', readme, re.S).group(1)
        self.assertEqual(printed(Sequencer3(sample('peaseporridge.txt'))).strip(), expected.strip())

    def test_every_implementation_prints(self):
        # RuleIndex.__repr__ recursed forever on Python 3.8+, which broke this for all
        for cls in (Sequencer, Sequencer2, Sequencer3):
            with self.subTest(cls=cls.__name__):
                self.assertTrue(printed(cls('abcabdabcabd')).startswith('S → '))

    def test_rule_index_formatting(self):
        self.assertEqual(repr(RuleIndex(3)), '^3')
        self.assertEqual(str(RuleIndex(3)), '3')
        self.assertEqual('^%s' % RuleIndex(3), '^3')


class TestSequencer3(unittest.TestCase):

    def test_resolve_restores_input(self):
        for text in ('Hello World\nTesting\tTabs! Spaces_too.', 'a_b a_b', 'ääöö ääöö ↵↵'):
            with self.subTest(text=text):
                self.assertEqual(''.join(Sequencer3(text).resolve()), text)

    def test_resolve_after_more_input(self):
        s = Sequencer3('abab')
        self.assertEqual(''.join(s.resolve()), 'abab')
        for c in 'cdcd':
            s.stream(c)
        self.assertEqual(''.join(s.resolve()), 'ababcdcd')

    def test_str_and_print_terminate(self):
        with time_limit(5):
            s = Sequencer3(CYCLIC_INPUT)
            self.assertTrue(str(s))
            self.assertTrue(printed(s))

    def test_numeric_tokens(self):
        tokens = [1, 2, 1, 2, 3, 1, 2, 3]
        self.assertEqual(Sequencer3(tokens).resolve(), tokens)

    def test_empty(self):
        s = Sequencer3()
        self.assertEqual(s.resolve(), [])
        self.assertEqual(s.get(), [[]])


if __name__ == '__main__':
    unittest.main()
