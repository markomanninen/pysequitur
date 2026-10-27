"""
Scores a field test run against tasks/answers.json, and summarises its cost:

    python score.py runs/RUN
"""
import json
import re
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def answer_of(reply):
    """The last JSON object in a reply, preferring a ```json block."""
    blocks = re.findall(r'```(?:json)?\s*(\{.*?\})\s*```', reply, re.S)
    for candidate in reversed(blocks + re.findall(r'(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})', reply)):
        try:
            return json.loads(candidate)
        except ValueError:
            continue
    return None


def words(text):
    return re.findall(r"[a-z0-9]+", text.lower().replace('’', "'"))


def grade(task, answer, truth):
    if not isinstance(answer, dict):
        return {'correct': False}
    if task == 'refrain':
        passage = re.sub(r'\s', '', str(answer.get('passage', ''))).lower()
        exact = passage == truth['passage']
        # any 40 letters of the refrain also occur seven times; the full refrain is the longest
        right_passage = len(passage) >= 40 and passage in truth['passage']
        right_count = answer.get('occurrences') == truth['occurrences']
        return {'correct': right_passage and right_count, 'exact': exact and right_count}
    if task == 'duplicates':
        first, second = answer.get('first'), answer.get('second')
        try:
            got = sorted([list(map(int, first)), list(map(int, second))])
        except (TypeError, ValueError):
            return {'correct': False, 'exact': False}
        want = [truth['first'], truth['second']]
        near = all(abs(g - w) <= 2 for gs, ws in zip(got, want) for g, w in zip(gs, ws))
        return {'correct': near, 'exact': got == want}
    # copied: a reported passage matches when its start holds the true first three words, or its
    # end the true last three. A few words more or less at the edges are allowed, because the two
    # books can share them: a shared span may begin with the "again." before a copied paragraph.
    def holds(reported, wanted):
        return bool(reported and wanted) and any(reported[i:i + len(wanted)] == wanted for i in range(len(reported)))

    found, false = set(), 0
    for item in answer.get('passages') or []:
        if not isinstance(item, dict):
            continue
        first, last = words(str(item.get('first_words', ''))), words(str(item.get('last_words', '')))
        hit = None
        for k, p in enumerate(truth['passages']):
            true_first, true_last = words(p['first_words']), words(p['last_words'])
            if (holds(first, true_first[:3]) or holds(true_first, first[:3])
                    or holds(last, true_last[-3:]) or holds(true_last, last[-3:])):
                hit = k
                break
        if hit is None:
            false += 1
        else:
            found.add(hit)
    try:
        error = abs(float(answer.get('copied_percent')) - truth['copied_percent'])
    except (TypeError, ValueError):
        error = None
    return {'correct': len(found) == len(truth['passages']) and false == 0, 'found': len(found), 'false': false,
            'percent_error': error}


def main(run):
    run = Path(run)
    truths = json.loads((HERE / 'tasks' / 'answers.json').read_text())
    rows = []
    for result_file in sorted(run.glob('*/*/*/result.json')):
        run_dir = result_file.parent
        task, condition, model = run_dir.parent.parent.name, run_dir.parent.name, run_dir.name.rsplit('-', 1)[0]
        try:
            result = json.loads(result_file.read_text() or '{}')
        except ValueError:
            result = {}
        usage = result.get('usage', {})
        row = {'task': task, 'condition': condition, 'model': model, 'run': run_dir.name,
               'models_used': sorted(result.get('modelUsage', {})), 'turns': result.get('num_turns', 0),
               'input': usage.get('input_tokens', 0) + usage.get('cache_read_input_tokens', 0)
               + usage.get('cache_creation_input_tokens', 0),
               'output': usage.get('output_tokens', 0), 'cost': result.get('total_cost_usd', 0.0),
               'seconds': result.get('duration_ms', 0) / 1000, 'error': result.get('is_error', not result)}
        answer = answer_of(result.get('result', '') or '')
        row['answer'] = answer
        row.update(grade(task, answer, truths[task]))
        rows.append(row)
    (run / 'summary.json').write_text(json.dumps(rows, indent=1))

    print('| Task | Condition | Model | Runs | Correct | Exact | Tokens read | Tokens written | Turns | Cost $ | Seconds |')
    print('|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|')
    groups = {}
    for row in rows:
        groups.setdefault((row['task'], row['condition'], row['model']), []).append(row)
    for (task, condition, model), group in sorted(groups.items()):
        mean = lambda key: statistics.mean(r[key] for r in group)  # noqa: E731
        exact = sum(bool(r.get('exact')) for r in group) if task != 'copied' else '-'
        print('| %s | %s | %s | %d | %d | %s | %s | %s | %.1f | %.3f | %.0f |' % (
            task, condition, model, len(group), sum(bool(r['correct']) for r in group), exact,
            format(round(mean('input')), ','), format(round(mean('output')), ','), mean('turns'), mean('cost'),
            mean('seconds')))
    copied = [r for r in rows if r['task'] == 'copied']
    if copied:
        print()
        print('| Copied passages | Condition | Model | Found of 4 (each run) | False | Percent error |')
        print('|---|---|---|---|---|---|')
        for (task, condition, model), group in sorted(groups.items()):
            if task == 'copied':
                print('| | %s | %s | %s | %s | %s |' % (condition, model, ', '.join(str(r.get('found', 0)) for r in group),
                                                      ', '.join(str(r.get('false', 0)) for r in group),
                                                      ', '.join('-' if r.get('percent_error') is None
                                                                else '%.1f' % r['percent_error'] for r in group)))


if __name__ == '__main__':
    main(sys.argv[1])
