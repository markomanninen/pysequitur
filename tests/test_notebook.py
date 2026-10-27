"""The notebook runs, and prints what it printed when its outputs were saved in 2016."""
import os
import unittest

try:
    import nbformat
    from nbclient import NotebookClient
except ImportError:  # Jupyter is not installed
    nbformat = None

from .support import ROOT

NOTEBOOK = os.path.join(ROOT, 'Python Sequitur Algorithms.ipynb')


def printed(cell):
    out = []
    for output in cell.get('outputs', []):
        if 'text' in output:
            out.append(output['text'])
        elif 'text/plain' in output.get('data', {}):
            out.append(output['data']['text/plain'])
    return ''.join(out)


@unittest.skipIf(nbformat is None, 'Jupyter (nbclient) is not installed')
class TestNotebook(unittest.TestCase):

    def test_outputs_match_the_saved_ones(self):
        saved = nbformat.read(NOTEBOOK, as_version=4)
        notebook = nbformat.read(NOTEBOOK, as_version=4)
        compared = []
        for i, cell in enumerate(notebook.cells):
            if cell.cell_type != 'code':
                continue
            if cell.source.startswith('%%timeit'):
                cell.source = 'pass'  # timings differ on every machine
                continue
            # the animated demos pause between frames; the random one prints random data
            cell.source = cell.source.replace('delay = 0.5', 'delay = 0')
            if cell.source.strip() == 'test_random_seq()':
                cell.source = 'test_random_seq(delay=0)'
            else:
                compared.append(i)
        NotebookClient(notebook, timeout=120, kernel_name='python3',
                       resources={'metadata': {'path': ROOT}}).execute()
        for i in compared:
            with self.subTest(cell=i):
                self.assertEqual(printed(notebook.cells[i]), printed(saved.cells[i]))


if __name__ == '__main__':
    unittest.main()
