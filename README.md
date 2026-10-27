# Python Sequitur (Nevill-Manning) algorithm (pysequitur)

Sequitur (Nevill-Manning & Witten, 1997) reads a sequence one symbol at a time and builds a context-free grammar of its repetitions: every pair of adjacent symbols occurs only once in the grammar, and every rule is used at least twice. The rules are the repeated phrases of the input, nested into a hierarchy.

The article [Giving AI agents an eye for repetition](https://markotmanninen.substack.com/p/giving-ai-agents-an-eye-for-repetition) explains how Sequitur works, how pysequitur compares with other implementations, and what its tools changed for AI agents asked about repetition.

For more information see: [Jupyter Notebook](https://github.com/markomanninen/pysequitur/blob/master/Python%20Sequitur%20Algorithms.ipynb) on GitHub or [Jupyter Notebook](http://nbviewer.jupyter.org/github/markomanninen/pysequitur/blob/master/Python%20Sequitur%20Algorithms.ipynb) on nbviewer.

## Implementations

- `Sequencer3`: the linear-time algorithm of the C++ reference implementation, first ported here from the JavaScript version. Recommended.
- `Sequencer`: keeps rules as lists of digrams. Quadratic time.
- `Sequencer2`: array slicing. Quadratic time, and it can keep a rule that is used only once.

All three take any hashable tokens: characters, words, lines or numbers.

### Optional compiled engine

`rust/` holds `Sequencer3`'s engine ported to Rust, as the Python module `pysequitur_rs`. When it is installed, `Sequencer3` uses it and builds the same grammar: the same rules, numbered the same, with `RuleIndex` references. pysequitur itself needs no Rust and installs as before. Building the module needs a Rust toolchain:

<pre><code>
pip install ./rust                       # from a checkout; or, in a virtualenv: cd rust && maturin develop --release
</code></pre>

`PYSEQUITUR_BACKEND=python` makes every `Sequencer3` use the Python engine, `rust` requires the compiled one, and `auto`, the default, uses it when it can be imported. `Sequencer3(tokens, backend='python')` chooses for one sequencer. The compiled engine takes `int` and `str` tokens; given anything else, such as a float, a tuple, `True` or an int beyond 64 bits, the sequencer carries on in Python with the same result.

Time to build the grammar and get it with `get()`, measured from Python on an Apple M4 Pro:

| Input | Python | Rust | |
|-------|-------:|-----:|---:|
| 2,400 ints, a few hundred distinct | 3.1 ms | 0.16 ms | 19× |
| revelation.txt (46.5 KB) | 62 ms | 3.3 ms | 19× |
| 1.6 MB of Python source | 2.47 s | 0.14 s | 18× |

About a third of the time on short inputs goes to making the rules into Python lists. `pysequitur.backend.grammar_size(tokens)` counts the grammar's symbols, `sum(len(r) for r in Sequencer3(tokens).get())`, without making them: 0.11 ms for the 2,400 ints.

## Basic usage

<pre><code>
from pysequitur import Sequencer3, print_grammar

input_string = open('samples/peaseporridge.txt', 'r').read()
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

a = Analysis.from_text(open('samples/iamsam.txt').read(), tokens='word')
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
| `shared_phrases` | The longest passages several documents have in common, and how much of each document also appears word for word in each other one. |
| `repetition_profile` | How much of each stretch of a document is repeated material: boilerplate, refrains, duplicated sections. |
| `get_grammar` | The grammar as text. |
| `render_visualization` | Writes the visualizer's report of an analysis as an HTML file (under `--root`) for a person to open. |
| `list_analyses` | The analyses the server holds. |

Use word tokens for prose, line tokens for code, logs and data files (they find duplicated blocks of lines), and character tokens for text without spaces. `samples/revelation.txt` is the Greek text of the Book of Revelation in lowercase Beta Code letters (`h` = η, `q` = θ, `w` = ω, ...) with no accents, punctuation or word spaces. Analysed by characters, it takes 0.1 s, and its longest repeats are built around the refrain "he that hath an ear, let him hear what the Spirit saith unto the churches", which the grammar finds as a phrase of its own: `oexwnousakousatwtitopneumalegeitaisekklhsiais`.

## Visualizer

`pysequitur-viz` shows what repeats in a text, where, and how the repeats nest:

<pre><code>
pysequitur-viz samples/iamsam.txt                          # open the app in a browser
pysequitur-viz samples/genesis1.txt samples/iamsam.txt     # several documents, and what they share
pysequitur-viz samples/revelation.txt --tokens char        # text without spaces
pysequitur-viz samples/iamsam.txt -o iamsam.html           # write a self-contained report
pysequitur-viz                                             # paste or open texts in the app
</code></pre>

The page has:

- the share of the text inside repeats, the number of repeated phrases, the longest repeat and the deepest nesting
- an arc diagram, where each band joins two consecutive occurrences of a repeated phrase and its width is the phrase's length
- how much of each stretch of the text is repeated
- the text with its repeated passages shaded: click anywhere to see the innermost phrase there, the phrases around it, what it is made of, and all of its occurrences
- a sortable, filterable table of the repeated phrases
- for several documents, how much of each also appears word for word in each other one, and their longest shared passages

The app runs on a local server at 127.0.0.1 and needs nothing beyond Python; a report is one HTML file with no external resources. Both have light and dark themes.

## Performance

Building the grammar, median of 3 runs on an Apple M4 Pro with Python 3.12:

| Implementation | genesis1.txt (2.5 KB) | iamsam.txt (3.5 KB) | revelation.txt (46.5 KB) |
|----------------|-----------------------|---------------------|--------------------------|
| Sequencer3     | 0.004 s               | 0.006 s             | 0.06 s                   |
| Sequencer      | 0.11 s                | 0.18 s              | 38.4 s                   |
| Sequencer2     | 0.22 s                | 0.32 s              | 67.6 s                   |

These are the Python engines; the compiled one is above. `Sequencer3` runs in linear time, about 600,000 tokens per second: 1.6 MB of Python source takes 2.5 s and 4.6 MB takes 7.6 s. `Sequencer` and `Sequencer2` compare symbols all the time, and a rule reference now compares itself in Python code so that the rule 2 is never mistaken for the number 2; that makes them about twice as slow as before.

[doc/performance.md](doc/performance.md) has charts of build time against input length, a comparison with ten other implementations in five languages, the correctness checks and the history of the library's performance. [doc/background.md](doc/background.md) collects the research on Sequitur and its uses, and [doc/substack/](doc/substack/) has the [article](https://markotmanninen.substack.com/p/giving-ai-agents-an-eye-for-repetition) with the scripts behind its images.

### Running benchmarks

<pre><code>
python benchmark.py samples/genesis1.txt Sequencer3
python benchmark.py samples/genesis1.txt samples/iamsam.txt samples/revelation.txt Sequencer3 Sequencer --runs 5
python benchmark.py samples/iamsam.txt --tokens word --json
</code></pre>

Give any number of input files and implementations (`Sequencer`, `Sequencer2`, `Sequencer3`; default `Sequencer3`, on the engine `PYSEQUITUR_BACKEND` chooses). Build is the time to stream the input in, resolve the time to extract the grammar and expand it back, and every run checks that the expansion equals the input.

## Tests

<pre><code>
python -m unittest discover -s tests -t .
</code></pre>

The tests check the grammar properties above (exact round trip, digram uniqueness, rule utility) for every implementation on the sample files, long runs of one symbol and seeded random inputs. When `pysequitur_rs` is installed, they also compare its grammars with the Python engine's, and `PYSEQUITUR_BACKEND=python` or `rust` runs the whole suite on one engine. The MCP server tests run when the `mcp` extra is installed, for example in a virtualenv with `pip install -e ".[mcp]"`, the visualizer tests run the page's own JavaScript in Node, when Node is installed, against the Python analysis, and with Jupyter installed (`pip install jupyter`) the notebook is run and its output compared with the output saved in it.
