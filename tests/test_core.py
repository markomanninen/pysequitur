"""
core.Grammar against the sequiturpython port it was restructured from: both
implement the same algorithm, so they must build identical grammars.
"""
import random
import unittest

from pysequitur.core import Grammar
from pysequitur.sequiturpython.grammar import Grammar as PortGrammar
from pysequitur.sequiturpython.symbol import RuleIndex

from .support import SAMPLES, sample
from .test_properties import random_strings


def port_rules(tokens):
    g = PortGrammar()
    g.train_string(tokens)
    return g.get_grammar()


class TestSameGrammarAsPort(unittest.TestCase):

    def test_sample_files(self):
        for name in SAMPLES:
            with self.subTest(sample=name):
                text = sample(name)
                self.assertEqual(Grammar(text).rules(), port_rules(text))

    def test_random_inputs(self):
        for text in random_strings(seed=4, count=200, max_length=600):
            with self.subTest(text=text):
                self.assertEqual(Grammar(text).rules(), port_rules(text))

    def test_word_tokens(self):
        words = sample('iamsam.txt').split()
        self.assertEqual(Grammar(words).rules(), port_rules(words))


class TestGrammar(unittest.TestCase):

    def test_incremental_feeding(self):
        text = sample('genesis1.txt')
        g = Grammar()
        for i in range(0, len(text), 97):
            g.feed(text[i:i + 97])
        self.assertEqual(len(g), len(text))
        self.assertEqual(g.rules(), Grammar(text).rules())

    def test_rule_references(self):
        rules = Grammar('abcabdabcabd').rules()
        self.assertEqual(rules, [[1, 1], [2, 'c', 2, 'd'], ['a', 'b']])
        self.assertIsInstance(rules[0][0], RuleIndex)
        self.assertNotIsInstance(rules[1][1], RuleIndex)

    def test_long_runs_stay_shallow(self):
        # the engine recurses while it restores the grammar properties; check
        # that a long run does not come near the interpreter's recursion limit
        rules = Grammar('a' * 100000).rules()
        self.assertLess(len(rules), 40)


if __name__ == '__main__':
    unittest.main()
