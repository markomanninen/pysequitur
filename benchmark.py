"""
Benchmark the Sequitur implementations.

    python benchmark.py genesis1.txt Sequencer3
    python benchmark.py genesis1.txt iamsam.txt revelation.txt Sequencer3 Sequencer
    python benchmark.py revelation.txt --tokens word --runs 5 --json

Build is the time to stream every token in; resolve is the time to extract the
grammar and expand it back. Every run checks that the expansion equals the input.
"""
import argparse
import json
import re
import statistics
import sys
import time

from pysequitur.main import Sequencer, Sequencer2, Sequencer3

IMPLEMENTATIONS = {'Sequencer': Sequencer, 'Sequencer2': Sequencer2, 'Sequencer3': Sequencer3}


def tokenize(text, mode):
    if mode == 'word':
        # words, whitespace runs and single punctuation marks: joins back to the text
        return re.findall(r'\w+|\s+|[^\w\s]', text)
    return list(text)


def run_once(cls, tokens):
    start = time.perf_counter()
    sequencer = cls()
    for token in tokens:
        sequencer.stream(token)
    built = time.perf_counter()
    resolved = sequencer.resolve()
    resolved_at = time.perf_counter()
    return {
        'build': built - start,
        'resolve': resolved_at - built,
        'rules': len(sequencer.grammar_rules()),
        'round_trip': resolved == tokens,
    }


def benchmark(path, name, tokens_mode, runs):
    with open(path) as f:
        tokens = tokenize(f.read(), tokens_mode)
    results = [run_once(IMPLEMENTATIONS[name], tokens) for _ in range(runs)]
    build = statistics.median(r['build'] for r in results)
    return {
        'file': path,
        'implementation': name,
        'tokens': len(tokens),
        'token_mode': tokens_mode,
        'runs': runs,
        'build_seconds': round(build, 4),
        'resolve_seconds': round(statistics.median(r['resolve'] for r in results), 4),
        'tokens_per_second': round(len(tokens) / build) if build else None,
        'rules': results[0]['rules'],
        'round_trip': all(r['round_trip'] for r in results),
    }


def main():
    parser = argparse.ArgumentParser(description='Benchmark the Sequitur implementations.')
    parser.add_argument('targets', nargs='+', metavar='FILE_OR_IMPLEMENTATION',
                        help='input files, and any of: %s (default Sequencer3)' % ', '.join(IMPLEMENTATIONS))
    parser.add_argument('-n', '--runs', type=int, default=3, help='runs per measurement; the median is reported')
    parser.add_argument('-t', '--tokens', choices=['char', 'word'], default='char', help='tokenization')
    parser.add_argument('--json', action='store_true', help='print one JSON object per measurement')
    args = parser.parse_intermixed_args()

    names = [t for t in args.targets if t in IMPLEMENTATIONS] or ['Sequencer3']
    files = [t for t in args.targets if t not in IMPLEMENTATIONS]
    if not files:
        parser.error('no input files given')

    if not args.json:
        print('%-18s %-11s %9s %10s %11s %12s %7s  %s' % (
            'file', 'version', 'tokens', 'build (s)', 'resolve (s)', 'tokens/s', 'rules', 'round trip'))
    failed = False
    for path in files:
        for name in names:
            try:
                row = benchmark(path, name, args.tokens, args.runs)
            except FileNotFoundError:
                print('Error: input file not found at %s' % path, file=sys.stderr)
                return 1
            failed = failed or not row['round_trip']
            if args.json:
                print(json.dumps(row))
            else:
                print('%-18s %-11s %9d %10.4f %11.4f %12d %7d  %s' % (
                    path[-18:], name, row['tokens'], row['build_seconds'], row['resolve_seconds'],
                    row['tokens_per_second'] or 0, row['rules'], 'ok' if row['round_trip'] else 'FAILED'))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
