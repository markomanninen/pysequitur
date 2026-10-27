# -*- coding: utf-8 -*-
# file: analysis.py
"""
What repeats in a text, where, and how the repeats nest.

An Analysis is the Sequitur grammar of one or more documents, indexed for
queries: its rules are the repeated phrases, with their sizes, counts,
positions and nesting. The MCP server and the visualizer are built on it.

    from pysequitur.analysis import Analysis

    a = Analysis.from_text(open('samples/iamsam.txt').read(), tokens='word')
    a.summary()['repeated_fraction']
    a.repeats(sort_by='coverage', limit=5)
    a.rule(3)
    a.find('green eggs')

Tokens are characters, words (whitespace runs and punctuation marks are
tokens of their own) or lines. They always tile the text, so every
occurrence of a rule is an exact character span of a document.
"""
from __future__ import annotations

import bisect
import json
import re
from collections import Counter
from typing import Dict, List, Optional

try:  # pydantic, which the MCP server uses, needs this TypedDict before Python 3.12
    from typing_extensions import TypedDict
except ImportError:  # pragma: no cover
    from typing import TypedDict

from .core import Grammar
from .sequiturpython.symbol import RuleIndex

TOKENIZATIONS = ('char', 'word', 'line')
SORT_KEYS = ('coverage', 'length', 'occurrences', 'depth')

_WORD = re.compile(r'\w+|\s+|[^\w\s]')
# phrase lookups classify at most this many occurrences by the rule they sit in
_CLASSIFY_LIMIT = 2000
# documents are compared word for word only up to this many characters in all
_OVERLAP_LIMIT = 2000000


class Position(TypedDict):
    document: str
    offset: int  # character offset in the document
    length: int  # characters
    line: int  # 1-based
    column: int  # 1-based
    context: str  # the occurrence in «» with surrounding text; empty when not requested


class Repeat(TypedDict):
    rule: int
    text: str
    truncated: bool  # text was cut to the requested length
    chars: int
    tokens: int
    occurrences: int  # times the phrase occurs in the documents, without overlapping
    coverage: int  # chars × occurrences
    depth: int  # nesting levels of rules inside the phrase, 1 = none
    first: Position
    documents: Dict[str, int]  # occurrences per document


class DocumentSummary(TypedDict):
    name: str
    chars: int
    tokens: int
    lines: int
    repeated_fraction: float  # share of the document's tokens inside some repeat


class Summary(TypedDict):
    analysis_id: str
    tokenization: str
    ignore_case: bool
    documents: List[DocumentSummary]
    tokens: int
    distinct_tokens: int
    rules: int  # repeated phrases found
    grammar_symbols: int  # size of the grammar, in symbols
    compression_ratio: float  # grammar symbols per input token
    repeated_fraction: float  # share of all tokens inside some repeat
    max_depth: int
    top_repeats: List[Repeat]  # most text covered (chars × occurrences), at least 12 characters
    longest_repeats: List[Repeat]


class RepeatList(TypedDict):
    analysis_id: str
    total: int  # repeats that pass the filters
    offset: int
    repeats: List[Repeat]


class Part(TypedDict):
    text: str
    rule: Optional[int]  # None for literal text


class RuleRef(TypedDict):
    rule: int
    text: str
    occurrences: int


class RuleDetail(TypedDict):
    analysis_id: str
    rule: int
    text: str
    truncated: bool
    chars: int
    tokens: int
    occurrences: int  # times the phrase occurs in the documents, without overlapping
    parsed_as_rule: int  # of those, the ones the grammar parses as this rule rather than inside others
    references: int  # uses of the rule in the grammar
    depth: int
    body: List[Part]
    parents: List[RuleRef]  # rules that use this one
    children: List[RuleRef]  # rules this one uses
    documents: Dict[str, int]
    positions: List[Position]


class PhraseMatches(TypedDict):
    analysis_id: str
    phrase: str
    occurrences: int  # non-overlapping occurrences in the documents
    positions: List[Position]
    exact_rule: Optional[int]  # rule whose text is exactly the phrase
    rules: List[RuleRef]  # innermost repeats that contain occurrences
    outside_repeats: int  # occurrences that are not inside any repeat
    classified: int  # occurrences checked for the two fields above


