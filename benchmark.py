import argparse
import time
from pysequitur.main import Sequencer, Sequencer2, Sequencer3

NUM_RUNS = 1

def main():
    parser = argparse.ArgumentParser(description="Benchmark different Sequitur versions.")
    parser.add_argument("input_file_path", help="Path to the input file.")
    parser.add_argument("sequitur_version", choices=['Sequencer', 'Sequencer2', 'Sequencer3'], help="Sequitur version to use.")
    args = parser.parse_args()

    try:
        with open(args.input_file_path, 'r') as f:
            input_content = f.read()
    except FileNotFoundError:
        print(f"Error: Input file not found at {args.input_file_path}")
        return

    sequitur_class = None
    if args.sequitur_version == 'Sequencer':
        sequitur_class = Sequencer
    elif args.sequitur_version == 'Sequencer2':
        sequitur_class = Sequencer2
    elif args.sequitur_version == 'Sequencer3':
        sequitur_class = Sequencer3
    else:
        # This case should ideally be caught by argparse choices, but as a fallback:
        print(f"Error: Invalid Sequitur version '{args.sequitur_version}'. Choose from 'Sequencer', 'Sequencer2', 'Sequencer3'.")
        return

    total_duration = 0.0
    print(f"Benchmarking {args.sequitur_version} with {args.input_file_path} ({NUM_RUNS} runs)...")

    for i in range(NUM_RUNS):
        start_time = time.perf_counter()

        sequitur_instance = sequitur_class()
        for char_index, character in enumerate(input_content):
            sequitur_instance.stream(character)
            # Optional: print progress for very long inputs
            # if (char_index + 1) % 10000 == 0:
            #     print(f"Run {i+1}/{NUM_RUNS}, Processed {char_index + 1}/{len(input_content)} chars")

        end_time = time.perf_counter()
        duration = end_time - start_time
        total_duration += duration
        print(f"Run {i+1}: {duration:.4f} seconds")

    average_time = total_duration / NUM_RUNS

    print("\n--- Benchmark Results ---")
    print(f"Input File:     {args.input_file_path}")
    print(f"Sequitur Version: {args.sequitur_version}")
    print(f"Number of Runs: {NUM_RUNS}")
    print(f"Average Time:   {average_time:.4f} seconds")

if __name__ == "__main__":
    main()
