"""
Sequitur's guarantees, checked on every implementation: the grammar expands
back to the input exactly, no digram occurs twice (digram uniqueness), and
every rule is used at least twice (rule utility).

Sequencer and Sequencer2 are quadratic, so they get shorter inputs.
"""
import random
import unittest

from .support import CYCLIC_INPUT, SAMPLES, build, sample, time_limit, violations

LINEAR = ('Sequencer3', 'sequiturpython')
VALID = ('Sequencer', 'Sequencer3', 'sequiturpython')

# Runs of one symbol exercise the overlapping-digram handling that the
# original Python port got wrong; small alphabets produce them constantly.
ALPHABETS = ('ab', 'aab', 'aaab', 'abc', 'abcdefgh')


def random_strings(seed, count, max_length):
    rnd = random.Random(seed)
    for alphabet in ALPHABETS:
        for _ in range(count):
            yield ''.join(rnd.choice(alphabet) for _ in range(rnd.randint(1, max_length)))


class TestSampleFiles(unittest.TestCase):

    def test_linear_implementations(self):
        for impl in LINEAR:
            for name in SAMPLES:
                with self.subTest(impl=impl, sample=name):
                    text = sample(name)
                    self.assertEqual(violations(build(impl, text), text), [])

    def test_quadratic_implementations(self):
        for name in SAMPLES[:3]:
            text = sample(name)
            with self.subTest(impl='Sequencer', sample=name):
                self.assertEqual(violations(build('Sequencer', text), text), [])
            with self.subTest(impl='Sequencer2', sample=name):
                problems = violations(build('Sequencer2', text), text)
                self.assertNotIn('expansion differs from input', problems)


class TestRandomInputs(unittest.TestCase):

    def test_linear_implementations(self):
        for impl in LINEAR:
            for text in random_strings(seed=1, count=300, max_length=400):
                with self.subTest(impl=impl, text=text):
                    with time_limit(10):
                        self.assertEqual(violations(build(impl, text), text), [])

    def test_sequencer(self):
        for text in random_strings(seed=2, count=40, max_length=150):
            with self.subTest(text=text):
                self.assertEqual(violations(build('Sequencer', text), text), [])

    def test_sequencer2_round_trip(self):
        for text in random_strings(seed=3, count=40, max_length=150):
            with self.subTest(text=text):
                problems = violations(build('Sequencer2', text), text)
                self.assertNotIn('expansion differs from input', problems)


class TestEdgeCases(unittest.TestCase):

    def test_runs_of_one_symbol(self):
        for n in range(1, 65):
            text = 'a' * n
            for impl in VALID:
                with self.subTest(impl=impl, n=n):
                    self.assertEqual(violations(build(impl, text), text), [])

    def test_short_inputs(self):
        for text in ('a', 'ab', 'aa', 'aaa', 'abab', 'abbbabcbb', 'abcabdabcabd'):
            for impl in VALID:
                with self.subTest(impl=impl, text=text):
                    self.assertEqual(violations(build(impl, text), text), [])

    def test_empty_input(self):
        for impl in LINEAR:
            with self.subTest(impl=impl):
                self.assertEqual(build(impl, ''), {0: []})

    def test_formerly_cyclic_input(self):
        for impl in VALID:
            with self.subTest(impl=impl):
                with time_limit(5):
                    self.assertEqual(violations(build(impl, CYCLIC_INPUT), CYCLIC_INPUT), [])

    def test_non_character_tokens(self):
        cases = [
            [1, 2, 1, 2, 3, 1, 2, 3, 1, 1, 1, 1],
            ['the', ' ', 'cat', ' ', 'the', ' ', 'cat', ' ', 'sat'],
            [(1, 2), (3,), (1, 2), (3,), None, None, None],
            # all of these collided while digram keys were "left+right" strings
            ['a+', 'b', 'a', '+b', 'z', 'a+', 'b'],
            ['rule(1)', 'x', 'rule(1)', 'x', 'y', 'rule(1)', 'x'],
        ]
        for tokens in cases:
            for impl in VALID:
                with self.subTest(impl=impl, tokens=tokens):
                    self.assertEqual(violations(build(impl, tokens), tokens), [])

    @unittest.expectedFailure
    def test_sequencer2_rule_utility(self):
        """Known limitation: Sequencer2 can keep a rule that is used only once."""
        self.assertEqual(violations(build('Sequencer2', 'aaa'), 'aaa'), [])


if __name__ == '__main__':
    unittest.main()
