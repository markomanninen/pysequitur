import unittest
from .main import Sequencer, Sequencer2, Sequencer3, Sequencer4

class TestSequencerResolve(unittest.TestCase):

    TEST_STRINGS = [
        "",
        "abc",
        "ababc",
        "ababab",
        "abcabdabcabe",
        "Hello World\nTesting\tTabs! Spaces_too."
    ]

    SEQUENCER_CLASSES = [Sequencer, Sequencer2, Sequencer3, Sequencer4]

    def test_resolve_all_sequencers(self):
        for test_string in self.TEST_STRINGS:
            for sequencer_class in self.SEQUENCER_CLASSES:
                sequencer_name = sequencer_class.__name__
                # Pre-format the string for display in subTest message
                display_test_string = test_string.replace(chr(10), '\\n').replace(chr(9), '\\t')
                with self.subTest(msg=f"Testing {sequencer_name} with string: '{display_test_string}'"):

                    sequencer_instance = sequencer_class()
                    resolved_output = []

                    if not test_string:
                        if sequencer_name in ["Sequencer", "Sequencer2"]:
                            # These sequencers initialize self[0] in the first stream call.
                            # Calling resolve() without stream results in IndexError.
                            # Their resolve() on an empty stream should logically be [].
                            resolved_output = []
                        else: # Sequencer3, Sequencer4
                            resolved_output = sequencer_instance.resolve(flatten=True)
                    else:
                        for character in test_string:
                            sequencer_instance.stream(character)
                        resolved_output = sequencer_instance.resolve(flatten=True)

                    reconstructed_string = "".join(map(str, resolved_output))
                    self.assertEqual(reconstructed_string, test_string)

if __name__ == '__main__':
    unittest.main()
