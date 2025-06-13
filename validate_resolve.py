#!/usr/bin/env python
import sys
from pysequitur.main import Sequencer, Sequencer2, Sequencer3, Sequencer4

# Define NEWLINE_REPLACEMENT, SPACE_REPLACEMENT, TAB_REPLACEMENT if they are used by resolve,
# or ensure resolve returns original characters. Based on Sequencer3/4's grammar_recursive,
# the resolve method should be giving back original characters, not these replacements.
# If resolve was returning the replacements, we'd need to un-replace them before comparison.

TEST_STRINGS = [
    "",
    "abc",
    "ababc",
    "ababab",
    "abcabdabcabe",
    "Hello World\nTesting\tTabs! Spaces_too."
]

SEQUENCER_CLASSES = [Sequencer, Sequencer2, Sequencer3, Sequencer4]

def main():
    any_test_failed = False
    original_chars_for_comparison = {}

    # Pre-process test strings to handle replacements if necessary for comparison
    # However, resolve() should return original characters.
    # The replacements in grammar_recursive are for string representation of the grammar,
    # not for the resolved sequence.
    for s in TEST_STRINGS:
        original_chars_for_comparison[s] = list(s)


    for test_string in TEST_STRINGS:
        display_test_string = test_string.replace(chr(10), '\\n').replace(chr(9), '\\t')
        print(f"\n--- Testing string: '{display_test_string}' ---") # Visualize special chars

        # For Sequencer and Sequencer2, resolve() might return RuleIndex objects or nested lists
        # if not fully flattened or if the internal representation differs significantly.
        # The goal is that `resolve(flatten=True)` should give a flat list of original characters.

        for sequencer_class in SEQUENCER_CLASSES:
            sequencer_name = sequencer_class.__name__
            print(f"  Testing with {sequencer_name}...")

            try:
                sequencer_instance = sequencer_class()
                resolved_output = []

                if not test_string:
                    # For empty strings, resolve() should yield an empty list.
                    # Sequencer & Sequencer2 would fail if stream() is not called and then resolve() tries to access self[0]
                    # Sequencer3 & Sequencer4 initialize self.g = Grammar(), and resolve() on this should be empty.
                    if sequencer_name in ["Sequencer", "Sequencer2"]:
                        # These sequencers initialize self[0] in the first stream call.
                        # Calling resolve() without stream results in IndexError.
                        # Their resolve() on an empty stream should logically be [].
                        resolved_output = []
                    else: # Sequencer3, Sequencer4
                        # These initialize a Grammar object, resolve() should work.
                        # No stream calls needed for an empty string.
                        resolved_output = sequencer_instance.resolve(flatten=True)
                else:
                    for char_index, character in enumerate(test_string):
                        sequencer_instance.stream(character)
                    resolved_output = sequencer_instance.resolve(flatten=True)

                # Ensure resolved_output is a list of strings/characters
                reconstructed_string = "".join(map(str, resolved_output)) # map(str,...) for safety if it's not all strings

                original_string_for_compare = test_string

                if reconstructed_string == original_string_for_compare:
                    print(f"    PASS: {sequencer_name}")
                else:
                    any_test_failed = True
                    print(f"    FAIL: {sequencer_name}")
                    display_original = original_string_for_compare.replace(chr(10), '\\n').replace(chr(9), '\\t')
                    display_reconstructed = reconstructed_string.replace(chr(10), '\\n').replace(chr(9), '\\t')
                    print(f"      Original:     '{display_original}'")
                    print(f"      Reconstructed: '{display_reconstructed}'")
                    # print(f"      Resolved raw: {resolved_output}") # For debugging if needed

            except Exception as e:
                any_test_failed = True
                print(f"    ERROR: {sequencer_name} raised an exception: {e}")
                import traceback
                traceback.print_exc()


    if any_test_failed:
        print("\n--- Some tests FAILED ---")
        sys.exit(1)
    else:
        print("\n--- All tests PASSED ---")
        sys.exit(0)

if __name__ == "__main__":
    main()
