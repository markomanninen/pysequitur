# -*- coding: utf-8 -*-
# file: mcp_server.py
"""
MCP server that lets agents analyse text with Sequitur grammars: which phrases
repeat, where they occur, how they nest, and what several documents share.

    pysequitur-mcp                          # files under the current directory
    pysequitur-mcp --root ~/notes --root /var/log

Needs the mcp extra: pip install "pysequitur[mcp]"
"""
import argparse
import itertools
import os
import re
from collections import OrderedDict
from typing import Annotated, List, Literal, Optional

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from .analysis import Analysis, PhraseMatches, Profile, RepeatList, RuleDetail, SharedPhrases, Summary

INSTRUCTIONS = """\
Sequitur finds every phrase that repeats in a text and arranges the repeats into a hierarchy (a grammar).

1. Call analyze with text, a file path or several documents. It returns an analysis_id and a summary:
   how much of the text is repeated, the phrases covering the most text, and the longest repeats.
2. Explore with the analysis_id:
   - list_repeats ranks and filters the repeated phrases
   - get_rule shows one phrase: its parts, the phrases around it and where it occurs
   - find_phrase tells where any phrase occurs and which repeats contain it
   - repetition_profile shows where in a document the repetition is
   - shared_phrases lists passages that several documents have in common
   - get_grammar prints the whole grammar

Tokens: 'word' (default) suits prose; 'line' suits code, logs and data, where it finds duplicated
blocks of lines; 'char' suits text without spaces and patterns inside words.
"""

Tokens = Annotated[Literal['word', 'line', 'char'], Field(
    description="'word' for prose, 'line' for code, logs and data, 'char' for text without spaces")]
AnalysisId = Annotated[str, Field(description='analysis_id returned by analyze')]
READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=False)


class DocumentInput(BaseModel):
    name: Optional[str] = Field(None, description='name to report the document by; defaults to the path')
    text: Optional[str] = Field(None, description='the text of the document')
    path: Optional[str] = Field(None, description='path of a UTF-8 text file to read instead of text')


class AnalysisInfo(TypedDict):
    analysis_id: str
    documents: List[str]
    tokenization: str
    tokens: int
    rules: int


class Store(object):
    """Analyses kept for follow-up queries; the least recently used is dropped first."""

    def __init__(self, capacity):
        self.capacity = capacity
        self.items = OrderedDict()
        self.serial = itertools.count(1)

    def add(self, analysis, name):
        slug = re.sub(r'[^a-z0-9]+', '-', os.path.basename(name).lower()).strip('-')[:32] or 'text'
        analysis.id = '%s-%d' % (slug, next(self.serial))
        self.items[analysis.id] = analysis
        while len(self.items) > self.capacity:
            self.items.popitem(last=False)
        return analysis

    def get(self, analysis_id):
        if analysis_id not in self.items:
            raise ToolError('Unknown analysis_id %r (known: %s). Call analyze first; the server keeps the %d most '
                            'recently used analyses.' % (analysis_id, ', '.join(self.items) or 'none', self.capacity))
        self.items.move_to_end(analysis_id)
        return self.items[analysis_id]


class Files(object):
    """Reads files under the allowed directories."""

    def __init__(self, roots):
        self.roots = [os.path.realpath(os.path.expanduser(root)) for root in roots]

    def read(self, path):
        path = os.path.expanduser(path)
        # a relative path is looked up in each allowed directory in turn
        candidates = [os.path.realpath(os.path.join(root, path)) for root in self.roots]
        allowed = [full for full in candidates
                   if any(os.path.commonpath([root, full]) == root for root in self.roots)]
        if not allowed:
            raise ToolError('%s is outside the directories this server may read (%s). Start the server with '
                            '--root to allow more.' % (path, ', '.join(self.roots)))
        for full in allowed:
            if os.path.isfile(full):
                with open(full, encoding='utf-8', errors='replace') as f:
                    return f.read()
        raise ToolError('No such file: %s' % ', '.join(sorted(set(allowed))))


