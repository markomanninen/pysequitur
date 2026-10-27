#!/bin/sh
# Fetches and builds the other Sequitur implementations that compare.py runs, into vendor/.
# Needs git, a C++ compiler, a JDK and Node. Nothing in vendor/ is committed.
set -e
cd "$(dirname "$0")"
mkdir -p vendor

# Craig Nevill-Manning's repository: the C++ reference, and the Java, JavaScript
# and Python versions kept with it
if [ ! -d vendor/sequitur ]; then
  git clone -q https://github.com/craignm/sequitur.git vendor/sequitur
fi
git -C vendor/sequitur checkout -q b6afb6e
make -s -C vendor/sequitur/c++ sequitur

# the Java port is an applet; Bench.java runs it from the command line
mkdir -p vendor/java
javac -nowarn -Xlint:none -d vendor/java vendor/sequitur/java/*.java Bench.java 2>/dev/null

# jsdw's C++11 version, templated over the symbol type
if [ ! -d vendor/cpp-sequitur ]; then
  git clone -q https://github.com/jsdw/cpp-sequitur.git vendor/cpp-sequitur
fi
git -C vendor/cpp-sequitur checkout -q a27a5d1
clang++ -std=c++11 -O2 -w -I vendor/cpp-sequitur -o vendor/bench_jsdw bench_jsdw.cpp vendor/cpp-sequitur/sequitur/*.cpp

# dylanjwolff's Rust version
if [ ! -d vendor/sequitur-rs ]; then
  git clone -q https://github.com/dylanjwolff/sequitur-rs.git vendor/sequitur-rs
fi
git -C vendor/sequitur-rs checkout -q 796d568
cp bench_rs.rs vendor/sequitur-rs/examples/bench.rs
(cd vendor/sequitur-rs && cargo build -q --release --example bench)

# scikit-sequitur from PyPI, as pure Python and compiled with Cython
for build in pure cython; do
  if [ ! -d vendor/venv-sksequitur-$build ]; then
    python3 -m venv vendor/venv-sksequitur-$build
    if [ $build = cython ]; then
      vendor/venv-sksequitur-$build/bin/pip install -q cython setuptools wheel
      vendor/venv-sksequitur-$build/bin/pip install -q --no-build-isolation --no-cache-dir scikit-sequitur==0.4.0
    else
      vendor/venv-sksequitur-$build/bin/pip install -q --no-cache-dir scikit-sequitur==0.4.0
    fi
  fi
done

# pysequitur as it was before the fixes, from this repository's history
if [ ! -d vendor/pysequitur-71a9298 ]; then
  mkdir -p vendor/pysequitur-71a9298
  git -C ../.. archive 71a9298 pysequitur | tar -x -C vendor/pysequitur-71a9298
fi
echo "built in $(pwd)/vendor"
