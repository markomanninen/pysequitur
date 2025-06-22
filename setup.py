from setuptools import setup, Extension
from Cython.Build import cythonize
import os

# Define the extension modules
extensions = [
    Extension(
        "pysequitur.sequiturpython.symbol",
        [os.path.join("pysequitur", "sequiturpython", "symbol.pyx")],
    ),
    Extension(
        "pysequitur.sequiturpython.grammar",
        [os.path.join("pysequitur", "sequiturpython", "grammar.pyx")],
    ),
    Extension(
        "pysequitur.sequiturpython.rule",
        [os.path.join("pysequitur", "sequiturpython", "rule.pyx")],
    ),
]

setup(
    name="pysequitur_cythonized",
    ext_modules=cythonize(extensions, compiler_directives={'language_level' : "3"}),
)
