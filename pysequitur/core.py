# -*- coding: utf-8 -*-
# file: core.py
"""
Linear-time Sequitur engine (Nevill-Manning & Witten, 1997).

This is the algorithm of the sequiturpython port and of the C++ reference
implementation, laid out for CPython speed: a single slotted symbol class,
digram keys built from the symbols' identities, and no per-symbol method
dispatch. It builds the same grammars as the corrected sequiturpython port.

Tokens can be any hashable values: characters, words, lines or numbers.

    g = Grammar('abcabdabcabd')
    g.rules()  # [[^1, ^1], [^2, 'c', ^2, 'd'], ['a', 'b']]
"""

from .sequiturpython.symbol import RuleIndex


class Symbol(object):
    """
    Node in a rule's circular doubly linked list. Terminals have rule None;
    nonterminals point to the rule they stand for; every rule's list starts
    and ends at its guard.
    """
    __slots__ = ('prev', 'next', 'value', 'rule', 'is_guard')

    def __init__(self, value, rule=None, is_guard=False):
        self.prev = None
        self.next = None
        # the token itself, or the Rule for nonterminals and guards; rules hash
        # by identity, so a digram key never confuses a token with a rule
        self.value = value
        self.rule = rule
        self.is_guard = is_guard


class Rule(object):
    __slots__ = ('guard', 'refs')


class Grammar(object):
    """Sequitur grammar built incrementally from a token stream."""

    def __init__(self, tokens=None):
        self.index = {}
        self.length = 0
        self.root = self._new_rule()
        if tokens is not None:
            self.feed(tokens)

    def __len__(self):
        """Number of tokens read so far."""
        return self.length

    def feed(self, tokens):
        stream = self.stream
        for token in tokens:
            stream(token)
        return self

    def stream(self, token):
        """Append one token to the input."""
        guard = self.root.guard
        self._insert_after(guard.prev, Symbol(token))
        self.length += 1
        if self.length > 1:
            self._check(guard.prev.prev)

    def rules(self):
        """
        Rules as lists, the main rule first and the others in order of first use.
        Nonterminals are RuleIndex values pointing into the returned list.
        """
        number = {self.root: 0}
        order = [self.root]
        out = []
        for rule in order:
            body = []
            s = rule.guard.next
            while not s.is_guard:
                if s.rule is None:
                    body.append(s.value)
                else:
                    i = number.get(s.rule)
                    if i is None:
                        i = number[s.rule] = len(order)
                        order.append(s.rule)
                    body.append(RuleIndex(i))
                s = s.next
            out.append(body)
        return out

    # The algorithm. Names follow the C++ reference and the sequiturpython port.

    def _new_rule(self):
        rule = Rule()
        guard = Symbol(rule, rule, True)
        guard.prev = guard.next = guard
        rule.guard = guard
        rule.refs = 0
        return rule

    def _join(self, left, right):
        """Link two symbols, removing the digram they used to start from the index."""
        old = left.next
        if old is not None:
            index = self.index
            if not (left.is_guard or old.is_guard):
                key = (left.value, old.value)
                if index.get(key) is left:
                    del index[key]
            # In a triple such as 'bbb' only the second digram is indexed. When
            # it is broken up, index the first so that it is not forgotten.
            rp = right.prev
            rn = right.next
            if rp is not None and rn is not None and right.value == rp.value and right.value == rn.value:
                index[(right.value, rn.value)] = right
            lp = left.prev
            if lp is not None and left.value == old.value and left.value == lp.value:
                index[(lp.value, left.value)] = lp
        left.next = right
        right.prev = left

    def _insert_after(self, left, symbol):
        self._join(symbol, left.next)
        self._join(left, symbol)

    def _delete(self, symbol):
        self._join(symbol.prev, symbol.next)
        following = symbol.next
        if not following.is_guard:
            key = (symbol.value, following.value)
            if self.index.get(key) is symbol:
                del self.index[key]
        if symbol.rule is not None:
            symbol.rule.refs -= 1

    def _reference(self, rule):
        rule.refs += 1
        return Symbol(rule, rule)

    def _copy(self, symbol):
        if symbol.rule is not None:
            symbol.rule.refs += 1
        return Symbol(symbol.value, symbol.rule)

    def _substitute(self, symbol, rule):
        """Replace the digram starting at symbol with a reference to rule."""
        prev = symbol.prev
        self._delete(prev.next)
        self._delete(prev.next)
        self._insert_after(prev, self._reference(rule))

    def _expand(self, symbol):
        """Inline the rule of a nonterminal that is its last reference."""
        left = symbol.prev
        right = symbol.next
        guard = symbol.rule.guard
        first = guard.next
        last = guard.prev
        key = (symbol.value, right.value)
        if self.index.get(key) is symbol:
            del self.index[key]
        self._join(left, first)
        self._join(last, right)
        self.index[(last.value, last.next.value)] = last

    def _check(self, symbol):
        """Index the digram starting at symbol, or deal with its earlier occurrence."""
        key = (symbol.value, symbol.next.value)
        match = self.index.get(key)
        if match is None:
            self.index[key] = symbol
        elif match.next is not symbol:  # overlapping occurrences such as 'aaa' stay
            self._process_match(symbol, match)

    def _propagate_change(self, symbol):
        """Check the digrams around a symbol after its neighbourhood changed."""
        following = symbol.next
        if symbol.is_guard or following.is_guard:
            if not (following.is_guard or following.next.is_guard):
                self._check(following)
            return
        key = (symbol.value, following.value)
        match = self.index.get(key)
        if match is None:
            self.index[key] = symbol
            if not (following.is_guard or following.next.is_guard):
                self._check(following)
        elif match.next is not symbol:
            self._process_match(symbol, match)

    def _process_match(self, symbol, match):
        """Enforce digram uniqueness: the digram at symbol already occurs at match."""
        if match.prev.is_guard and match.next.next.is_guard:
            # the earlier occurrence is a whole rule: reuse it
            rule = match.prev.rule
            self._substitute(symbol, rule)
            self._propagate_change(symbol.prev)
        else:
            rule = self._new_rule()
            self._insert_after(rule.guard.prev, self._copy(symbol))
            self._insert_after(rule.guard.prev, self._copy(symbol.next))
            self._substitute(match, rule)
            self._propagate_change(match.prev)
            # index the new rule's digram only after the first occurrence is
            # replaced, as the C++ reference does
            first = rule.guard.next
            self.index[(first.value, first.next.value)] = first
            self._substitute(symbol, rule)
            self._propagate_change(symbol.prev)
        # rule utility: a nested rule now used only once is inlined
        first = rule.guard.next
        if first.rule is not None and not first.is_guard and first.rule.refs == 1:
            self._expand(first)
