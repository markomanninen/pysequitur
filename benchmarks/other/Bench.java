import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayDeque;
import java.util.Deque;
import java.util.IdentityHashMap;
import java.util.Locale;
import java.util.Map;

/**
 * Times Eibe Frank's Java port of Sequitur on a file, then measures the grammar it
 * built and expands it back: java -cp vendor/java Bench FILE
 *
 * The port is an applet; this does what its runSequitur() does, without the window.
 */
public class Bench {

  public static void main(String[] args) throws Exception {
    String text = new String(Files.readAllBytes(Paths.get(args[0])), StandardCharsets.UTF_8);
    long start = System.nanoTime();
    rule.numRules = 0;
    symbol.theDigrams.clear();
    rule first = new rule();
    for (int i = 0; i < text.length(); i++) {
      first.last().insertAfter(new terminal(text.charAt(i)));
      first.last().p.check();
    }
    double seconds = (System.nanoTime() - start) / 1e9;

    Map<rule, Boolean> seen = new IdentityHashMap<>();
    Deque<rule> todo = new ArrayDeque<>();
    seen.put(first, true);
    todo.push(first);
    long symbols = 0;
    while (!todo.isEmpty()) {
      rule r = todo.pop();
      for (symbol s = r.first(); !s.isGuard(); s = s.n) {
        symbols++;
        if (s.isNonTerminal() && seen.put(((nonTerminal) s).r, true) == null) {
          todo.push(((nonTerminal) s).r);
        }
      }
    }
    boolean same = expand(first, text.length()).equals(text);
    System.out.printf(Locale.ROOT, "{\"seconds\": %.6f, \"rules\": %d, \"symbols\": %d, \"roundtrip\": %b}%n",
                      seconds, seen.size() - 1, symbols, same);
  }

  // the text a rule stands for, cut short past limit characters in case the grammar loops
  static String expand(rule root, int limit) {
    StringBuilder out = new StringBuilder();
    Deque<symbol> stack = new ArrayDeque<>();
    stack.push(root.first());
    while (!stack.isEmpty() && out.length() <= limit) {
      symbol s = stack.pop();
      if (s.isGuard()) {
        continue;
      }
      stack.push(s.n);
      if (s.isNonTerminal()) {
        stack.push(((nonTerminal) s).r.first());
      } else {
        out.append((char) s.value);
      }
    }
    return out.toString();
  }
}
