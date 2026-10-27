"""
Field test: Claude agents answer questions about texts, either with the text in
the prompt or with nothing but the pysequitur MCP tools.

    python make_tasks.py                                   # once
    python run_agents.py --repeats 3 --models haiku opus   # every run calls a model
    python score.py runs/RUN                               # again, to rescore a run

Needs the claude CLI and pysequitur-mcp (pip install -e ".[mcp]"). Claude Code's
own tools are switched off in every run, and no other MCP server is loaded.
"""
import argparse
import concurrent.futures
import datetime
import json
import shutil
import subprocess
from pathlib import Path

import score

HERE = Path(__file__).resolve().parent
TASKS = HERE / 'tasks'

QUESTIONS = {
    'refrain': (
        'the Greek text of the Book of Revelation, transliterated into Latin letters, in lowercase and without '
        'spaces or punctuation', ['revelation.txt'],
        'Which passage of at least 40 letters occurs the most times in the text? Give the passage exactly as it is '
        'written there, as long as it can be while it keeps that number of occurrences, and how many times it occurs.',
        '{"passage": "...", "occurrences": 0}'),
    'duplicates': (
        'a Python source file from the standard library', ['contextlib.py'],
        'Find the longest block of consecutive lines that appears twice, identically, in this file. Give the first '
        'and the last line number of each of its two copies.',
        '{"first": [0, 0], "second": [0, 0]}'),
    'copied': (
        'two documents, A and B', ['A.txt', 'B.txt'],
        'Some passages of document B were copied word for word from document A. Find every copied passage of at '
        'least 40 characters, and give the first five and the last five words of each. Also estimate what '
        'percentage of the characters of document B were copied from document A.',
        '{"passages": [{"first_words": "...", "last_words": "..."}], "copied_percent": 0}'),
}


def prompt(task, condition):
    description, files, question, answer = QUESTIONS[task]
    ending = 'End your answer with a JSON block like this one:\n```json\n%s\n```' % answer
    if condition == 'tool':
        names = ' and '.join(files)
        return ('The file%s %s %s %s. Use the pysequitur tools to answer; there is no other way to read the '
                'file%s.\n\n%s\n\n%s' % ('s' if len(files) > 1 else '', names, 'are' if len(files) > 1 else 'is',
                                       description, 's' if len(files) > 1 else '', question, ending))
    parts = ['Below %s %s.' % ('are' if len(files) > 1 else 'is', description)]
    for name in files:
        text = (TASKS / task / name).read_text()
        if name.endswith('.py'):  # numbered, as an agent's file reader shows it
            text = '\n'.join('%5d  %s' % (n, line) for n, line in enumerate(text.split('\n'), 1))
            parts.append('Its lines are numbered from 1.')
        label = name if len(files) == 1 else 'document %s' % name[0]
        parts.append('<%s>\n%s\n</%s>' % (label, text, label))
    return '\n\n'.join(parts[:1] + [question] + parts[1:] + [ending])


def run_one(run_dir, task, condition, model, server):
    run_dir.mkdir(parents=True)
    servers = {}
    if condition == 'tool':
        servers['pysequitur'] = {'type': 'stdio', 'command': server, 'args': ['--root', str(TASKS / task)]}
    (run_dir / 'mcp.json').write_text(json.dumps({'mcpServers': servers}))
    text = prompt(task, condition)
    (run_dir / 'prompt.txt').write_text(text)
    command = ['claude', '-p', text, '--model', model, '--tools', '', '--output-format', 'stream-json',
               '--verbose', '--strict-mcp-config', '--mcp-config', 'mcp.json']
    if condition == 'tool':
        command += ['--allowedTools', 'mcp__pysequitur']
    # the transcript shows which tools the agent called; its last event is the result
    with open(run_dir / 'transcript.jsonl', 'w') as out, open(run_dir / 'err.txt', 'w') as err:
        subprocess.run(command, cwd=run_dir, stdout=out, stderr=err, timeout=900)
    result = {}
    for line in (run_dir / 'transcript.jsonl').read_text().splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get('type') == 'result':
            result = event
    (run_dir / 'result.json').write_text(json.dumps(result))
    return run_dir


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--models', nargs='+', default=['haiku', 'opus'])
    parser.add_argument('--tasks', nargs='+', default=list(QUESTIONS))
    parser.add_argument('--conditions', nargs='+', default=['text', 'tool'])
    parser.add_argument('--parallel', type=int, default=6)
    args = parser.parse_args()
    server = shutil.which('pysequitur-mcp')
    if not server:
        parser.error('pysequitur-mcp is not on PATH; pip install -e ".[mcp]"')
    run = HERE / 'runs' / datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    jobs = [(run / task / condition / ('%s-%d' % (model, n)), task, condition, model)
            for task in args.tasks for condition in args.conditions for model in args.models
            for n in range(1, args.repeats + 1)]
    with concurrent.futures.ThreadPoolExecutor(args.parallel) as pool:
        for done in pool.map(lambda job: run_one(*job, server), jobs):
            print('done', done.relative_to(run), flush=True)
    score.main(run)


if __name__ == '__main__':
    main()
