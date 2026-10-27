"""
How often a Sequitur implementation builds a wrong grammar.

For every input, the grammar must expand back to the input exactly, repeat no
digram, and use every rule at least twice. Run it on two checkouts to compare
them, for example the code before and after a fix:

    python benchmarks/correctness.py                      # this checkout
    PYTHONPATH=../old-checkout python benchmarks/correctness.py

It checks pysequitur.sequiturpython.grammar.Grammar, which exists in every
version, by walking its linked lists, so a broken grammar is measured instead
of hanging the walk; and pysequitur.core.Grammar where it exists.
"""
import json
import random
import signal
import sys
import sysconfig
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))  # after PYTHONPATH, so another checkout can be measured

from pysequitur.sequiturpython.grammar import Grammar  # noqa: E402
from pysequitur.sequiturpython.symbol import NonTerminal  # noqa: E402

try:
    from pysequitur.core import Grammar as CoreGrammar
except ImportError:  # versions before the linear-time core
    CoreGrammar = None


class Timeout(Exception):
    pass


def _expire(signum, frame):
    raise Timeout()


def walk(grammar, limit):
    """Rules of a sequiturpython Grammar as lists, nonterminals as ('R', id); None when a list never ends."""
    rules, todo, seen = {}, [grammar.root_production], set()
    while todo:
        rule = todo.pop()
        body, symbol, steps = [], rule.first(), 0
        while not symbol.is_guard():
            steps += 1
            if steps > limit:
                return None
            if isinstance(symbol, NonTerminal):
                body.append(('R', id(symbol.rule)))
                if id(symbol.rule) not in seen:
                    seen.add(id(symbol.rule))
                    todo.append(symbol.rule)
            else:
                body.append(symbol.terminal)
            symbol = symbol.next
        rules['root' if rule is grammar.root_production else id(rule)] = body
    return rules


def from_core(tokens):
    rules = CoreGrammar(tokens).rules()
    return {('root' if i == 0 else i): [('R', int(x)) if type(x).__name__ == 'RuleIndex' else x for x in body]
            for i, body in enumerate(rules)}


def problems(rules, text):
    """The properties a Sequitur grammar of text breaks: expansion, digram, utility."""
    if rules is None:
        return {'never returns'}
    found = set()

    def expand(key, depth=0):
        if depth > 10000:
            raise RecursionError
        out = []
        for x in rules[key]:
            out.extend(expand(x[1], depth + 1) if isinstance(x, tuple) else [x])
        return out

    try:
        if ''.join(expand('root')) != text:
            found.add('wrong expansion')
    except (RecursionError, KeyError):
        found.add('wrong expansion')
    seen = {}
    for key, body in rules.items():
        for i in range(len(body) - 1):
            digram = (body[i], body[i + 1])
            if digram in seen and seen[digram] != (key, i - 1):
                found.add('repeated digram')
            seen.setdefault(digram, (key, i))
    uses = Counter(x[1] for body in rules.values() for x in body if isinstance(x, tuple))
    if any(uses[key] < 2 for key in rules if key != 'root'):
        found.add('rule used once')
    return found


def check(build, text, seconds=10):
    signal.signal(signal.SIGALRM, _expire)
    signal.alarm(seconds)
    try:
        return problems(build(text), text)
    except Timeout:
        return {'never returns'}
    finally:
        signal.alarm(0)


def port(text):
    g = Grammar()
    g.train_string(text)
    return walk(g, 4 * len(text) + 16)


def inputs():
    samples = ROOT / 'samples'
    yield 'sample texts', [p.read_text() for p in sorted(samples.glob('*.txt'))]
    stdlib = Path(sysconfig.get_paths()['stdlib'])
    code = ''.join(p.read_text(errors='replace') for p in sorted(stdlib.glob('*.py')))
    yield 'Python source, 100 KB pieces', [code[i:i + 100000] for i in range(0, 1000000, 100000)]
    yield 'runs of one letter, 1 to 100', ['a' * n for n in range(1, 101)]
    rnd = random.Random(1997)
    for alphabet in ('ab', 'abc', 'abcdefgh'):
        yield 'random strings over %s' % alphabet, [
            ''.join(rnd.choice(alphabet) for _ in range(rnd.randint(1, 300))) for _ in range(1000)]


def main():
    builders = [('sequiturpython', port)] + ([('core', from_core)] if CoreGrammar else [])
    for group, texts in inputs():
        for name, build in builders:
            counts = Counter()
            failed = 0
            for text in texts:
                found = check(build, text)
                counts.update(found)
                failed += bool(found)
            print(json.dumps({'implementation': name, 'inputs': group, 'count': len(texts), 'failed': failed,
                              'problems': dict(counts)}))


if __name__ == '__main__':
    main()
