# -*- coding: utf-8 -*-
# file: backend.py
"""
The engine behind Sequencer3: core.Grammar in Python, or the same algorithm
compiled from rust/ as the optional module pysequitur_rs.

Both build the same grammar. Sequencer3 uses the compiled engine when
pysequitur_rs can be imported, and core.Grammar otherwise. To choose:

    PYSEQUITUR_BACKEND=python   always core.Grammar
    PYSEQUITUR_BACKEND=rust     always pysequitur_rs: Sequencer3() raises ImportError without it
    PYSEQUITUR_BACKEND=auto     the default: pysequitur_rs if it is installed

The variable is read when pysequitur is imported. Sequencer3(tokens,
backend='python') or backend='rust' chooses for one sequencer.

The compiled engine takes ints and strs. On any other token (a float, a
tuple, True, None, an int beyond 64 bits, a subclass of int or str) the
sequencer moves to core.Grammar, replaying the input read so far, and carries
on there, so its grammar is always the one core.Grammar builds.
"""
import os
import warnings

from .core import Grammar
from .sequiturpython.symbol import RuleIndex

# The version of the algorithm that pysequitur_rs must implement. A build of
# another version is not used: rebuild it from rust/.
ENGINE_VERSION = 1
BACKENDS = ('python', 'rust')

_rust = None
_rust_error = None


def _load_rust():
    """pysequitur_rs, or None with the reason in _rust_error."""
    global _rust, _rust_error
    if _rust is None and _rust_error is None:
        try:
            import pysequitur_rs
        except ImportError as e:
            _rust_error = 'pysequitur_rs is not installed (%s); build it from rust/ with maturin' % e
        else:
            version = getattr(pysequitur_rs, 'ENGINE_VERSION', None)
            if version == ENGINE_VERSION:
                _rust = pysequitur_rs
            else:
                _rust_error = ('pysequitur_rs implements engine version %r, this pysequitur needs %d; '
                               'rebuild it from rust/' % (version, ENGINE_VERSION))
    return _rust


def _default():
    choice = os.environ.get('PYSEQUITUR_BACKEND', 'auto').strip().lower() or 'auto'
    if choice == 'python':
        return 'python'
    if choice not in ('auto', 'rust'):
        warnings.warn('PYSEQUITUR_BACKEND must be auto, python or rust, not %r; using auto' % choice,
                      RuntimeWarning)
        choice = 'auto'
    if choice == 'rust' or _load_rust() is not None:
        return 'rust'
    if _rust_error.startswith('pysequitur_rs implements'):
        warnings.warn(_rust_error + '; using the Python engine', RuntimeWarning)
    return 'python'


# The backend Sequencer3 uses when none is given: 'rust' or 'python'. Change it
# to switch every sequencer created from then on.
DEFAULT = _default()


def available():
    """True when the compiled engine can be used."""
    return _load_rust() is not None


def new_grammar(backend=None):
    """An empty grammar: core.Grammar, or RustGrammar for the compiled engine."""
    backend = DEFAULT if backend is None else backend
    if backend == 'rust':
        if _load_rust() is None:
            raise ImportError("the 'rust' backend was asked for, but " + _rust_error)
        return RustGrammar()
    if backend == 'python':
        return Grammar()
    raise ValueError('backend must be one of %s, not %r' % (', '.join(BACKENDS), backend))


class RustGrammar(object):
    """
    core.Grammar's interface on the compiled engine. When a token comes that the
    engine does not take, it replays the input into a core.Grammar and goes on
    with that one.
    """
    __slots__ = ('_engine', '_python')

    def __init__(self, tokens=None):
        self._engine = _load_rust().Grammar()
        self._python = None
        if tokens is not None:
            self.feed(tokens)

    @property
    def backend(self):
        """'rust', or 'python' once a token sent the grammar to core.Grammar."""
        return 'rust' if self._python is None else 'python'

    def __len__(self):
        """Number of tokens read so far."""
        return len(self._engine) if self._python is None else len(self._python)

    def __reduce__(self):
        return (RustGrammar, (self.expand(),))

    def feed(self, tokens):
        if self._python is None:
            t = type(tokens)
            if t is not list and t is not tuple and t is not str:
                tokens = list(tokens)
            if self._engine.feed(tokens):
                return self
            self._fall_back()
        self._python.feed(tokens)
        return self

    def stream(self, token):
        """Append one token to the input."""
        if self._python is None:
            if self._engine.stream(token):
                return
            self._fall_back()
        self._python.stream(token)

    def rules(self):
        """
        Rules as lists, the main rule first and the others in order of first use.
        Nonterminals are RuleIndex values pointing into the returned list.
        """
        if self._python is None:
            return self._engine.rules(RuleIndex)
        return self._python.rules()

    def size(self):
        """(rules, symbols): len(rules()) and sum(len(r) for r in rules())."""
        if self._python is None:
            return self._engine.size()
        rules = self._python.rules()
        return len(rules), sum(len(r) for r in rules)

    def expand(self):
        """The input read so far."""
        if self._python is None:
            return self._engine.expand()
        return _expand(self._python.rules())

    def _fall_back(self):
        python = Grammar()
        python.feed(self._engine.expand())
        self._python = python
        self._engine = None


def _expand(rules):
    out = []
    stack = [iter(rules[0])] if rules else []
    while stack:
        for x in stack[-1]:
            if isinstance(x, RuleIndex):
                stack.append(iter(rules[x]))
                break
            out.append(x)
        else:
            stack.pop()
    return out


def grammar_size(tokens, backend=None):
    """
    sum(len(r) for r in Sequencer3(tokens).get()), the number of symbols in the
    grammar, without building the rules as lists when the compiled engine
    takes the tokens.
    """
    g = new_grammar(backend)
    g.feed(tokens)
    if isinstance(g, RustGrammar):
        return g.size()[1]
    return sum(len(r) for r in g.rules())