def _query(method, *args, **kwargs):
    """Run an analysis query, reporting bad arguments to the agent."""
    try:
        return method(*args, **kwargs)
    except (KeyError, ValueError) as e:
        raise ToolError(e.args[0] if e.args else str(e))


def create_server(roots=None, max_chars=5000000, max_analyses=16):
    """An MCP server whose file reads are limited to roots (default: the current directory)."""
    server = MCPServer('pysequitur', instructions=INSTRUCTIONS)
    store = Store(max_analyses)
    files = Files(roots or [os.getcwd()])

    @server.tool(annotations=READ_ONLY)
    def analyze(
        text: Annotated[Optional[str], Field(description='text to analyse')] = None,
        path: Annotated[Optional[str], Field(description='path of a UTF-8 text file to analyse')] = None,
        documents: Annotated[Optional[List[DocumentInput]], Field(
            description='several documents to analyse together, to find what they share')] = None,
        tokens: Tokens = 'word',
        ignore_case: Annotated[bool, Field(description='treat upper and lower case as the same')] = False,
        name: Annotated[Optional[str], Field(description='name for the text and the analysis')] = None,
    ) -> Summary:
        """
        Find the repeated phrases of a text, a file or several documents. Give exactly one of text,
        path or documents. Returns an analysis_id for the other tools, with a summary: the share of
        the text inside repeats, the phrases that cover the most text, and the longest repeats.
        """
        given = [x for x in (text, path, documents) if x is not None]
        if len(given) != 1:
            raise ToolError('Give exactly one of text, path or documents.')
        if text is not None:
            sources = [(name or 'text', text)]
        elif path is not None:
            sources = [(name or path, files.read(path))]
        else:
            if not documents:
                raise ToolError('documents is empty.')
            sources = []
            for i, doc in enumerate(documents):
                if (doc.text is None) == (doc.path is None):
                    raise ToolError('Document %d needs exactly one of text or path.' % (i + 1))
                content = doc.text if doc.text is not None else files.read(doc.path)
                sources.append((doc.name or doc.path or 'document %d' % (i + 1), content))
        size = sum(len(content) for _, content in sources)
        if size > max_chars:
            raise ToolError('The input has %d characters; this server analyses at most %d (--max-chars).'
                            % (size, max_chars))
        analysis = Analysis(sources, tokens=tokens, ignore_case=ignore_case)
        store.add(analysis, name or (sources[0][0] if len(sources) == 1 else 'documents'))
        return analysis.summary()

    @server.tool(annotations=READ_ONLY)
    def list_repeats(
        analysis_id: AnalysisId,
        sort_by: Annotated[Literal['coverage', 'length', 'occurrences', 'depth'], Field(
            description='coverage: most text covered (characters × occurrences); length: longest; '
                        'occurrences: most frequent; depth: most nested')] = 'coverage',
        min_chars: Annotated[int, Field(ge=1, description='shortest phrase to list, in characters')] = 8,
        min_occurrences: Annotated[int, Field(ge=2, description='fewest occurrences to list')] = 2,
        contains: Annotated[Optional[str], Field(description='only phrases containing this text')] = None,
        document: Annotated[Optional[str], Field(description='only phrases occurring in this document')] = None,
        limit: Annotated[int, Field(ge=1, le=200)] = 15,
        offset: Annotated[int, Field(ge=0, description='skip this many, for paging')] = 0,
        max_text: Annotated[int, Field(ge=10, le=10000, description='cut longer phrases to this many characters')] = 200,
    ) -> RepeatList:
        """List the repeated phrases of an analysis, ranked and filtered, with counts and first positions."""
        return _query(store.get(analysis_id).repeats, sort_by=sort_by, min_chars=min_chars,
                      min_occurrences=min_occurrences, contains=contains, document=document,
                      limit=limit, offset=offset, max_text=max_text)

    @server.tool(annotations=READ_ONLY)
    def get_rule(
        analysis_id: AnalysisId,
        rule: Annotated[int, Field(ge=1, description='rule number from list_repeats, find_phrase or get_grammar')],
        max_positions: Annotated[int, Field(ge=0, le=500)] = 10,
        context_chars: Annotated[int, Field(ge=0, le=500, description='text to show around each position')] = 40,
        max_text: Annotated[int, Field(ge=10, le=100000)] = 500,
    ) -> RuleDetail:
        """
        One repeated phrase in detail: its parts (literal text and nested repeats), the longer repeats
        that contain it, its occurrences per document, and its positions with line, column and context.
        """
        return _query(store.get(analysis_id).rule, rule, max_positions=max_positions, context=context_chars,
                      max_text=max_text)

    @server.tool(annotations=READ_ONLY)
    def find_phrase(
        analysis_id: AnalysisId,
        phrase: Annotated[str, Field(min_length=1, description='exact text to look for')],
        max_positions: Annotated[int, Field(ge=0, le=500)] = 10,
        context_chars: Annotated[int, Field(ge=0, le=500)] = 40,
    ) -> PhraseMatches:
        """
        Where a phrase occurs, whether it is itself a repeat (exact_rule), and which repeats contain
        its occurrences. Use it to place any text in the structure of the documents.
        """
        return _query(store.get(analysis_id).find, phrase, max_positions=max_positions, context=context_chars)

    @server.tool(annotations=READ_ONLY)
    def shared_phrases(
        analysis_id: AnalysisId,
        min_documents: Annotated[int, Field(ge=2, description='fewest documents a phrase must occur in')] = 2,
        min_chars: Annotated[int, Field(ge=1)] = 20,
        limit: Annotated[int, Field(ge=1, le=200)] = 20,
    ) -> SharedPhrases:
        """
        For an analysis of several documents: the longest passages they have in common, and for each
        pair of documents the share of one's text that also occurs in the other.
        """
        return _query(store.get(analysis_id).shared, min_documents=min_documents, min_chars=min_chars,
                      limit=limit)

    @server.tool(annotations=READ_ONLY)
    def repetition_profile(
        analysis_id: AnalysisId,
        document: Annotated[Optional[str], Field(description='document name; default the first')] = None,
        segments: Annotated[int, Field(ge=1, le=500)] = 20,
    ) -> Profile:
        """
        Split a document into equal stretches and report how much of each is repeated material,
        to locate boilerplate, refrains or duplicated sections.
        """
        return _query(store.get(analysis_id).profile, document, segments=segments)

    @server.tool(annotations=READ_ONLY)
    def get_grammar(
        analysis_id: AnalysisId,
        max_rules: Annotated[int, Field(ge=0, le=5000)] = 50,
        max_line_chars: Annotated[int, Field(ge=20, le=10000)] = 200,
    ) -> str:
        """
        The grammar as text. S is the whole input, R<n> are the repeats with their occurrence counts,
        quoted strings are literal text, and | separates documents.
        """
        return store.get(analysis_id).grammar_text(max_rules=max_rules, max_line=max_line_chars)

    @server.tool(annotations=READ_ONLY)
    def list_analyses() -> List[AnalysisInfo]:
        """The analyses this server holds, most recently used last."""
        return [AnalysisInfo(analysis_id=a.id, documents=[d.name for d in a.documents],
                             tokenization=a.tokenization, tokens=sum(d.count for d in a.documents),
                             rules=len(a.rules) - 1)
                for a in store.items.values()]

    return server


def main(argv=None):
    parser = argparse.ArgumentParser(prog='pysequitur-mcp', description='Sequitur text analysis over MCP (stdio).')
    parser.add_argument('--root', action='append', metavar='DIR',
                        help='directory whose files may be analysed; repeat for more (default: current directory)')
    parser.add_argument('--max-chars', type=int, default=5000000, help='largest input to analyse, in characters')
    parser.add_argument('--max-analyses', type=int, default=16, help='analyses to keep for follow-up queries')
    args = parser.parse_args(argv)
    create_server(args.root, args.max_chars, args.max_analyses).run('stdio')


if __name__ == '__main__':
    main()
