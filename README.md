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
