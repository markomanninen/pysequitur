// Times the JavaScript Sequitur from Nevill-Manning's repository on a file, then
// measures the grammar it built and expands it back:
//   node bench_js.js vendor/javascript/main.js FILE
//
// The file is written for a web page: it starts with its licence as plain text,
// which is not JavaScript, and its main() reads the input with jQuery. Here the
// licence is turned into a comment and the input is fed as main() feeds it, by
// index instead of by Array.shift(), which would make the loop quadratic.
// It runs in its own context, because it defines a function called Symbol.
const fs = require('fs');
const vm = require('vm');

const [source, file] = process.argv.slice(2);
let code = fs.readFileSync(source, 'utf8');
const start = code.indexOf('function Rule()');
code = '/*' + code.slice(0, start).replace(/\*\//g, '* /') + '*/\n' + code.slice(start);

const context = vm.createContext({ text: fs.readFileSync(file, 'utf8'), now: () => process.hrtime.bigint() });
vm.runInContext(code, context);
const result = vm.runInContext(`
  (function () {
    var started = now();
    digramIndex = {};
    var S = new Rule();
    for (var i = 0; i < text.length; i++) {
      S.last().insertAfter(new Symbol(text[i]));
      if (i) S.last().getPrev().check();
    }
    var seconds = Number(now() - started) / 1e9;

    var seen = new Set([S]), todo = [S], symbols = 0;
    while (todo.length) {
      var rule = todo.pop();
      for (var s = rule.first(); !s.isGuard(); s = s.next) {
        symbols++;
        if (s.rule && !seen.has(s.rule)) { seen.add(s.rule); todo.push(s.rule); }
      }
    }
    // expand iteratively, cut short past the input's length in case the grammar loops
    var out = [], length = 0, stack = [S.first()];
    while (stack.length && length <= text.length) {
      var t = stack.pop();
      if (t.isGuard()) continue;
      stack.push(t.next);
      if (t.rule) stack.push(t.rule.first());
      else { out.push(t.terminal); length++; }
    }
    return { seconds: seconds, rules: seen.size - 1, symbols: symbols, roundtrip: out.join('') === text };
  })()
`, context);
console.log(JSON.stringify(result));