class SharedPassage(TypedDict):
    document: str
    offset: int  # character offset in the document
    line: int
    chars: int
    text: str
    truncated: bool  # a long passage is shown as its start … its end
    also_in: List[str]  # the other documents that have it


class Overlap(TypedDict):
    document: str
    other: str
    shared_fraction: float  # share of the document also found word for word in other, in passages of min_chars or more


class SharedPhrases(TypedDict):
    analysis_id: str
    min_chars: int
    compared: bool  # False when the documents are too large to compare in memory
    passages: List[SharedPassage]  # longest first
    overlaps: List[Overlap]


class Segment(TypedDict):
    start: int
    end: int
    line: int
    repeated_fraction: float


class Profile(TypedDict):
    analysis_id: str
    document: str
    segments: List[Segment]


def tokenize(text, mode='word'):
    """
    Split text into tokens that join back to it exactly. Returns the tokens and
    the character offset of each, or None for offsets when tokens are characters.
    """
    if mode == 'char':
        return list(text), None
    if mode == 'word':
        tokens = []
        starts = []
        for m in _WORD.finditer(text):
            tokens.append(m.group())
            starts.append(m.start())
        return tokens, starts
    if mode == 'line':
        tokens = text.splitlines(True)
        starts = []
        offset = 0
        for token in tokens:
            starts.append(offset)
            offset += len(token)
        return tokens, starts
    raise ValueError('tokens must be one of %s, not %r' % (', '.join(TOKENIZATIONS), mode))


class Document(object):
    """An input text and where its tokens sit in the combined token stream."""

    def __init__(self, name, text, first, count, starts):
        self.name = name
        self.text = text
        self.first = first  # stream index of the document's first token
        self.count = count  # number of tokens
        self._starts = starts  # character offset of each token; None for characters
        self._line_starts = None

    def char_offset(self, token):
        """Character offset of the document's token; count gives the end of the text."""
        if self._starts is None:
            return token
        return self._starts[token] if token < self.count else len(self.text)

    def token_at(self, offset):
        """Index of the token that contains a character offset."""
        if self._starts is None:
            return offset
        return bisect.bisect_right(self._starts, offset) - 1

    def line_column(self, offset):
        if self._line_starts is None:
            self._line_starts = [0] + [m.end() for m in re.finditer('\n', self.text)]
        line = bisect.bisect_right(self._line_starts, offset)
        return line, offset - self._line_starts[line - 1] + 1

    @property
    def lines(self):
        self.line_column(0)
        return len(self._line_starts)


class _Boundary(object):
    """Separator between documents. Each is unique, so no repeat spans two documents."""
    __slots__ = ()


