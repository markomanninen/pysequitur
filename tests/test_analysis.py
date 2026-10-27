"""The analysis layer: positions must be exact spans, and counts must agree."""
import re
import unittest

from pysequitur.analysis import Analysis, tokenize
from pysequitur.sequiturpython.symbol import RuleIndex

from .support import sample


def occurrence_texts(a, rule):
    texts = []
    for offset in a.positions(rule):
        d, start, end = a._span(rule, offset)
        texts.append(a.documents[d].text[start:end])
    return texts


class TestTokenize(unittest.TestCase):

    def test_tokens_join_back(self):
        text = sample('iamsam.txt') + '\r\n  tabs\tand_unicode ääkköset!\n'
        for mode in ('char', 'word', 'line'):
            with self.subTest(mode=mode):
                tokens, starts = tokenize(text, mode)
                self.assertEqual(''.join(tokens), text)
                if starts is not None:
                    self.assertEqual([text[s:s + len(t)] for s, t in zip(starts, tokens)], tokens)

    def test_unknown_mode(self):
        with self.assertRaises(ValueError):
            tokenize('abc', 'sentence')


class TestSingleDocument(unittest.TestCase):

    def test_occurrences_are_exact_spans(self):
        for mode in ('char', 'word', 'line'):
            a = Analysis.from_text(sample('iamsam.txt'), tokens=mode)
            for rule in range(1, len(a.rules)):
                with self.subTest(mode=mode, rule=rule):
                    texts = occurrence_texts(a, rule)
                    self.assertEqual(len(texts), a.occurrences[rule])
                    self.assertGreaterEqual(len(texts), 2)
                    self.assertEqual(set(texts), {a.text(rule)})

    def test_positions_are_in_text_order(self):
        a = Analysis.from_text(sample('genesis1.txt'), tokens='char')
        for rule in range(1, len(a.rules)):
            offsets = a.positions(rule)
            self.assertEqual(offsets, sorted(offsets))
            self.assertEqual(a.positions(rule, limit=1), offsets[:1])

    def test_summary(self):
        text = sample('iamsam.txt')
        a = Analysis.from_text(text, name='iamsam', tokens='word')
        s = a.summary()
        self.assertEqual(s['tokens'], len(tokenize(text, 'word')[0]))
        self.assertEqual(s['rules'], len(a.rules) - 1)
        self.assertEqual(s['documents'][0]['name'], 'iamsam')
        self.assertEqual(s['documents'][0]['chars'], len(text))
        self.assertTrue(0 < s['repeated_fraction'] < 1)
        self.assertTrue(0 < s['compression_ratio'] < 1)
        self.assertGreater(s['max_depth'], 1)
        self.assertTrue(s['top_repeats'])
        first = s['top_repeats'][0]
        self.assertEqual(first['documents'], {'iamsam': first['occurrences']})

    def test_repeats_sorting_and_filters(self):
        a = Analysis.from_text(sample('iamsam.txt'), tokens='word')
        listing = a.repeats(sort_by='coverage', limit=50)
        coverage = [r['coverage'] for r in listing['repeats']]
        self.assertEqual(coverage, sorted(coverage, reverse=True))
        self.assertTrue(all(r['coverage'] == r['chars'] * r['occurrences'] for r in listing['repeats']))
        longest = a.repeats(sort_by='length', limit=1)['repeats'][0]
        self.assertEqual(longest['chars'], max(a.chars[1:]))
        filtered = a.repeats(min_chars=15, contains='eggs', limit=1000)
        self.assertTrue(filtered['repeats'])
        self.assertTrue(all(r['chars'] >= 15 and 'eggs' in r['text'] for r in filtered['repeats']))
        self.assertEqual(filtered['total'], len(filtered['repeats']))
        page = a.repeats(limit=5, offset=5)
        self.assertEqual(page['repeats'], a.repeats(limit=10)['repeats'][5:])

    def test_rule_detail(self):
        a = Analysis.from_text(sample('iamsam.txt'), tokens='word')
        for rule in range(1, len(a.rules)):
            detail = a.rule(rule, max_positions=3, max_text=10 ** 6)
            with self.subTest(rule=rule):
                self.assertEqual(''.join(p['text'] for p in detail['body']), detail['text'])
                self.assertEqual(detail['references'], sum(body.count(RuleIndex(rule)) for body in a.rules))
                self.assertEqual(len(detail['positions']), min(3, detail['occurrences']))
                for p in detail['positions']:
                    self.assertIn('«' + detail['text'][:5], p['context'])
        with self.assertRaises(KeyError):
            a.rule(0)
        with self.assertRaises(KeyError):
            a.rule(len(a.rules))

    def test_find(self):
        text = sample('iamsam.txt')
        a = Analysis.from_text(text, tokens='word')
        found = a.find('green eggs and ham')
        self.assertEqual(found['occurrences'], len(re.findall('green eggs and ham', text)))
        self.assertGreater(found['occurrences'], 1)
        for p in found['positions']:
            self.assertEqual(text[p['offset']:p['offset'] + p['length']], 'green eggs and ham')
            line = text.splitlines()[p['line'] - 1]
            self.assertEqual(line[p['column'] - 1:p['column'] - 1 + 5], 'green')
        self.assertTrue(found['rules'])
        self.assertTrue(all('green eggs and ham' in r['text'] for r in found['rules']))
        self.assertEqual(a.find('no such phrase anywhere')['occurrences'], 0)

    def test_find_exact_rule(self):
        a = Analysis.from_text(sample('iamsam.txt'), tokens='word')
        rule = a.repeats(sort_by='length', limit=1)['repeats'][0]['rule']
        self.assertEqual(a.find(a.text(rule))['exact_rule'], rule)

    def test_profile(self):
        text = sample('iamsam.txt')
        a = Analysis.from_text(text, tokens='word')
        segments = a.profile(segments=7)['segments']
        self.assertEqual(len(segments), 7)
        self.assertEqual(segments[0]['start'], 0)
        self.assertEqual(segments[-1]['end'], len(text))
        for left, right in zip(segments, segments[1:]):
            self.assertEqual(left['end'], right['start'])
        self.assertTrue(all(0 <= s['repeated_fraction'] <= 1 for s in segments))

    def test_grammar_text(self):
        a = Analysis.from_text('abcabdabcabd', tokens='char')
        self.assertEqual(a.grammar_text(), 'S → R1 R1\nR1 ×2 → R2 "c" R2 "d"\nR2 ×4 → "ab"')
        self.assertIn('more rules', Analysis.from_text(sample('iamsam.txt')).grammar_text(max_rules=3))

    def test_ignore_case(self):
        text = 'Green eggs. green EGGS. GREEN eggs. '
        a = Analysis.from_text(text, tokens='word', ignore_case=True)
        rule = a.repeats(sort_by='length', limit=1)['repeats'][0]['rule']
        texts = occurrence_texts(a, rule)
        self.assertEqual(len(texts), 3)
        self.assertEqual({t.lower() for t in texts}, {'green eggs. '})
        self.assertEqual(a.find('GREEN EGGS')['occurrences'], 3)

    def test_tiny_inputs(self):
        for text in ('', 'a', 'ab'):
            with self.subTest(text=text):
                a = Analysis.from_text(text, tokens='char')
                s = a.summary()
                self.assertEqual((s['tokens'], s['rules'], s['repeated_fraction']), (len(text), 0, 0.0))
                self.assertEqual(a.repeats()['total'], 0)
                self.assertTrue(a.profile()['segments'])

    def test_bad_arguments(self):
        with self.assertRaises(ValueError):
            Analysis.from_text('abc', tokens='sentence')
        a = Analysis.from_text('abcabc')
        with self.assertRaises(ValueError):
            a.repeats(sort_by='alphabet')
        with self.assertRaises(ValueError):
            a.shared()
        with self.assertRaises(KeyError):
            a.repeats(document='other')


