//! Times dylanjwolff's sequitur-rs on a file, then measures the grammar it built and
//! expands it back. fetch.sh copies this into the crate's examples and builds it with
//! `cargo build --release --example bench`. This is its examples/main.rs with a timer.
use sequitur_rs::Sequitur;
use std::time::Instant;

fn main() {
    let path = std::env::args().nth(1).expect("usage: bench FILE");
    let bytes = std::fs::read(&path).expect("cannot read the file");

    let start = Instant::now();
    let mut seq = Sequitur::new();
    for &byte in &bytes {
        seq.push(byte);
    }
    let seconds = start.elapsed().as_secs_f64();

    let same = seq.iter().copied().eq(bytes.iter().copied());
    let stats = seq.stats();
    println!(
        "{{\"seconds\": {:.6}, \"rules\": {}, \"symbols\": {}, \"roundtrip\": {}}}",
        seconds,
        stats.num_rules - 1,
        stats.grammar_symbols,
        same
    );
}
