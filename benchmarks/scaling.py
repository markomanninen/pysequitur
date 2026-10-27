"""
Time to build the grammar against the length of the input, for each Python
implementation in the history of pysequitur:

    python benchmarks/scaling.py [--json FILE]

The inputs are prefixes of 1.6 MB of Python source (benchmarks/other/compare.py
makes the file), doubling from 1 KB. Each measurement runs in a fresh process,
as the median of three runs, or one run when a run takes over five seconds. An
implementation stops at the first length that takes over 30 seconds.

'port, 2016' is the sequiturpython port as it was before the fixes, at commit
71a9298; benchmarks/other/fetch.sh puts that checkout in benchmarks/other/vendor.
"""
import argparse
import json
import os
import statistics
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCE = HERE / 'other' / 'vendor' / 'python_source.txt'
OLD = HERE / 'other' / 'vendor' / 'pysequitur-71a9298'
SIZES = [1000 * 2 ** k for k in range(11)] + [1600000]
LIMIT = 30

WORKER = r'''
import sys, time
kind, size = sys.argv[1], int(sys.argv[2])
text = open(sys.argv[3], encoding='utf-8').read()[:size]
if kind == 'core':
    from pysequitur.core import Grammar
    start = time.perf_counter()
    Grammar(text)
elif kind == 'port':
    from pysequitur.sequiturpython.grammar import Grammar
    start = time.perf_counter()
    Grammar().train_string(text)
else:
    from pysequitur.main import Sequencer, Sequencer2
    sequencer = {'Sequencer': Sequencer, 'Sequencer2': Sequencer2}[kind]()
    start = time.perf_counter()
    for c in text:
        sequencer.stream(c)
print(time.perf_counter() - start)
'''

IMPLEMENTATIONS = [
    ('Sequencer, 2016', 'Sequencer', ROOT),
    ('Sequencer2, 2016', 'Sequencer2', ROOT),
    ('port, 2016', 'port', OLD),
    ('core, 2026', 'core', ROOT),
]


def once(kind, path, size):
    env = dict(os.environ, PYTHONPATH=str(path))
    done = subprocess.run([sys.executable, '-c', WORKER, kind, str(size), str(SOURCE)], env=env,
                          capture_output=True, text=True, timeout=600)
    if done.returncode:
        raise RuntimeError(done.stderr.strip().splitlines()[-1])
    return float(done.stdout)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--json', help='write the measurements to this file')
    args = parser.parse_args()
    rows = []
    for label, kind, path in IMPLEMENTATIONS:
        for size in SIZES:
            first = once(kind, path, size)
            times = [first] if first > 5 else [first, once(kind, path, size), once(kind, path, size)]
            row = {'implementation': label, 'chars': size, 'seconds': round(statistics.median(times), 6)}
            print(json.dumps(row), flush=True)
            rows.append(row)
            if first > LIMIT:
                break
    if args.json:
        Path(args.json).write_text(json.dumps(rows, indent=1) + '\n')


if __name__ == '__main__':
    main()