class TestDocuments(unittest.TestCase):

    def setUp(self):
        genesis, iamsam = sample('genesis1.txt'), sample('iamsam.txt')
        self.docs = [('genesis', genesis), ('iamsam', iamsam), ('mix', iamsam[:900] + genesis[:700])]
        self.a = Analysis(self.docs, tokens='word')

    def test_counts_per_document(self):
        a = self.a
        for rule in range(1, len(a.rules)):
            counts = a.document_counts(rule)
            with self.subTest(rule=rule):
                self.assertEqual(sum(counts.values()), a.occurrences[rule])
                seen = {}
                for offset in a.positions(rule):
                    name = a.documents[a._document_of(offset)].name
                    seen[name] = seen.get(name, 0) + 1
                self.assertEqual(seen, counts)

    def test_no_repeat_crosses_documents(self):
        a = self.a
        for rule in range(1, len(a.rules)):
            self.assertEqual(set(occurrence_texts(a, rule)), {a.text(rule)})

    def test_shared_phrases(self):
        shared = self.a.shared(min_chars=20)
        self.assertTrue(shared['phrases'])
        texts = dict(self.docs)
        for phrase in shared['phrases']:
            self.assertGreaterEqual(len(phrase['documents']), 2)
            for name in phrase['documents']:
                self.assertIn(phrase['text'], texts[name])
        self.assertTrue(shared['overlaps_computed'])
        fractions = {(o['document'], o['other']): o['shared_fraction'] for o in shared['overlaps']}
        self.assertEqual(len(fractions), 6)
        self.assertTrue(all(0 <= f <= 1 for f in fractions.values()))
        # mix is the first 900 characters of iamsam followed by the first 700 of genesis
        mix = len(texts['mix'])
        self.assertAlmostEqual(fractions[('mix', 'iamsam')], 900 / mix, places=2)
        self.assertAlmostEqual(fractions[('mix', 'genesis')], 700 / mix, places=2)
        self.assertEqual(fractions[('genesis', 'iamsam')], 0)
        # genesis repeats passages of its opening, which mix has, so more than 700 characters count
        self.assertGreater(fractions[('genesis', 'mix')], 700 / len(texts['genesis']))

    def test_document_filter(self):
        listing = self.a.repeats(document='genesis', limit=1000)
        self.assertTrue(all('genesis' in r['documents'] for r in listing['repeats']))
        self.assertLess(listing['total'], self.a.repeats(limit=1)['total'])

    def test_duplicate_names(self):
        a = Analysis([('x', 'abab'), ('x', 'abab')], tokens='char')
        self.assertEqual([d.name for d in a.documents], ['x', 'x (2)'])

    def test_profile_and_summary_per_document(self):
        s = self.a.summary()
        self.assertEqual([d['name'] for d in s['documents']], ['genesis', 'iamsam', 'mix'])
        self.assertEqual(self.a.profile('mix', segments=3)['segments'][-1]['end'], len(self.docs[2][1]))


if __name__ == '__main__':
    unittest.main()
