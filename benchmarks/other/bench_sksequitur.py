"""
Times scikit-sequitur on a file, then measures the grammar it built and expands it
back: python bench_sksequitur.py FILE

Run it with the Python of a virtualenv that has scikit-sequitur, built with or
without Cython (fetch.sh makes one of each).
"""
import json
import sys
import time

import sksequitur.core
from sksequitur import Grammar, Parser, Production

text = open(sys.argv[1], encoding='utf-8').read()
sys.setrecursionlimit(100000)
start = time.perf_counter()
parser = Parser()
parser.feed(text)
seconds = time.perf_counter() - start
grammar = Grammar(parser.tree)
print(json.dumps({'seconds': round(seconds, 6), 'rules': len(grammar) - 1,
                  'symbols': sum(len(body) for body in grammar.values()),
                  'roundtrip': ''.join(grammar.expand(Production(0))) == text,
                  'compiled': hasattr(sksequitur.core, '__file__') and sksequitur.core.Parser.__module__ != 'sksequitur.core'}))
