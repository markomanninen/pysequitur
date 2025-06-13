#!/usr/bin/env python
import time
from pysequitur.main import Sequencer, Sequencer2, Sequencer3, Sequencer4

NUM_RUNS = 2
FILE_PATHS = ["genesis1.txt", "iamsam.txt", "peaseporridge.txt"]
SEQUENCER_CLASSES = [Sequencer, Sequencer2, Sequencer3, Sequencer4]

def main():
    print("Starting benchmarks...") # Added for debugging
    results = {}

    for file_path in FILE_PATHS:
        results[file_path] = {}
        try:
            with open(file_path, 'r') as f:
                input_content = f.read()
        except FileNotFoundError:
            print(f"Error: Input file not found at {file_path}")
            continue

        for sequencer_class in SEQUENCER_CLASSES:
            sequencer_name = sequencer_class.__name__
            total_duration = 0.0
            print(f"Benchmarking {sequencer_name} with {file_path} ({NUM_RUNS} runs)...")

            for i in range(NUM_RUNS):
                start_time = time.perf_counter()
                sequitur_instance = sequencer_class()
                for char_index, character in enumerate(input_content):
                    sequitur_instance.stream(character)
                end_time = time.perf_counter()
                duration = end_time - start_time
                total_duration += duration
                print(f"Run {i+1}: {duration:.4f} seconds")

            average_time = total_duration / NUM_RUNS
            results[file_path][sequencer_name] = average_time
            print(f"Average time for {sequencer_name} on {file_path}: {average_time:.4f} seconds\n")

    print("\n--- Preparing Consolidated Benchmark Report ---") # Added for debugging
    print(f"Results: {results}") # Added for debugging
    print("--- Consolidated Benchmark Report ---")
    header = f"{'File':<20}"
    for sequencer_class in SEQUENCER_CLASSES:
        header += f" | {sequencer_class.__name__:<15}"
    print(header)
    print("-" * len(header))

    for file_path in FILE_PATHS:
        row = f"{file_path:<20}"
        for sequencer_class in SEQUENCER_CLASSES:
            sequencer_name = sequencer_class.__name__
            avg_time = results.get(file_path, {}).get(sequencer_name, float('nan'))
            row += f" | {avg_time:<15.4f}"
        print(row)

if __name__ == "__main__":
    main()
