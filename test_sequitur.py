#!/usr/bin/env python
try:
    from pysequitur.main import Sequencer
    print("Successfully imported Sequencer.")
    sequencer_instance = Sequencer()
    print("Successfully created Sequencer instance.")
except ImportError as e:
    print(f"Error importing Sequencer: {e}")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
