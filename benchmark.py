import os
import sys
import time

import psutil

# Ensure the project root is in the Python path
sys.path.insert(0, "/a0/usr/workdir/neuralmind")

from neuralmind.core import NeuralMind


def get_memory_usage():
    """Gets the peak memory usage of the current process and its children."""
    process = psutil.Process(os.getpid())
    peak_mem = process.memory_info().rss
    for child in process.children(recursive=True):
        try:
            peak_mem += child.memory_info().rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return peak_mem / (1024 * 1024)  # Convert to MB


def run_benchmark():
    """Runs a standardized benchmark and returns a dictionary of metrics."""
    print("--- Running Benchmark ---")

    project_path = "/a0/usr/workdir/neuralmind"
    test_query = "Trace the 'run_experiment' function in 'experiment.py' and explain how it modifies the 'CONTEXT_SELECTOR_PATH' file."

    start_time = time.time()

    # Initialize NeuralMind and run the query
    nm = NeuralMind(project_path)
    output = nm.query(test_query)

    elapsed_time = time.time() - start_time
    peak_mem = get_memory_usage()
    token_count = len(output.split())  # Approximate token count

    # Package results into a dictionary
    return {
        "time_sec": round(elapsed_time, 2),
        "memory_mb": round(peak_mem, 2),
        "tokens": token_count,
    }


if __name__ == "__main__":
    # Allow the script to be run directly for testing
    metrics = run_benchmark()
    print("\n--- Benchmark Results ---")
    print(f"Execution Time: {metrics['time_sec']} seconds")
    print(f"Peak Memory: {metrics['memory_mb']} MB")
    print(f"Approx. Output Tokens: {metrics['tokens']}")
