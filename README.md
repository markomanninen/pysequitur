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

## Analysis

`pysequitur.analysis` indexes the grammar of one or more documents for questions about the text: which phrases repeat, how often, where (line and column), inside which longer phrases, and what several documents have in common. Tokens are characters, words or lines, and every occurrence maps to an exact span of a document.

<pre><code>
from pysequitur.analysis import Analysis

a = Analysis.from_text(open('iamsam.txt').read(), tokens='word')
a.summary()['repeated_fraction']           # 0.9625: almost all of the text is repeated material
a.repeats(min_chars=12, limit=3)           # 'I do not like' ×12, 'green eggs and ham' ×8, ...
a.find('Sam-I-am')['positions'][0]         # {'document': 'text', 'line': 6, 'column': 6, 'context': 'That «Sam-I-am»...'}
</code></pre>

## MCP server for agents

The MCP server lets agents use the analysis: find what repeats in a text, file or set of documents, rank the phrases, locate them, and compare documents. It needs Python 3.10 or later and the `mcp` extra:

<pre><code>
pip install -e ".[mcp]"
pysequitur-mcp --root ~/texts
</code></pre>

The server talks over stdio and reads files only under the `--root` directories (default: the current directory). To add it to Claude Code:

<pre><code>
claude mcp add pysequitur -- pysequitur-mcp --root /path/to/texts
</code></pre>

Other clients take the usual configuration:

<pre><code>
{"mcpServers": {"pysequitur": {"command": "pysequitur-mcp", "args": ["--root", "/path/to/texts"]}}}
</code></pre>

| Tool | What it does |
|------|--------------|
| `analyze` | Builds the grammar of a text, a file or several documents. Returns an `analysis_id` and a summary: the share of the text inside repeats, the phrases covering the most text, the longest repeats. |
| `list_repeats` | Ranks repeated phrases by coverage, length, occurrences or depth, filtered by length, count, contained text or document. |
| `get_rule` | One phrase in detail: its parts, the phrases that contain it, and its positions with line, column and context. |
| `find_phrase` | Where any phrase occurs, whether it is itself a repeat, and which repeats contain it. |
| `shared_phrases` | The longest passages several documents have in common, and how much of each document also occurs in each other one. |
| `repetition_profile` | How much of each stretch of a document is repeated material: boilerplate, refrains, duplicated sections. |
| `get_grammar` | The grammar as text. |
| `list_analyses` | The analyses the server holds. |

Use word tokens for prose, line tokens for code, logs and data files (they find duplicated blocks of lines), and character tokens for text without spaces. Analysing `revelation.txt`, which has no spaces at all, by characters takes 0.1 s and finds its longest refrain, "he that hath an ear, let him hear what the Spirit saith unto the churches", as `oexwnousakousatwtitopneumalegeitaisekklhsiais`.

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

The tests check the grammar properties above (exact round trip, digram uniqueness, rule utility) for every implementation on the sample files, long runs of one symbol and seeded random inputs. The MCP server tests run when the `mcp` extra is installed, for example in a virtualenv with `pip install -e ".[mcp]"`.
