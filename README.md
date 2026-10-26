# Python Sequitur (Nevill-Manning) algorithm (pysequitur)

Sequitur (Nevill-Manning & Witten, 1997) reads a sequence one symbol at a time and builds a context-free grammar of its repetitions: every pair of adjacent symbols occurs only once in the grammar, and every rule is used at least twice. The rules are the repeated phrases of the input, nested into a hierarchy.

For more information see: [Jupyter Notebook](https://github.com/markomanninen/pysequitur/blob/master/Python%20Sequitur%20Algorithms.ipynb) on GitHub or [Jupyter Notebook](http://nbviewer.jupyter.org/github/markomanninen/pysequitur/blob/master/Python%20Sequitur%20Algorithms.ipynb) on nbviewer.

## Implementations

- `Sequencer3`: the linear-time algorithm of the C++ reference implementation, first ported here from the JavaScript version. Recommended.
- `Sequencer`: keeps rules as lists of digrams. Quadratic time.
- `Sequencer2`: array slicing. Quadratic time, and it can keep a rule that is used only once.

All three take any hashable tokens: characters, words, lines or numbers.

## Basic usage

<pre><code>
from pysequitur import Sequencer3, print_grammar

input_string = open('peaseporridge.txt', 'r').read()
s = Sequencer3(input_string)
print_grammar(s)
</code></pre>

should output:

<pre><code>
S → ^1^2^3^4^3^5↵↵^6^2^7^4^7^5
1 → peas^8rridg^9
2 → hot
3 → ^10^1
4 → c^11
5 → ^12_th^8t^10n^12^9days_^11.
6 → som^9lik^9it_
7 → ^10^6
8 → ^9po
9 → e_
10 → ,↵
11 → old
12 → in
</code></pre>

`s.get()` returns the rules as lists, with `RuleIndex` values for rule references, and `s.resolve()` expands the grammar back to the input. Tokens can be streamed in one at a time with `s.stream(token)`.

Words as tokens, keeping the whitespace so that the tokens join back to the text:

<pre><code>
import re

tokens = re.findall(r'\w+|\s+|[^\w\s]', 'the cat sat on the mat and the cat sat down')
print_grammar(Sequencer3(tokens))
# S → ^1^2on^3mat_and^3^2down
# 1 → the_
# 2 → cat_sat_
# 3 → _^1
</code></pre>

## Performance

Building the grammar, median of 3 runs on an Apple M4 Pro with Python 3.12:

| Implementation | genesis1.txt (2.5 KB) | iamsam.txt (3.5 KB) | revelation.txt (46.5 KB) |
|----------------|-----------------------|---------------------|--------------------------|
| Sequencer3     | 0.004 s               | 0.006 s             | 0.07 s                   |
| Sequencer      | 0.05 s                | 0.08 s              | 10.7 s                   |
| Sequencer2     | 0.13 s                | 0.19 s              | 36.8 s                   |

`Sequencer3` runs in linear time, about 600,000 tokens per second: 1.6 MB of Python source takes 2.5 s and 4.6 MB takes 7.6 s.

### Running benchmarks

<pre><code>
python benchmark.py genesis1.txt Sequencer3
python benchmark.py genesis1.txt iamsam.txt revelation.txt Sequencer3 Sequencer --runs 5
python benchmark.py iamsam.txt --tokens word --json
</code></pre>

Give any number of input files and implementations (`Sequencer`, `Sequencer2`, `Sequencer3`; default `Sequencer3`). Build is the time to stream the input in, resolve the time to extract the grammar and expand it back, and every run checks that the expansion equals the input.

## Tests

<pre><code>
python -m unittest discover -s tests -t .
</code></pre>

The tests check the grammar properties above (exact round trip, digram uniqueness, rule utility) for every implementation on the sample files, long runs of one symbol and seeded random inputs.
