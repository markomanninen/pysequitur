"""
Times the Python port in Nevill-Manning's repository (Ravi Annaswamy, 2013) on a
file, then measures the grammar it built and expands it back:

    python bench_python_port.py vendor/python/sequitur.py FILE

The port is Python 2 and does not parse as published: its licence is plain text,
and it compares with <>. Both are patched here, and the self-test calls at the
end of the file are left out; the algorithm is untouched.
"""
import json
import sys
import time

source, path = sys.argv[1], sys.argv[2]
code = open(source).read()
code = code[code.index('class Rule'):].replace('<>', '!=').replace('\ntest()', '\n')
code += '''
def _build(text):
  global numRules, digrams
  first_rule = Rule(numRules)
  numRules += 1
  digrams = {}
  for c in text:
    first_rule.last().insert_after(Terminal(c))
    first_rule.last().p.check()
  return first_rule
'''
namespace = {}
exec(compile(code, source, 'exec'), namespace)
text = open(path, encoding='utf-8').read()
sys.setrecursionlimit(100000)

start = time.perf_counter()
root = namespace['_build'](text)
seconds = time.perf_counter() - start

seen, todo, symbols = {id(root)}, [root], 0
while todo:
    symbol = todo.pop().first()
    while not symbol.is_guard():
        symbols += 1
        if symbol.is_nonterminal() and id(symbol.r) not in seen:
            seen.add(id(symbol.r))
            todo.append(symbol.r)
        symbol = symbol.n
out, stack = [], [root.first()]
while stack and len(out) <= len(text):
    symbol = stack.pop()
    if symbol.is_guard():
        continue
    stack.append(symbol.n)
    if symbol.is_nonterminal():
        stack.append(symbol.r.first())
    else:
        out.append(symbol.value)
print(json.dumps({'seconds': round(seconds, 6), 'rules': len(seen) - 1, 'symbols': symbols,
                  'roundtrip': ''.join(out) == text}))
