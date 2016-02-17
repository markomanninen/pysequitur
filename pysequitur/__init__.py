#!/usr/local/bin/python
# -*- coding: utf-8 -*-
# file: __init__.py

try:
    from .main import Sequencer, Sequencer2, print_grammar
except:
	from main import Sequencer, Sequencer2, print_grammar

"""
exporting:
- Sequencer
- Sequencer2
- print_grammar
"""
