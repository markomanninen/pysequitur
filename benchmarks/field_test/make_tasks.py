"""
Builds the field test's three tasks in tasks/, with their answers computed
exactly, without Sequitur:

    python make_tasks.py

- refrain: the Greek text of Revelation without spaces; which passage of at
  least 40 letters occurs most often
- duplicates: contextlib.py from the running Python's standard library; the
  longest block of lines that occurs twice
- copied: part of Through the Looking-Glass with four paragraphs of Alice's
  Adventures in Wonderland inserted; which passages were copied, and how much
"""
import hashlib
import json
import shutil
import sys
import sysconfig
import urllib.request
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASKS = HERE / 'tasks'
ROOT = HERE.parent.parent
GUTENBERG = 'https://www.gutenberg.org/cache/epub/%d/pg%d.txt'


def gutenberg(number):
    cache = TASKS / ('pg%d.txt' % number)
    if not cache.exists():
        with urllib.request.urlopen(GUTENBERG % (number, number), timeout=60) as response:
            cache.write_bytes(response.read())
    text = cache.read_text(encoding='utf-8-sig').replace('\r\n', '\n')
    start = text.index('\n', text.index('*** START OF')) + 1
    return text[start:text.index('*** END OF')].strip() + '\n'


def occurrences(text, passage):
    count, i = 0, text.find(passage)
    while i >= 0:
        count += 1
        i = text.find(passage, i + 1)
    return count


def most_repeated(text, minimum):
    """The passage of at least minimum characters that occurs most often, grown while its count holds."""
    passage = Counter(text[i:i + minimum] for i in range(len(text) - minimum + 1)).most_common(1)[0][0]
    count = occurrences(text, passage)
    grown = True
    while grown:
        grown = False
        starts = [i for i in range(len(text)) if text.startswith(passage, i)]
        for candidate in {text[i - 1:i + len(passage)] for i in starts if i} | \
                         {text[i:i + len(passage) + 1] for i in starts if i + len(passage) < len(text)}:
            if occurrences(text, candidate) == count:
                passage, grown = candidate, True
                break
    return passage, count, [i for i in range(len(text)) if text.startswith(passage, i)]


def longest_duplicate_block(lines):
    """The longest run of lines found twice without overlapping: (length, first start, second start), 1-based."""
    n, best, previous = len(lines), (0, 0, 0), [0] * (len(lines) + 1)
    for i in range(1, n + 1):
        current = [0] * (n + 1)
        for j in range(i + 1, n + 1):
            if lines[i - 1] == lines[j - 1]:
                current[j] = min(previous[j - 1] + 1, j - i)
                if current[j] > best[0]:
                    best = (current[j], i - current[j] + 1, j - current[j] + 1)
        previous = current
    return best


def shared_passages(a, b, n=40):
    """Spans of b, as (start, end), covered by passages of n characters that also occur in a."""
    grams = {a[i:i + n] for i in range(len(a) - n + 1)}
    spans = []
    for p in range(len(b) - n + 1):
        if b[p:p + n] in grams:
            if spans and spans[-1][1] >= p:
                spans[-1][1] = p + n
            else:
                spans.append([p, p + n])
    return spans


def main():
    if TASKS.exists():
        for child in TASKS.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
    TASKS.mkdir(exist_ok=True)
    answers = {}

    folder = TASKS / 'refrain'
    folder.mkdir()
    text = (ROOT / 'samples' / 'revelation.txt').read_text()
    (folder / 'revelation.txt').write_text(text)
    passage, count, starts = most_repeated(text, 40)
    answers['refrain'] = {'passage': passage, 'occurrences': count, 'offsets': starts}

    folder = TASKS / 'duplicates'
    folder.mkdir()
    source = Path(sysconfig.get_paths()['stdlib']) / 'contextlib.py'
    code = source.read_text()
    (folder / 'contextlib.py').write_text(code)
    length, first, second = longest_duplicate_block(code.split('\n'))
    answers['duplicates'] = {'first': [first, first + length - 1], 'second': [second, second + length - 1],
                             'lines': length, 'python': sys.version.split()[0],
                             'sha256': hashlib.sha256(code.encode()).hexdigest()}

    folder = TASKS / 'copied'
    folder.mkdir()
    alice = gutenberg(11)
    looking_glass = gutenberg(12)
    a = alice[alice.index('CHAPTER I.\nDown the Rabbit-Hole'):]
    a = a[:a.index('CHAPTER IV.')]
    b_paragraphs = looking_glass[looking_glass.index('CHAPTER I.\nLooking-Glass house'):].split('\n\n')[:40]
    # the first paragraph of A in each length range is copied into B, at evenly spread places
    a_paragraphs = [p for p in a.split('\n\n') if '\n' in p or len(p) > 80]
    copied = []
    for low, high in ((120, 220), (250, 400), (450, 650), (700, 1100)):
        copied.append(next(p for p in a_paragraphs if low <= len(p) <= high and p not in copied))
    for k, paragraph in enumerate(copied):
        b_paragraphs.insert(6 + 9 * k, paragraph)
    b = '\n\n'.join(b_paragraphs) + '\n'
    (folder / 'A.txt').write_text(a)
    (folder / 'B.txt').write_text(b)
    spans = shared_passages(a, b)
    found = [b[s:e] for s, e in spans]
    assert all(any(p in f for f in found) for p in copied), 'a copied passage is not found whole'
    assert len(found) == len(copied), 'the books share more than the copied paragraphs: %r' % found
    answers['copied'] = {'passages': [{'first_words': ' '.join(p.split()[:5]), 'last_words': ' '.join(p.split()[-5:]),
                                       'chars': len(p)} for p in copied],
                         'copied_percent': round(100 * sum(e - s for s, e in spans) / len(b), 1),
                         'a_chars': len(a), 'b_chars': len(b)}

    (TASKS / 'answers.json').write_text(json.dumps(answers, indent=1))
    print(json.dumps(answers, indent=1))


if __name__ == '__main__':
    main()
