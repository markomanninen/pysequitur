"""Helpers shared by the test modules: building grammars through each
implementation's public API, and checking the properties Sequitur guarantees."""
import contextlib
import os
import signal
from collections import Counter

from pysequitur import Sequencer, Sequencer2, Sequencer3
from pysequitur.core import Grammar as CoreGrammar
from pysequitur.sequiturpython.grammar import Grammar
from pysequitur.sequiturpython.symbol import RuleIndex

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES_DIR = os.path.join(ROOT, 'samples')
SAMPLES = ['peaseporridge.txt', 'genesis1.txt', 'iamsam.txt', 'revelation.txt']

# Fed to the original port before the fix, this input left the main rule as a
# cycle: stream() returned, but resolve() and print_grammar() never did.
CYCLIC_INPUT = 'ababbbbbaaaababbbabbbaaaaaaaababaaaaabbbbbbbbbbabbb'


def sample(name):
    with open(os.path.join(SAMPLES_DIR, name)) as f:
        return f.read()


class Ref(object):
    """Nonterminal in a normalised grammar, distinct from any terminal value."""
    __slots__ = ('key',)

    def __init__(self, key):
        self.key = key

    def __eq__(self, other):
        return isinstance(other, Ref) and other.key == self.key

    def __hash__(self):
        return hash((Ref, self.key))

    def __repr__(self):
        return 'Ref(%r)' % self.key


def _refs(symbols):
    return [Ref(int(x)) if isinstance(x, RuleIndex) else x for x in symbols]


def _from_lists(rules):
    """get() / get_grammar() format: rule 0 first, nonterminals as RuleIndex."""
    return {i: _refs(body) for i, body in enumerate(rules)}


def _from_sequencer(s):
    """Sequencer keeps every rule as a list of overlapping digrams."""
    g = {0: _refs(s.grammar_sequence()['S'])}
    for key, digrams in s.grammar_rules().items():
        g[int(key)] = _refs([digrams[0][0]] + [d[1] for d in digrams])
    return g


def _from_sequencer2(s):
    g = {0: _refs(s.grammar_sequence()['S'])}
    for key, body in s.grammar_rules().items():
        g[int(key)] = _refs(body)
    return g


def _build_grammar(tokens):
    g = Grammar()
    g.train_string(tokens)
    return _from_lists(g.get_grammar())


IMPLEMENTATIONS = {
    'Sequencer': lambda tokens: _from_sequencer(Sequencer(tokens)),
    'Sequencer2': lambda tokens: _from_sequencer2(Sequencer2(tokens)),
    'Sequencer3': lambda tokens: _from_lists(Sequencer3(tokens).get()),
    'core': lambda tokens: _from_lists(CoreGrammar(tokens).rules()),
    'sequiturpython': _build_grammar,
}


def build(impl, tokens):
    """Normalised grammar {rule key: [symbols]} with rule 0 as the main rule."""
    return IMPLEMENTATIONS[impl](tokens)


def expand(grammar, key=0, memo=None):
    memo = {} if memo is None else memo
    if key not in memo:
        out = []
        for x in grammar[key]:
            out.extend(expand(grammar, x.key, memo) if isinstance(x, Ref) else [x])
        memo[key] = out
    return memo[key]


def violations(grammar, tokens):
    """Problems with a grammar built from tokens; empty when it is a valid Sequitur grammar."""
    problems = []
    if expand(grammar) != list(tokens):
        problems.append('expansion differs from input')
    # digram uniqueness: no pair of adjacent symbols occurs twice, except as
    # overlapping occurrences inside a run such as 'aaa'
    seen = {}
    for key, body in grammar.items():
        for i in range(len(body) - 1):
            digram = (body[i], body[i + 1])
            if digram not in seen:
                seen[digram] = (key, i)
            elif seen[digram] != (key, i - 1):
                problems.append('digram %r repeated in rules %r and %r' % (digram, seen[digram][0], key))
    # rule utility: every rule except the main one is used at least twice
    uses = Counter(x.key for body in grammar.values() for x in body if isinstance(x, Ref))
    problems.extend('rule %r used %d time(s)' % (key, uses[key])
                    for key in grammar if key != 0 and uses[key] < 2)
    return problems


@contextlib.contextmanager
def time_limit(seconds):
    """Fail instead of hanging; a no-op where SIGALRM is unavailable (Windows)."""
    if not hasattr(signal, 'SIGALRM'):
        yield
        return

    def expire(signum, frame):
        raise TimeoutError('did not finish within %d seconds' % seconds)

    previous = signal.signal(signal.SIGALRM, expire)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)
