"""
The compiled engine (pysequitur_rs, built from rust/) against core.Grammar:
Sequencer3 must give the same grammar with either backend, down to the rule
numbers and the type of every element, and fall back to Python for tokens
the compiled engine does not take. Skipped when pysequitur_rs is not built.
"""
import os
import pickle
import random
import subprocess
import sys
import unittest

from pysequitur import Sequencer3
from pysequitur import backend
from pysequitur.core import Grammar
from pysequitur.sequiturpython.symbol import RuleIndex

from .support import CYCLIC_INPUT, ROOT, SAMPLES, sample

HAVE_RUST = backend.available()


def both(tokens):
    return (Sequencer3(tokens, backend='python').get(),
            Sequencer3(tokens, backend='rust').get())


class SameGrammar(unittest.TestCase):

    def assertSameGrammar(self, expected, actual, msg=None):
        """Equal rule for rule, and every element of the same type."""
        self.assertEqual(expected, actual, msg)
        for i, (a, b) in enumerate(zip(expected, actual)):
            self.assertEqual([type(x) for x in a], [type(x) for x in b], 'rule %d: %s' % (i, msg))

    def check(self, tokens, msg=None):
        expected, actual = both(tokens)
        self.assertSameGrammar(expected, actual, msg)
        return actual


def random_ints(rnd, n, k):
    return [rnd.randrange(k) for _ in range(n)]


def repetitive(rnd, n, k):
    """Words from a small vocabulary with a few random letters between them."""
    vocab = [random_ints(rnd, rnd.randint(2, 9), k) for _ in range(rnd.randint(1, 30))]
    out = []
    while len(out) < n:
        out.extend(random_ints(rnd, rnd.randint(0, 3), k))
        out.extend(rnd.choice(vocab))
    return out[:n]


def thue_morse(n):
    return [bin(i).count('1') % 2 for i in range(n)]


def fibonacci_word(n):
    a, b = [0], [0, 1]
    while len(b) < n:
        a, b = b, b + a
    return b[:n]