class Analysis(object):

    def __init__(self, documents, tokens='word', ignore_case=False):
        """documents: (name, text) pairs."""
        if tokens not in TOKENIZATIONS:
            raise ValueError('tokens must be one of %s, not %r' % (', '.join(TOKENIZATIONS), tokens))
        self.id = ''
        self.tokenization = tokens
        self.ignore_case = ignore_case
        self.documents = []
        grammar = Grammar()
        distinct = set()
        names = Counter()
        position = 0
        for i, (name, text) in enumerate(documents):
            names[name] += 1
            if names[name] > 1:
                name = '%s (%d)' % (name, names[name])
            if i:
                grammar.stream(_Boundary())
                position += 1
            values, starts = tokenize(text, tokens)
            if ignore_case:
                values = [v.lower() for v in values]
            distinct.update(values)
            self.documents.append(Document(name, text, position, len(values), starts))
            grammar.feed(values)
            position += len(values)
        self.distinct_tokens = len(distinct)
        self._folded = [d.text.lower() for d in self.documents] if ignore_case else [d.text for d in self.documents]
        self.rules = grammar.rules()
        self._firsts = [d.first for d in self.documents]
        self._parents = None
        self._root_offsets = None
        self._measure()

    @classmethod
    def from_text(cls, text, name='text', **options):
        return cls([(name, text)], **options)

    @classmethod
    def from_files(cls, paths, **options):
        documents = []
        for path in paths:
            with open(path, encoding='utf-8', errors='replace') as f:
                documents.append((path, f.read()))
        return cls(documents, **options)

    # Indexes

    def _measure(self):
        rules = self.rules
        n = len(rules)
        length = [0] * n
        depth = [0] * n
        # post-order walk: every rule after the rules it uses
        state = bytearray(n)
        postorder = []
        stack = [0]
        while stack:
            r = stack[-1]
            if not state[r]:
                state[r] = 1
                stack.extend(x for x in rules[r] if type(x) is RuleIndex and not state[x])
                continue
            stack.pop()
            if state[r] == 1:
                state[r] = 2
                size = deepest = 0
                for x in rules[r]:
                    if type(x) is RuleIndex:
                        size += length[x]
                        if depth[x] > deepest:
                            deepest = depth[x]
                    else:
                        size += 1
                length[r] = size
                depth[r] = deepest + 1
                postorder.append(r)
        self.length = length
        self.depth = depth
        self._topological = postorder[::-1]  # every rule before the rules it uses

        occurrences = [0] * n
        occurrences[0] = 1
        for r in self._topological:
            k = occurrences[r]
            for x in rules[r]:
                if type(x) is RuleIndex:
                    occurrences[x] += k
        self.occurrences = occurrences

        # first occurrence of every rule: a text-order walk that enters each rule once
        first = [-1] * n
        first[0] = 0
        stack = [[0, 0, 0]]  # rule, next body index, stream offset of that symbol
        while stack:
            frame = stack[-1]
            r, i, offset = frame
            body = rules[r]
            if i == len(body):
                stack.pop()
                continue
            x = body[i]
            frame[1] = i + 1
            if type(x) is RuleIndex:
                frame[2] = offset + length[x]
                if first[x] < 0:
                    first[x] = offset
                    stack.append([x, 0, offset])
            else:
                frame[2] = offset + 1
        self.first = first

        chars = [0] * n
        chars[0] = sum(len(d.text) for d in self.documents)
        for r in range(1, n):
            _, start, end = self._span(r, first[r])
            chars[r] = end - start
        self.chars = chars

        # root symbols that are tokens are the text outside every repeat
        outside = [0] * len(self.documents)
        per_document = [None] * n
        multiple = len(self.documents) > 1
        offset = 0
        for x in rules[0]:
            if type(x) is RuleIndex:
                if multiple:
                    d = self._document_of(offset)
                    counts = per_document[x]
                    if counts is None:
                        counts = per_document[x] = Counter()
                    counts[d] += 1
                offset += length[x]
            else:
                if type(x) is not _Boundary:
                    outside[self._document_of(offset)] += 1
                offset += 1
        self._outside = outside
        if multiple:
            for r in self._topological:
                if r == 0:
                    continue
                counts = per_document[r]
                for x in rules[r]:
                    if type(x) is RuleIndex:
                        child = per_document[x]
                        if child is None:
                            child = per_document[x] = Counter()
                        child.update(counts)
        self._per_document = per_document if multiple else None

    def _document_of(self, token):
        return bisect.bisect_right(self._firsts, token) - 1

    def _span(self, rule, token):
        """Document index and character span of a rule (or token, for None) at a stream offset."""
        d = self._document_of(token)
        doc = self.documents[d]
        local = token - doc.first
        size = 1 if rule is None else self.length[rule]
        return d, doc.char_offset(local), doc.char_offset(local + size)

    def parents(self):
        """For every rule, the rules that use it and how many times."""
        if self._parents is None:
            parents = [Counter() for _ in self.rules]
            for r, body in enumerate(self.rules):
                for x in body:
                    if type(x) is RuleIndex:
                        parents[x][r] += 1
            self._parents = parents
        return self._parents

    def _root_prefix(self):
        """Stream offset of every symbol of the main rule, for bisecting."""
        if self._root_offsets is None:
            offsets = []
            offset = 0
            for x in self.rules[0]:
                offsets.append(offset)
                offset += self.length[x] if type(x) is RuleIndex else 1
            self._root_offsets = offsets
        return self._root_offsets

    # Rules

    def _check_rule(self, rule):
        if not isinstance(rule, int) or not 1 <= rule < len(self.rules):
            raise KeyError('no rule %r: rules are numbered 1 to %d' % (rule, len(self.rules) - 1))

    def text(self, rule):
        """The phrase a rule stands for, as it first occurs."""
        d, start, end = self._span(rule, self.first[rule])
        return self.documents[d].text[start:end]

    def text_counts(self, rule):
        """Times a rule's phrase occurs in each document, without overlapping, which may be more
        often than the grammar parses it as this rule: Sequitur's parse is greedy, so an occurrence
        can be split between neighbouring rules."""
        phrase = self.text(rule)
        if self.ignore_case:
            phrase = phrase.lower()
        counts = {}
        for doc, text in zip(self.documents, self._folded):
            k = text.count(phrase)
            if k:
                counts[doc.name] = k
        return counts

    def text_positions(self, rule, limit=None):
        """(document index, start, end) of a rule's phrase in the documents, without overlapping."""
        phrase = self.text(rule)
        if self.ignore_case:
            phrase = phrase.lower()
        found = []
        for d, text in enumerate(self._folded):
            i = text.find(phrase)
            while i >= 0 and (limit is None or len(found) < limit):
                found.append((d, i, i + len(phrase)))
                i = text.find(phrase, i + len(phrase))
        return found

    def document_counts(self, rule):
        if self._per_document is None:
            return {self.documents[0].name: self.occurrences[rule]}
        counts = self._per_document[rule] or {}
        return dict((self.documents[d].name, k) for d, k in sorted(counts.items()))

    def positions(self, rule, limit=None):
        """Stream offsets of a rule's occurrences, in text order."""
        rules = self.rules
        length = self.length
        parents = self.parents()
        # only rules that contain the target, directly or not, need to be entered
        inside = set()
        todo = [rule]
        while todo:
            for p in parents[todo.pop()]:
                if p not in inside:
                    inside.add(p)
                    todo.append(p)
        found = []
        stack = [[0, 0, 0]]
        while stack:
            frame = stack[-1]
            r, i, offset = frame
            body = rules[r]
            if i == len(body):
                stack.pop()
                continue
            x = body[i]
            frame[1] = i + 1
            if type(x) is RuleIndex:
                frame[2] = offset + length[x]
                x = int(x)  # a RuleIndex equals only RuleIndexes; rule and inside hold ints
                if x == rule:
                    found.append(offset)
                    if limit is not None and len(found) >= limit:
                        break
                elif x in inside:
                    stack.append([x, 0, offset])
            else:
                frame[2] = offset + 1
        return found

    def _parts(self, rule, start, limit=None):
        """A rule's body as literal text and rule references, starting at a stream offset."""
        parts = []
        offset = start
        for x in self.rules[rule]:
            if limit is not None and len(parts) >= limit:
                break
            if type(x) is RuleIndex:
                parts.append((x, None))
                offset += self.length[x]
                continue
            if type(x) is not _Boundary:
                d, a, b = self._span(None, offset)
                text = self.documents[d].text[a:b]
                if parts and parts[-1][0] is None and parts[-1][1][0] == d:
                    parts[-1] = (None, (d, parts[-1][1][1] + text))
                else:
                    parts.append((None, (d, text)))
            else:
                parts.append(('|', None))
            offset += 1
        return parts

    # Queries

    def _cut(self, text, limit):
        if limit is not None and len(text) > limit:
            return text[:limit] + '…', True
        return text, False

    def _ends(self, text, limit):
        """Like _cut, but keeps both ends of a long passage."""
        if limit is not None and len(text) > limit:
            half = max(1, limit // 2)
            return text[:half] + ' … ' + text[-half:], True
        return text, False

    def _context(self, d, start, end, width):
        text = self.documents[d].text
        inner = text[start:end]
        if len(inner) > 2 * width + 1:
            inner = inner[:width] + '…' + inner[-width:]
        return '%s%s«%s»%s%s' % ('…' if start > width else '', text[max(0, start - width):start], inner,
                                 text[end:end + width], '…' if end + width < len(text) else '')

    def _position(self, d, start, end, context=0):
        doc = self.documents[d]
        line, column = doc.line_column(start)
        return Position(document=doc.name, offset=start, length=end - start, line=line, column=column,
                        context=self._context(d, start, end, context) if context else '')

    def _ref(self, rule, max_text):
        return RuleRef(rule=rule, text=self._cut(self.text(rule), max_text)[0],
                       occurrences=sum(self.text_counts(rule).values()))

    def repeat(self, rule, max_text=200, counts=None):
        text, truncated = self._cut(self.text(rule), max_text)
        counts = counts or self.text_counts(rule)
        occurrences = sum(counts.values())
        d, start, end = self.text_positions(rule, limit=1)[0]
        return Repeat(rule=rule, text=text, truncated=truncated, chars=self.chars[rule],
                      tokens=self.length[rule], occurrences=occurrences,
                      coverage=self.chars[rule] * occurrences, depth=self.depth[rule],
                      first=self._position(d, start, end), documents=counts)

    def _document_index(self, name):
        for d, doc in enumerate(self.documents):
            if doc.name == name:
                return d
        raise KeyError('no document %r; documents: %s' % (name, ', '.join(d.name for d in self.documents)))

    def repeats(self, sort_by='coverage', min_chars=1, min_occurrences=2, contains=None,
                document=None, limit=20, offset=0, max_text=200):
        """Repeated phrases that pass the filters, best first."""
        if sort_by not in SORT_KEYS:
            raise ValueError('sort_by must be one of %s, not %r' % (', '.join(SORT_KEYS), sort_by))
        d = None if document is None else self._document_index(document)
        if contains is not None and self.ignore_case:
            contains = contains.lower()
        chars, occurrences, depth = self.chars, self.occurrences, self.depth
        selected = []
        for r in range(1, len(self.rules)):
            if occurrences[r] < min_occurrences or chars[r] < min_chars:
                continue
            if d is not None and self._per_document is not None and d not in (self._per_document[r] or ()):
                continue
            if contains is not None:
                text = self.text(r)
                if contains not in (text.lower() if self.ignore_case else text):
                    continue
            selected.append(r)
        key = {
            'coverage': lambda r: (-chars[r] * occurrences[r], -chars[r], r),
            'length': lambda r: (-chars[r], -occurrences[r], r),
            'occurrences': lambda r: (-occurrences[r], -chars[r], r),
            'depth': lambda r: (-depth[r], -chars[r], r),
        }[sort_by]
        selected.sort(key=key)
        # The grammar's counts can be lower than the counts in the text, never higher. Rank
        # the leading candidates by their counts in the text, which are what is reported.
        counts = {}
        if sort_by in ('coverage', 'occurrences'):
            head = selected[:max(4 * (offset + limit), 100)]
            for r in head:
                counts[r] = self.text_counts(r)
            total = lambda r: sum(counts[r].values())  # noqa: E731
            head.sort(key=(lambda r: (-chars[r] * total(r), -chars[r], r)) if sort_by == 'coverage'
                      else (lambda r: (-total(r), -chars[r], r)))
            selected[:len(head)] = head
        page = selected[offset:offset + limit]
        return RepeatList(analysis_id=self.id, total=len(selected), offset=offset,
                          repeats=[self.repeat(r, max_text, counts.get(r)) for r in page])

    def rule(self, rule, max_positions=10, context=40, max_text=500):
        """Everything about one rule: its phrase, structure, relatives and positions."""
        self._check_rule(rule)
        text, truncated = self._cut(self.text(rule), max_text)
        body = []
        for x, value in self._parts(rule, self.first[rule]):
            if x is None:
                body.append(Part(text=self._cut(value[1], max_text)[0], rule=None))
            else:
                body.append(Part(text=self._cut(self.text(x), max_text)[0], rule=int(x)))
        parents = self.parents()[rule]
        children = []
        for x in self.rules[rule]:
            if type(x) is RuleIndex and int(x) not in [c['rule'] for c in children]:
                children.append(self._ref(int(x), 80))
        positions = [self._position(d, start, end, context)
                     for d, start, end in self.text_positions(rule, max_positions)]
        counts = self.text_counts(rule)
        return RuleDetail(analysis_id=self.id, rule=rule, text=text, truncated=truncated,
                          chars=self.chars[rule], tokens=self.length[rule],
                          occurrences=sum(counts.values()), parsed_as_rule=self.occurrences[rule],
                          references=sum(parents.values()),
                          depth=self.depth[rule], body=body,
                          parents=[self._ref(p, 80) for p in sorted(parents, key=lambda p: -self.occurrences[p])[:20]
                                   if p != 0],
                          children=children, documents=counts, positions=positions)

    def _innermost(self, d, start, end):
        """The innermost rule whose occurrence contains a character span; 0 when none does."""
        doc = self.documents[d]
        g0 = doc.first + doc.token_at(start)
        g1 = doc.first + doc.token_at(max(start, end - 1))
        offsets = self._root_prefix()
        i = bisect.bisect_right(offsets, g0) - 1
        x = self.rules[0][i]
        if type(x) is not RuleIndex or g1 >= offsets[i] + self.length[x]:
            return 0
        rule, pos = int(x), offsets[i]  # rule numbers as ints, like the rest of the results
        while True:
            for x in self.rules[rule]:
                size = self.length[x] if type(x) is RuleIndex else 1
                if pos <= g0 and g1 < pos + size:
                    if type(x) is not RuleIndex:
                        return rule
                    rule = int(x)
                    break
                if pos + size > g0:
                    return rule  # the span straddles symbols of this rule
                pos += size
            else:
                return rule

    def find(self, phrase, max_positions=10, context=40, max_text=200):
        """
        Where a phrase occurs, and which repeats contain it. Whitespace in the phrase matches
        any whitespace in the text, so a phrase typed on one line finds text broken over two.
        """
        if not phrase:
            raise ValueError('phrase is empty')
        parts = re.split(r'(\s+)', phrase)
        pattern = re.compile(''.join(r'\s+' if part.isspace() else re.escape(part) for part in parts if part),
                             re.IGNORECASE if self.ignore_case else 0)
        count = classified = outside = 0
        positions = []
        inner = Counter()
        exact = None
        for d, doc in enumerate(self.documents):
            for m in pattern.finditer(doc.text):
                count += 1
                if len(positions) < max_positions:
                    positions.append(self._position(d, m.start(), m.end(), context))
                if classified < _CLASSIFY_LIMIT:
                    classified += 1
                    r = self._innermost(d, m.start(), m.end())
                    if r:
                        inner[r] += 1
                        if exact is None and self.chars[r] == m.end() - m.start():
                            exact = int(r)
                    else:
                        outside += 1
        return PhraseMatches(analysis_id=self.id, phrase=phrase, occurrences=count, positions=positions,
                             exact_rule=exact, rules=[self._ref(int(r), max_text) for r, _ in inner.most_common(10)],
                             outside_repeats=outside, classified=classified)

    def shared(self, min_documents=2, min_chars=10, limit=20, max_text=300, document=None):
        """
        The passages of at least min_chars characters that two or more documents have word for
        word, longest first, and for each pair of documents the share of one that also appears
        in the other.

        This compares the texts directly, with hashed passages of min_chars characters, rather
        than the grammar: a long shared passage is often split over several rules, and phrases
        of it can recur elsewhere.
        """
        if len(self.documents) < 2:
            raise ValueError('shared passages need an analysis of two or more documents')
        only = None if document is None else self._document_index(document)
        compared = self._compare(min_chars)
        if compared is None:
            return SharedPhrases(analysis_id=self.id, min_chars=min_chars, compared=False, passages=[], overlaps=[])
        spans, overlaps = compared
        passages = []
        for d, start, end, others in sorted(spans, key=lambda span: (span[1] - span[2], span[0], span[1])):
            if (only is not None and d != only) or bin(others).count('1') + 1 < min_documents:
                continue
            text, truncated = self._ends(self.documents[d].text[start:end], max_text)
            passages.append(SharedPassage(
                document=self.documents[d].name, offset=start, line=self.documents[d].line_column(start)[0],
                chars=end - start, text=text, truncated=truncated,
                also_in=[o.name for b, o in enumerate(self.documents) if others >> b & 1]))
            if len(passages) >= limit:
                break
        return SharedPhrases(analysis_id=self.id, min_chars=min_chars, compared=True, passages=passages,
                             overlaps=overlaps)

    def _compare(self, min_chars):
        """
        The stretches of each document made of passages of min_chars characters that some
        other document also has, as (document, start, end, bit set of those documents), and
        for each ordered pair of documents the share of the first found in the second; None
        when the documents are too large to compare in memory.
        """
        texts = self._folded
        if sum(map(len, texts)) > _OVERLAP_LIMIT:
            return None
        n = max(1, min_chars)
        owners = {}  # hash of a passage of n characters -> bit set of the documents having it
        for i, text in enumerate(texts):
            bit = 1 << i
            for p in range(len(text) - n + 1):
                key = hash(text[p:p + n])
                owners[key] = owners.get(key, 0) | bit
        spans, overlaps = [], []
        for a, text in enumerate(texts):
            covered = [0] * len(texts)
            reached = [0] * len(texts)  # end of the covered stretch so far, per other document
            others = ~(1 << a)
            span = None
            for p in range(len(text) - n + 1):
                mask = owners[hash(text[p:p + n])] & others
                if not mask:
                    continue
                if span and p < span[2]:  # overlapping, not just touching: passages copied from
                    span[2] = p + n          # different places stay apart
                    span[3] |= mask
                else:
                    if span:
                        spans.append(tuple(span))
                    span = [a, p, p + n, mask]
                while mask:
                    low = mask & -mask
                    b = low.bit_length() - 1
                    mask ^= low
                    covered[b] += p + n - max(p, reached[b])
                    reached[b] = p + n
            if span:
                spans.append(tuple(span))
            for b, other in enumerate(self.documents):
                if a != b:
                    overlaps.append(Overlap(document=self.documents[a].name, other=other.name,
                                            shared_fraction=round(covered[b] / len(text), 4) if text else 0.0))
        return spans, overlaps

    def profile(self, document=None, segments=20):
        """How much of each stretch of a document is repeated material."""
        d = 0 if document is None else self._document_index(document)
        doc = self.documents[d]
        total = len(doc.text)
        segments = max(1, min(segments, total or 1))
        bounds = [total * k // segments for k in range(segments + 1)]
        repeated = [0] * segments
        offsets = self._root_prefix()
        root = self.rules[0]
        i = bisect.bisect_left(offsets, doc.first)
        end = doc.first + doc.count
        while i < len(root) and offsets[i] < end:
            x = root[i]
            if type(x) is RuleIndex:
                start = doc.char_offset(offsets[i] - doc.first)
                stop = doc.char_offset(offsets[i] - doc.first + self.length[x])
                k = max(0, bisect.bisect_right(bounds, start) - 1)
                while k < segments and bounds[k] < stop:
                    repeated[k] += min(stop, bounds[k + 1]) - max(start, bounds[k])
                    k += 1
            i += 1
        out = []
        for k in range(segments):
            width = bounds[k + 1] - bounds[k]
            out.append(Segment(start=bounds[k], end=bounds[k + 1], line=doc.line_column(bounds[k])[0],
                               repeated_fraction=round(repeated[k] / width, 4) if width else 0.0))
        return Profile(analysis_id=self.id, document=doc.name, segments=out)

    def grammar_text(self, max_rules=50, max_line=200):
        """The grammar as text: S is the main rule, R<n> the others, literal text in quotes."""
        lines = []
        for r in range(min(len(self.rules), max_rules + 1)):
            parts = []
            for x, value in self._parts(r, self.first[r], limit=max_line):
                if x is None:
                    parts.append(json.dumps(value[1], ensure_ascii=False))
                elif x == '|':
                    parts.append('|')
                else:
                    parts.append('R%d' % x)
            head = 'S →' if r == 0 else 'R%d ×%d →' % (r, self.occurrences[r])
            line = '%s %s' % (head, ' '.join(parts))
            lines.append(line if len(line) <= max_line else line[:max_line] + '…')
        if len(self.rules) > max_rules + 1:
            lines.append('… %d more rules' % (len(self.rules) - max_rules - 1))
        return '\n'.join(lines)

    def summary(self, top=5, min_chars=12):
        tokens = sum(d.count for d in self.documents)
        outside = sum(self._outside)
        symbols = sum(len(body) for body in self.rules) - (len(self.documents) - 1)
        docs = [DocumentSummary(name=d.name, chars=len(d.text), tokens=d.count, lines=d.lines,
                                repeated_fraction=round(1 - self._outside[i] / d.count, 4) if d.count else 0.0)
                for i, d in enumerate(self.documents)]
        return Summary(analysis_id=self.id, tokenization=self.tokenization, ignore_case=self.ignore_case,
                       documents=docs, tokens=tokens, distinct_tokens=self.distinct_tokens,
                       rules=len(self.rules) - 1, grammar_symbols=symbols,
                       compression_ratio=round(symbols / tokens, 4) if tokens else 0.0,
                       repeated_fraction=round(1 - outside / tokens, 4) if tokens else 0.0,
                       max_depth=max(self.depth[1:], default=0),
                       top_repeats=self.repeats(limit=top, min_chars=min_chars, max_text=120)['repeats'],
                       longest_repeats=self.repeats(sort_by='length', limit=top, max_text=120)['repeats'])
