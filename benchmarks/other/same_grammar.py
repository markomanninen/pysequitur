"""
Checks that pysequitur builds exactly the grammar of Nevill-Manning's C++ reference:
it prints pysequitur's grammar the way `sequitur -p` does, rules numbered in the same
order, and compares the two texts.

    sh fetch.sh                                 # once
    python same_grammar.py FILE [FILE ...]      # default: the sample texts
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))

from pysequitur.core import Grammar  # noqa: E402
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


def main(paths):
    different = 0
    for path in paths:
        text = Path(path).read_text()
        ours = ''.join('%d -> %s\n' % (i, ''.join(printed(x) + ' ' for x in body))
                       for i, body in enumerate(Grammar(text).rules()))
        with open(path, 'rb') as f:
            theirs = subprocess.run([str(BINARY), '-p', '-q', '-m', '128'], stdin=f, capture_output=True).stdout
        same = ours.encode('utf-8') == theirs
        different += not same
        print('%-40s %s (%d rules)' % (Path(path).name, 'identical' if same else 'DIFFERENT', ours.count('\n')))
    return 1 if different else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:] or sorted(str(p) for p in (ROOT / 'samples').glob('*.txt'))))
