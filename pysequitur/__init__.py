#!/usr/local/bin/python
# -*- coding: utf-8 -*-
# file: __init__.py

try:
    from .main import Sequencer, Sequencer2, print_grammar, \
					  RULE_INDEX_STR, SEQUENCE_KEY, ARROW, \
					  NEWLINE_REPLACEMENT, SPACE_REPLACEMENT
except:
	from main import Sequencer, Sequencer2, print_grammar, \
					 RULE_INDEX_STR, SEQUENCE_KEY, ARROW, \
					 NEWLINE_REPLACEMENT, SPACE_REPLACEMENT
"""
exporting:
- Sequencer
- Sequencer2
- print_grammar
- RULE_INDEX_STR
- SEQUENCE_KEY
- ARROW
- NEWLINE_REPLACEMENT
- SPACE_REPLACEMENT
"""