@unittest.skipUnless(HAVE_RUST, 'pysequitur_rs is not built (see rust/)')
class TestSameGrammar(SameGrammar):

    def test_backends(self):
        self.assertEqual(type(Sequencer3('ab', backend='rust').g), backend.RustGrammar)
        self.assertEqual(type(Sequencer3('ab', backend='python').g), Grammar)
        with self.assertRaises(ValueError):
            Sequencer3('ab', backend='c++')

    def test_edge_cases(self):
        cases = [[], '', [0], 'a', [7, 7], 'aa', 'aaa', 'aaaa', 'ab', 'abab', 'ababa', 'aabaab',
                 'abbbabcbb', 'abcabdabcabd', CYCLIC_INPUT, [-1, -1, -1], [0, 1, 0, 1, 0]]
        for tokens in cases:
            with self.subTest(tokens=tokens):
                self.check(tokens)
        self.assertEqual(Sequencer3([], backend='rust').get(), [[]])
        self.assertEqual(Sequencer3(backend='rust').get(), [[]])

    def test_runs_and_overlapping_digrams(self):
        for n in range(1, 300):
            for unit in ('a', 'ab', 'aab', 'abb', 'abc'):
                tokens = (unit * n)[:n + 2]
                with self.subTest(tokens=tokens):
                    self.check(tokens)
        for tokens in ('a' * 10000, 'ab' * 5000, 'a' * 99 + 'b' + 'a' * 99, [3] * 4097):
            self.check(tokens)

    def test_random_ints(self):
        rnd = random.Random(7)
        for k in (2, 3, 4, 5, 8, 16, 50, 100, 300, 1000):
            for _ in range(60):
                n = rnd.choice([rnd.randint(0, 50), rnd.randint(0, 600), rnd.randint(1000, 3000)])
                tokens = random_ints(rnd, n, k)
                with self.subTest(k=k, n=n):
                    self.check(tokens)

    def test_repetitive_ints(self):
        rnd = random.Random(8)
        for k in (2, 3, 26, 100, 300, 1000):
            for _ in range(40):
                n = rnd.randint(0, 8000)
                tokens = repetitive(rnd, n, k)
                # misread letters, as procrustes-sequitur's repairs try
                for i in rnd.sample(range(n), n // 20) if n else []:
                    tokens[i] = rnd.randrange(k)
                with self.subTest(k=k, n=n):
                    self.check(tokens)
        for tokens in (thue_morse(5000), fibonacci_word(5000)):
            self.check(tokens)

    def test_int_values(self):
        # beyond the lookup arrays, negative, and at the 64-bit limits
        rnd = random.Random(9)
        values = [0, 4095, 4096, -1, -4096, 2 ** 31, 2 ** 32 + 5, 2 ** 63 - 1, -2 ** 63, 10 ** 15]
        for _ in range(50):
            tokens = [rnd.choice(values) for _ in range(rnd.randint(0, 400))]
            self.check(tokens)
        self.check([v * 1000003 for v in repetitive(rnd, 3000, 40)])

    def test_strings(self):
        for name in SAMPLES:
            with self.subTest(sample=name):
                text = sample(name)
                self.check(text)
                self.check(list(text))
                self.check(text.split())
                self.check(text.splitlines(True))
        for text in ('ääöö ääöö ↵↵', 'ŝŝŝŝ', '日本語日本語日本', '😀😀a😀😀a', '\x00\x00\x00',
                     'a\U0010ffffa\U0010ffff', '\ud800\ud800\ud800'):
            with self.subTest(text=text):
                self.check(text)
                self.check(list(text))
        self.check(['', '', 'ab', '', 'ab', ''])

    def test_mixed_ints_and_strs(self):
        rnd = random.Random(10)
        alphabet = [0, 1, 2, '0', '1', 'a', 'ab', 'b', 300, '300']
        for _ in range(100):
            self.check([rnd.choice(alphabet) for _ in range(rnd.randint(0, 500))])

    def test_rule_references(self):
        rules = Sequencer3('abcabdabcabd', backend='rust').get()
        R = RuleIndex
        self.assertEqual(rules, [[R(1), R(1)], [R(2), 'c', R(2), 'd'], ['a', 'b']])
        self.assertIs(type(rules[0][0]), RuleIndex)
        self.assertIs(type(rules[1][1]), str)
        rules = Sequencer3([1, 2, 1, 2], backend='rust').get()
        self.assertEqual(rules, [[R(1), R(1)], [1, 2]])
        self.assertNotEqual(rules[0][0], 1)
        self.assertIs(type(rules[1][0]), int)

    def test_input_types(self):
        tokens = repetitive(random.Random(11), 500, 10)
        expected = Sequencer3(tokens, backend='python').get()
        for given in (tokens, tuple(tokens), iter(tokens), (t for t in tokens), range(0)):
            with self.subTest(type=type(given).__name__):
                if isinstance(given, range):
                    self.assertSameGrammar(Sequencer3(given, backend='rust').get(), [[]])
                else:
                    self.assertSameGrammar(expected, Sequencer3(given, backend='rust').get())
        self.check(range(100))
        self.check(b'abcabcabc')

    def test_streaming(self):
        rnd = random.Random(12)
        for _ in range(20):
            tokens = repetitive(rnd, rnd.randint(0, 2000), 20)
            expected = Sequencer3(tokens, backend='python').get()
            s = Sequencer3(backend='rust')
            for t in tokens:
                s.stream(t)
            self.assertSameGrammar(expected, s.get())
            # get() in between, then more input
            s = Sequencer3(tokens[:len(tokens) // 2], backend='rust')
            s.get()
            for t in tokens[len(tokens) // 2:]:
                s.stream(t)
            self.assertSameGrammar(expected, s.get())
            g = backend.RustGrammar()
            for i in range(0, len(tokens), 97):
                g.feed(tokens[i:i + 97])
            self.assertEqual(len(g), len(tokens))
            self.assertSameGrammar(expected, g.rules())

    def test_api_on_rust(self):
        text = sample('peaseporridge.txt')
        p, r = Sequencer3(text, backend='python'), Sequencer3(text, backend='rust')
        self.assertEqual(str(p), str(r))
        self.assertEqual(p.resolve(), r.resolve())
        self.assertEqual(p.resolve(False), r.resolve(False))
        self.assertEqual(p.grammar_sequence(True), r.grammar_sequence(True))
        self.assertEqual(p.grammar_rules(True, True), r.grammar_rules(True, True))
        self.assertEqual(len(p.g), len(r.g))

    def test_pickle(self):
        s = Sequencer3('abcabdabcabd' * 3, backend='rust')
        copy = pickle.loads(pickle.dumps(s))
        self.assertEqual(copy.get(), s.get())
        self.assertEqual(copy.g.backend, 'rust')

    def test_grammar_size(self):
        rnd = random.Random(13)
        for _ in range(30):
            tokens = repetitive(rnd, rnd.randint(0, 3000), 50)
            expected = sum(len(r) for r in Sequencer3(tokens, backend='python').get())
            self.assertEqual(backend.grammar_size(tokens), expected)
            self.assertEqual(backend.grammar_size(tokens, backend='python'), expected)
            self.assertEqual(backend.grammar_size(tokens + [1.5]),
                             sum(len(r) for r in Sequencer3(tokens + [1.5], backend='python').get()))


@unittest.skipUnless(HAVE_RUST, 'pysequitur_rs is not built (see rust/)')
class TestFallBack(SameGrammar):
    """Tokens the compiled engine does not take send the grammar to core.Grammar."""

    OTHERS = [1.5, 2.0, True, False, None, (1, 2), frozenset([1]), 2 ** 64, -2 ** 63 - 1,
              RuleIndex(1), b'x', object()]

    def test_other_tokens(self):
        rnd = random.Random(14)
        for other in self.OTHERS:
            for _ in range(5):
                tokens = repetitive(rnd, rnd.randint(1, 300), 5)
                tokens.insert(rnd.randrange(len(tokens) + 1), other)
                with self.subTest(other=other):
                    s = Sequencer3(tokens, backend='rust')
                    self.assertEqual(s.g.backend, 'python')
                    expected = Sequencer3(tokens, backend='python').get()
                    self.assertSameGrammar(expected, s.get())

    def test_equal_tokens_of_other_types(self):
        # Python merges 1, 1.0 and True; the grammar keeps the objects it saw
        for tokens in ([1, 2, 1.0, 2], [1, True, 1, True], [1.0, 2, 1, 2], [0, False, 0, False, 0]):
            with self.subTest(tokens=tokens):
                self.check(tokens)

    def test_subclasses(self):
        class Str(str):
            pass

        class Int(int):
            pass
        for tokens in ([Int(1), 2, 1, 2], ['a', Str('a'), 'a', 'a'], [RuleIndex(1), 1, RuleIndex(1), 1]):
            with self.subTest(tokens=tokens):
                self.check(tokens)

    def test_mid_stream(self):
        rnd = random.Random(15)
        for _ in range(20):
            tokens = repetitive(rnd, rnd.randint(0, 1000), 8)
            more = repetitive(rnd, rnd.randint(0, 1000), 8)
            s = Sequencer3(tokens, backend='rust')
            s.get()
            for t in [None] + more:
                s.stream(t)
            self.assertEqual(s.g.backend, 'python')
            self.assertSameGrammar(Sequencer3(tokens + [None] + more, backend='python').get(), s.get())
            g = backend.RustGrammar(tokens)
            g.feed(more + [1.5] + tokens)
            self.assertSameGrammar(Grammar(tokens + more + [1.5] + tokens).rules(), g.rules())
            self.assertEqual(len(g), len(tokens) * 2 + len(more) + 1)

    def test_unhashable(self):
        for b in ('python', 'rust'):
            with self.assertRaises(TypeError):
                Sequencer3([1, 2, [3]], backend=b)


class TestChoice(unittest.TestCase):
    """PYSEQUITUR_BACKEND, read when pysequitur is imported."""

    def default(self, value):
        env = dict(os.environ, PYSEQUITUR_BACKEND=value)
        code = 'import pysequitur.backend as b, pysequitur as p; print(b.DEFAULT, type(p.Sequencer3("ab").g).__name__)'
        done = subprocess.run([sys.executable, '-c', code], cwd=ROOT, env=env, capture_output=True, text=True)
        return done.stdout.split(), done.stderr

    def test_python(self):
        self.assertEqual(self.default('python')[0], ['python', 'Grammar'])

    def test_auto(self):
        expected = ['rust', 'RustGrammar'] if HAVE_RUST else ['python', 'Grammar']
        self.assertEqual(self.default('auto')[0], expected)
        self.assertEqual(self.default('')[0], expected)

    def test_rust(self):
        out, err = self.default('rust')
        if HAVE_RUST:
            self.assertEqual(out, ['rust', 'RustGrammar'])
        else:
            self.assertIn('ImportError', err)

    def test_unknown_value_warns(self):
        out, err = self.default('fortran')
        self.assertIn('PYSEQUITUR_BACKEND', err)
        self.assertEqual(out[0], 'rust' if HAVE_RUST else 'python')


if __name__ == '__main__':
    unittest.main()
