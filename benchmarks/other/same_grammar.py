"""
Checks that pysequitur builds exactly the grammar of Nevill-Manning's C++ reference:
it prints pysequitur's grammar the way `sequitur -p` does, rules numbered in the same
order, and compares the two texts.

    sh fetch.sh                                 # once
    python same_grammar.py FILE [FILE ...]      # default: the sample texts
    python same_grammar.py --backend both FILE  # the Python engine and the compiled one

With --backend both, it also compares the two backends' grammars as lists, element
types included. Times are for building the grammar and getting its rules as lists.
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))

from pysequitur.backend import new_grammar  # noqa: E402
from pysequitur.sequiturpython.symbol import RuleIndex  # noqa: E402

BINARY = HERE / 'vendor' / 'sequitur' / 'c++' / 'sequitur'


def printed(symbol):
    """A symbol as the C++ program prints it."""
    if type(symbol) is RuleIndex:
        return str(int(symbol))
    if symbol == '\n':
        return '\\n'
    if symbol == '\t':
        return '\\t'
    if symbol == ' ':
        return '_'
    if symbol in '\\()_' or symbol.isdigit():
        return '\\' + symbol
    return symbol


def build(text, backend):
    start = time.perf_counter()
    rules = new_grammar(backend).feed(text).rules()
    return rules, time.perf_counter() - start


def same_lists(a, b):
    return a == b and all([type(x) for x in p] == [type(x) for x in q] for p, q in zip(a, b))


def main(paths, backends):
    different = 0
    for path in paths:
        text = Path(path).read_text()
        with open(path, 'rb') as f:
            theirs = subprocess.run([str(BINARY), '-p', '-q', '-m', '128'], stdin=f, capture_output=True).stdout
        grammars = {}
        for backend in backends:
            rules, seconds = build(text, backend)
            grammars[backend] = rules
            ours = ''.join('%d -> %s\n' % (i, ''.join(printed(x) + ' ' for x in body))
                           for i, body in enumerate(rules))
            same = ours.encode('utf-8') == theirs
            different += not same
            print('%-30s %-6s %s as C++ (%d rules) %9.4f s' % (
                Path(path).name, backend, 'identical' if same else 'DIFFERENT', ours.count('\n'), seconds))
        if len(grammars) == 2:
            same = same_lists(grammars['python'], grammars['rust'])
            different += not same
            print('%-30s rust   %s to python, as lists' % (Path(path).name, 'identical' if same else 'DIFFERENT'))
    return 1 if different else 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0].strip())
    parser.add_argument('files', nargs='*', help='default: the sample texts')
    parser.add_argument('--backend', choices=['python', 'rust', 'both'], default='python')
    args = parser.parse_args()
    sys.exit(main(args.files or sorted(str(p) for p in (ROOT / 'samples').glob('*.txt')),
                  ['python', 'rust'] if args.backend == 'both' else [args.backend]))
