"""
Times pysequitur on a file, then measures the grammar it built and expands it back:

    python bench_pysequitur.py core FILE    # pysequitur.core, behind Sequencer3
    python bench_pysequitur.py rust FILE    # the compiled engine (pysequitur_rs) behind Sequencer3
    python bench_pysequitur.py port FILE    # pysequitur.sequiturpython, the older port

Put another checkout first on PYTHONPATH to measure it instead.
"""
import json
import sys
import time

mode, path = sys.argv[1], sys.argv[2]
text = open(path, encoding='utf-8').read()

if mode in ('core', 'rust'):
    if mode == 'core':
        from pysequitur.core import Grammar
    else:
        from pysequitur.backend import RustGrammar as Grammar
    start = time.perf_counter()
    grammar = Grammar(text)
    seconds = time.perf_counter() - start
    rules = grammar.rules()
    rules_seconds = time.perf_counter() - start - seconds
    symbols = sum(len(body) for body in rules)

    def expand(i, out):
        for x in rules[i]:
            if type(x).__name__ == 'RuleIndex':
                expand(int(x), out)
            else:
                out.append(x)
        return out
    sys.setrecursionlimit(100000)
    result = {'rules': len(rules) - 1, 'symbols': symbols, 'roundtrip': ''.join(expand(0, [])) == text,
              'rules_seconds': round(rules_seconds, 6)}
else:
    from pysequitur.sequiturpython.grammar import Grammar
    from pysequitur.sequiturpython.symbol import NonTerminal
    grammar = Grammar()
    start = time.perf_counter()
    grammar.train_string(text)
    seconds = time.perf_counter() - start
    root = grammar.root_production
    # the older port could leave a rule's list cyclic, so every walk is bounded
    seen, todo, symbols, bounded = {id(root)}, [root], 0, True
    while todo and bounded:
        symbol, steps = todo.pop().first(), 0
        while not symbol.is_guard():
            symbols += 1
            steps += 1
            if steps > len(text):
                bounded = False
                break
            if isinstance(symbol, NonTerminal) and id(symbol.rule) not in seen:
                seen.add(id(symbol.rule))
                todo.append(symbol.rule)
            symbol = symbol.next
    out, stack = [], [root.first()]
    while bounded and stack and len(out) <= len(text):
        symbol = stack.pop()
        if symbol.is_guard():
            continue
        stack.append(symbol.next)
        if isinstance(symbol, NonTerminal):
            stack.append(symbol.rule.first())
        else:
            out.append(symbol.terminal)
    result = {'rules': len(seen) - 1, 'symbols': symbols, 'roundtrip': bounded and ''.join(out) == text}

result['seconds'] = round(seconds, 6)
print(json.dumps(result))
