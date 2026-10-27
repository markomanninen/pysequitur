# Background research

The research behind the article in [substack/](substack/): where Sequitur comes
from, what it has been used for, how it relates to other ways of finding
repetition, and which implementations exist. Sources were checked in October
2026. Those marked *(abstract)* or *(record)* were read only as an abstract
or a bibliographic record.

## Origins

Sequitur was published by Craig Nevill-Manning and Ian Witten of the
University of Waikato, New Zealand. It reads a sequence one symbol at a time
and keeps a grammar with two properties: no pair of adjacent symbols appears
more than once in the grammar, and every rule is used more than once. It runs
in time and space linear in the length of the input; in 1997 it processed
about 50,000 symbols a second.

- C.G. Nevill-Manning and I.H. Witten, [Identifying Hierarchical Structure in Sequences: A linear-time algorithm](https://arxiv.org/abs/cs/9709102), *Journal of Artificial Intelligence Research* 7:67–82, 1997. Demonstrations on Genesis in English, French and German (where it splits *begin+ning* and *commence+ment*), on word-class tags, and on Bach chorales.
- C.G. Nevill-Manning, [Inferring Sequential Structure](https://ml.cms.waikato.ac.nz/publications/1996/NevMan-Thesis.pdf), PhD thesis, University of Waikato, 1996. Compression on the Calgary corpus averaged 2.64 bits per character, against 3.64 for compress, 2.69 for gzip and 2.49 for PPM; on the King James Bible, 1.84 against 2.32 for gzip and 1.92 for PPM. In the Bach chorales a 50-interval rule revealed two harmonisations of the same 1524 melody by Walther. Rerunning Wolff's test of finding words in text without spaces, Sequitur found words sooner but formed more spurious phrases.
- *(record)* Nevill-Manning, Witten and Maulsby, [Compression by induction of hierarchical grammars](https://doi.org/10.1109/DCC.1994.305932), *Data Compression Conference* 1994, the first paper of the line; Nevill-Manning and Witten, [Linear-time, incremental hierarchy inference for compression](https://doi.org/10.1109/DCC.1997.581951), DCC 1997; [Compression and explanation using hierarchical grammars](https://researchcommons.waikato.ac.nz/handle/10289/1169), *The Computer Journal* 40(2/3), 1997.
- The algorithm's site is [sequitur.info](http://www.sequitur.info/), and the reference code is at [github.com/craignm/sequitur](https://github.com/craignm/sequitur).

## Theory

- Charikar, Lehman, Liu, Panigrahy, Prabhakaran, Sahai and shelat, [The Smallest Grammar Problem](https://scholar.archive.org/work/kkxmd4etnzahze4vi35kkhnwze), *IEEE Transactions on Information Theory* 51(7), 2005, credit Nevill-Manning and Witten, with Kieffer, Yang et al., with first stating the problem of finding the smallest grammar of a string. They bound how far greedy methods can be from the smallest grammar, and note that their lower bound for Kieffer and Yang's sequential algorithm extends to Sequitur.
- J.C. Kieffer and E.-H. Yang, [Grammar-based codes: a new class of universal lossless source codes](https://compression.ru/download/articles/grammar/kieffer_2000_grammar_based_codes.pdf), *IEEE Transactions on Information Theory* 46(3), 2000, prove that grammar-based codes are universal under mild conditions. Because Sequitur can keep two rules with the same expansion, they leave it "an open problem whether the SEQUITUR algorithm leads to a universal source code", and give a modified Sequitur that is.
- *(abstract)* Nevill-Manning and Witten, [Online and offline heuristics for inferring hierarchies of repetitions in sequences](https://researchcommons.waikato.ac.nz/handle/10289/1319), *Proceedings of the IEEE* 88(11), 2000, compare heuristics by the size of the grammar: offline ones that choose the most compressive or the most frequent repetition first beat the online Sequitur.
- *(abstract)* N.J. Larsson and A. Moffat, [Off-line dictionary-based compression](https://people.eng.unimelb.edu.au/ammoffat/abstracts/lm00procieee.html), *Proceedings of the IEEE* 88(11), 2000: Re-Pair, which repeatedly replaces the most frequent pair, also in linear time.

## Applications

- **Program traces.** J.R. Larus, [Whole Program Paths](https://people.cs.umass.edu/~emery/classes/cmpsci710-spring2003/p259-larus.pdf), PLDI 1999, compressed program path traces with a modified Sequitur into grammars 7.3 to 392.8 times smaller than the traces. T.M. Chilimbi, [Efficient Representations and Abstractions for Quantifying and Exploiting Data Reference Locality](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/12/locality_final.pdf), PLDI 2001, built "whole program streams" of memory references the same way.
- **Time series.** P. Senin et al., [Time series anomaly discovery with grammar-based compression](https://csdl.ics.hawaii.edu/techreports/2014/14-05/14-05.pdf), EDBT 2015, discretise a series into letters and find motifs and anomalies of any length with Sequitur; their [GrammarViz](https://github.com/GrammarViz2/grammarviz2_src) tool now uses Re-Pair by default.
- **Security.** T. Okumura and Y. Oyama, [Grammar Compression of Call Traces in Dynamic Malware Analysis](https://www.jstage.jst.go.jp/article/ipsjjip/25/0/25_229/_article), *Journal of Information Processing* 25, 2017: Sequitur and Re-Pair both beat gzip on API-call traces of malware. Microsoft ([US8069374B2](https://patents.google.com/patent/US8069374B2/en)) and NEC ([US10678625B2](https://patents.google.com/patent/US10678625B2/en)) hold patents that apply Sequitur to event logs.
- **DNA.** N. Cherniavsky and R. Ladner, [Grammar-based Compression of DNA Sequences](https://personal.broadinstitute.org/neva/publications/dnasequitur.pdf), 2004, extended Sequitur to reverse-complement repeats and concluded that grammar-based compression does not work well on DNA.
- **Music.** K. Sidorov, A. Jones and D. Marshall, [Music Analysis as a Smallest Grammar Problem](https://archives.ismir.net/ismir2014/paper/000226.pdf), ISMIR 2014, found smaller grammars of Bach chorales than Sequitur's; R. Perkins and D. Ventura, [Musical Phrase Segmentation via Grammatical Induction](https://arxiv.org/abs/2405.18742), IJCAI 2024, compare Sequitur with other grammar methods for phrase segmentation.
- **Words.** P. Cohen, N. Adams and B. Heeringa, [Voting Experts](https://www.cs.williams.edu/~heeringa/publications/voting-experts.pdf), *Intelligent Data Analysis* 11(6), 2007, segmented Orwell's *1984* without spaces with an F-score of 0.76, against 0.58 for Sequitur.
- **Learning.** R.T. Lange and A. Faisal, [Semantic RL with Action Grammars](https://arxiv.org/abs/1907.12477), 2019, inferred macro-actions for reinforcement learning with a Sequitur variant.

## Sequitur, Re-Pair and byte pair encoding

All three replace a repeated pair of adjacent symbols with a new symbol and so
build a hierarchy. Sequitur reads its input once and makes a rule as soon as any
pair repeats, without counting, and inlines rules used only once, so its rules
grow longer than pairs. Re-Pair and byte pair encoding count pairs first and
replace the most frequent one.

- P. Gage, [A New Algorithm for Data Compression](https://jacobfilipp.com/DrDobbs/articles/CUJ/1994/9402/gage/gage.htm), *C Users Journal* 12(2), 1994, introduced byte pair encoding as a compressor, the same year as the first Sequitur paper.
- R. Sennrich, B. Haddow and A. Birch, [Neural Machine Translation of Rare Words with Subword Units](https://aclanthology.org/P16-1162/), ACL 2016, turned it into a way to split words into subword units, learned from word frequencies and never across word boundaries; the ACL Anthology records its 2026 Test of Time Award, which calls it "the default tokenization method for most large language models". It cites Gage, not Sequitur: the two are siblings rather than parent and child.
- M. Gallé, [Investigating the Effectiveness of BPE: The Power of Shorter Sequences](https://aclanthology.org/D19-1141.pdf), EMNLP 2019, tried Sequitur against BPE as a tokenizer for translation.

## Arc diagrams

Arc diagrams of repetition are Martin Wattenberg's: the artwork
[The Shape of Song](https://www.bewitched.com/song.html) (2001), which drew
them for music, and the paper [Arc Diagrams: Visualizing Structure in
Strings](http://hint.fm/papers/arc-diagrams.pdf), IEEE InfoVis 2002. His arcs
join consecutive occurrences of maximal repeated substrings found with a suffix
tree, a repeat that occurs n times getting n−1 arcs. pysequitur's visualizer
draws its arcs from the occurrences of grammar rules instead.

## Other implementations

| Implementation | Language | Status | Notes |
|---|---|---|---|
| [craignm/sequitur](https://github.com/craignm/sequitur) `c++/` | C++ | last commit 2019 | The reference, by Nevill-Manning. Correct. |
| same repository, `javascript/` | JavaScript | 2019 | Written for a web page; the license text at the top is not commented out. Mis-handles runs of three equal symbols ([issue #3](https://github.com/craignm/sequitur/issues/3), open since 2017). |
| same repository, `java/` (Eibe Frank, 1997) | Java | 2012 fix | An applet without the handling of runs; builds different grammars. Also named in issue #3. |
| same repository, `python/` (Ravi Annaswamy, 2013) | Python 2 | – | Does not parse as published; patched to run, it crashes on Revelation. String digram keys can collide. |
| [jsdw/cpp-sequitur](https://github.com/jsdw/cpp-sequitur) | C++11 | 2018 | Templated over the symbol type. |
| [dylanjwolff/sequitur-rs](https://github.com/dylanjwolff/sequitur-rs) | Rust | 2026 | Mirrors jsdw's C++; also multi-document grammars. |
| [scikit-sequitur](https://pypi.org/project/scikit-sequitur/) (Grant Jenks) | Python, optional Cython | 0.4.0, 2021 | Any hashable symbols. |
| [mspandit/sequitur-python](https://github.com/mspandit/sequitur-python) | Python | 2016 | The port of the JavaScript that pysequitur's Sequencer3 came from. |
| [dgryski/go-sequitur](https://github.com/dgryski/go-sequitur) | Go | 2022 | |
| [jMotif/GI](https://github.com/jMotif/GI) | Java | 2026 | Sequitur and Re-Pair for time series; the base of GrammarViz. |
| gem [sequitur](https://rubygems.org/gems/sequitur) | Ruby | 2025 | |

There are also ports in C#, Haskell, Perl, Clojure, Dart, Swift, Ada and Object
Pascal. No other implementation found ships an MCP server, and the
visualizers found are the live demo on sequitur.info, GrammarViz for time
series, and a few D3 experiments.

The name `pysequitur` on PyPI belongs to an unrelated tool for file sequences,
and PyPI's similarity rules also block `py-sequitur`; `sequitur` belongs to an
autoencoder library. pysequitur installs from GitHub.
