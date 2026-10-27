"""
Runs Sequitur implementations in several languages on the same inputs, and
reports how long each takes to build the grammar, its peak memory, and the
grammar it builds, compared with the C++ reference by Nevill-Manning.

    sh fetch.sh            # once: fetch and build the other implementations
    python compare.py      # prints one JSON object per run, then a table
    python compare.py --json FILE   # also writes the rows to FILE

Times are medians of three runs, each in a fresh process. They cover building
the grammar only; reading the input and starting the process or the virtual
machine are left out, except for the C++ program, which is timed as a whole.
"""
import importlib.util
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import sysconfig
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
VENDOR = HERE / 'vendor'
RUNS = 3


def python_source():
    """1.6 MB of the standard library's source, ASCII only so that every implementation sees the same tokens."""
    path = VENDOR / 'python_source.txt'
    if not path.exists():
        stdlib = Path(sysconfig.get_paths()['stdlib'])
        text = ''.join(p.read_text(errors='replace') for p in sorted(stdlib.glob('*.py')))
        path.write_text(text.encode('ascii', 'replace').decode('ascii')[:1600000])
    return path


INPUTS = [('revelation.txt, 46.5 KB', ROOT / 'samples' / 'revelation.txt'),
          ('Python source, 1.6 MB', None)]


def implementations():
    py = sys.executable
    env_new = dict(os.environ, PYTHONPATH=str(ROOT))
    env_old = dict(os.environ, PYTHONPATH=str(VENDOR / 'pysequitur-71a9298'))
    found = [
        ('C++ reference (Nevill-Manning)', 'C++', 'cpp', None),
        ('C++11 (jsdw)', 'C++', [str(VENDOR / 'bench_jsdw')], None),
        ('Rust (sequitur-rs)', 'Rust', [str(VENDOR / 'sequitur-rs' / 'target' / 'release' / 'examples' / 'bench')], None),
        ('Java port (Eibe Frank, 1997)', 'Java', ['java', '-cp', str(VENDOR / 'java'), 'Bench'], None),
        ('JavaScript (Nevill-Manning, 2019)', 'JavaScript',
         ['node', 'bench_js.js', str(VENDOR / 'sequitur' / 'javascript' / 'main.js')], None),
        ('pysequitur, CPython 3.12', 'Python', [py, 'bench_pysequitur.py', 'core'], env_new),
    ]
    if importlib.util.find_spec('pysequitur_rs'):
        # the compiled engine built from rust/, behind Sequencer3 when installed
        found.append(('pysequitur, Rust backend', 'Rust', [py, 'bench_pysequitur.py', 'rust'], env_new))
    pypy = shutil.which('pypy3') or shutil.which('pypy3.10')
    if pypy:
        found.append(('pysequitur, PyPy', 'Python', [pypy, 'bench_pysequitur.py', 'core'], env_new))
    found += [
        ('scikit-sequitur, Cython', 'Python', [str(VENDOR / 'venv-sksequitur-cython' / 'bin' / 'python'),
                                              'bench_sksequitur.py'], None),
        ('scikit-sequitur, pure Python', 'Python', [str(VENDOR / 'venv-sksequitur-pure' / 'bin' / 'python'),
                                                   'bench_sksequitur.py'], None),
        ('pysequitur before the fixes', 'Python', [py, 'bench_pysequitur.py', 'port'], env_old),
        ('Python port (Annaswamy, 2013)', 'Python',
         [py, 'bench_python_port.py', str(VENDOR / 'sequitur' / 'python' / 'sequitur.py')], None),
    ]
    return found


def peak_memory(stderr):
    # /usr/bin/time -l on macOS, -v on Linux
    m = re.search(r'(\d+)\s+maximum resident set size', stderr)
    if m:
        return int(m.group(1)) / 2 ** 20
    m = re.search(r'Maximum resident set size \(kbytes\): (\d+)', stderr)
    return int(m.group(1)) / 1024 if m else None


def timed(command, env=None, stdin=None):
    flag = '-l' if sys.platform == 'darwin' else '-v'
    import time
    start = time.perf_counter()
    done = subprocess.run(['/usr/bin/time', flag] + command, cwd=HERE, env=env, stdin=stdin,
                          capture_output=True, text=True, timeout=3600)
    return time.perf_counter() - start, done


def run_cpp(path):
    binary = str(VENDOR / 'sequitur' / 'c++' / 'sequitur')
    with open(path) as f:
        seconds, done = timed([binary, '-q', '-m', '128'], stdin=f)
    with open(path) as f:
        printed = subprocess.run([binary, '-p', '-q', '-m', '128'], stdin=f, capture_output=True, text=True).stdout
    lines = [line for line in printed.splitlines() if ' -> ' in line]
    symbols = sum(len(line.split(' -> ', 1)[1].split()) for line in lines)
    return {'seconds': round(seconds, 6), 'rules': len(lines) - 1, 'symbols': symbols, 'roundtrip': None,
            'memory_mb': peak_memory(done.stderr)}


def run(command, env, path):
    _, done = timed(command + [str(path)], env=env)
    if done.returncode:
        # the program's own last words come before the statistics /usr/bin/time adds
        own = re.split(r'\n\s*[\d.]+ real\b|\n\s*Command (?:exited|terminated)', done.stderr)[0].strip()
        return {'error': own.splitlines()[-1] if own else 'exit %d' % done.returncode}
    result = json.loads(done.stdout.strip().splitlines()[-1])
    result['memory_mb'] = peak_memory(done.stderr)
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--json', help='write the rows to this file')
    args = parser.parse_args()
    rows = []
    for label, path in INPUTS:
        path = path or python_source()
        reference = None
        for name, language, command, env in implementations():
            results = [run_cpp(path) if command == 'cpp' else run(command, env, path) for _ in range(RUNS)]
            if any('error' in r for r in results):
                row = {'input': label, 'implementation': name, 'language': language,
                       'error': next(r['error'] for r in results if 'error' in r)}
            else:
                row = {'input': label, 'implementation': name, 'language': language,
                       'seconds': statistics.median(r['seconds'] for r in results),
                       'memory_mb': round(statistics.median(r['memory_mb'] for r in results), 1),
                       'rules': results[0]['rules'], 'symbols': results[0]['symbols'],
                       'roundtrip': results[0]['roundtrip']}
                if command == 'cpp':
                    reference = row
                row['same_size_as_cpp'] = (reference is not None and row['rules'] == reference['rules']
                                           and row['symbols'] == reference['symbols'])
            print(json.dumps(row), flush=True)
            rows.append(row)
    if args.json:
        Path(args.json).write_text(json.dumps(rows, indent=1) + '\n')
    print()
    print('%-24s %-34s %10s %9s %8s %9s  %s' % ('input', 'implementation', 'seconds', 'MB', 'rules', 'symbols',
                                                'same as C++ / expands back'))
    for row in rows:
        if 'error' in row:
            print('%-24s %-34s  error: %s' % (row['input'], row['implementation'], row['error'][:60]))
            continue
        print('%-24s %-34s %10.3f %9.1f %8d %9d  %s / %s' % (
            row['input'], row['implementation'], row['seconds'], row['memory_mb'], row['rules'], row['symbols'],
            'yes' if row['same_size_as_cpp'] else 'no', {True: 'yes', False: 'NO', None: '-'}[row['roundtrip']]))


if __name__ == '__main__':
    main()
