# Python Sequitur (Nevill-Manning) algorithm (pysequitur)

For more information see: [Jupyter Notebook](https://github.com/markomanninen/pysequitur/blob/master/Python%20Sequitur%20Algorithms.ipynb) on GitHub or [Jupyter Notebook](http://nbviewer.jupyter.org/github/markomanninen/pysequitur/blob/master/Python%20Sequitur%20Algorithms.ipynb) on nbviewer.

## Note

Three different implementations of the algorithm are provided:

- array slicing method
- digram storage
- javascript port

Most robust in terms of efficiency is the last one.

## Basic usage

<pre><code>
from pysequitur import Sequencer3 as Sequencer

input_string = open('peaseporridge.txt', 'r').read()
s = Sequencer(input_string)
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

## Performance

Performance benchmarks were run comparing the three Sequitur implementations available in this repository: `Sequencer`, `Sequencer2`, and `Sequencer3`. `Sequencer3` (which utilizes the `pysequitur.sequiturpython` module) was found to be significantly faster.

### Benchmark Results

| Implementation | Input File     | Average Execution Time (seconds) | Notes                           |
|----------------|----------------|---------------------------------|---------------------------------|
| Sequencer      | genesis1.txt   | 0.1834                          | Baseline                        |
| Sequencer2     | genesis1.txt   | 0.5065                          |                                 |
| Sequencer3     | genesis1.txt   | 0.0731                          | Optimized/Recommended           |
| Sequencer      | revelation.txt | 37.7859                         | Baseline                        |
| Sequencer2     | revelation.txt | 138.9520                        |                                 |
| Sequencer3     | revelation.txt | 1.2384                          | Optimized/Recommended           |

*(Note: Times are based on a single run due to overall execution duration with larger files.)*

### Running Benchmarks

The `benchmark.py` script can be used to test the performance of the Sequitur implementations.
To run the script, use the following command structure:
```bash
python benchmark.py <input_file.txt> <SequencerVersion>
```
Replace `<input_file.txt>` with the path to an input text file (e.g., `genesis1.txt`, `revelation.txt`).
Replace `<SequencerVersion>` with one of `Sequencer`, `Sequencer2`, or `Sequencer3`.

Example:
```bash
python benchmark.py genesis1.txt Sequencer3
```
