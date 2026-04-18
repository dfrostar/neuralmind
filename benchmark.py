import os
import sys
import time
import psutil
from pathlib import Path

# Ensure the neuralmind package is in the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from neuralmind.core import NeuralMind

def get_memory_usage():
    """Get the peak memory usage of child processes."""
    process = psutil.Process(os.getpid())
    children = process.children(recursive=True)
    peak_mem = 0
    for child in children:
        try:
            mem_info = child.memory_info()
            peak_mem += mem_info.rss  # Resident Set Size
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return peak_mem / (1024 * 1024)  # Convert to MB

def run_benchmark():
    """Runs a standardized benchmark for NeuralMind performance."""
    print("--- Running Benchmark ---")
    
    PROJECT_PATH = "/a0/usr/workdir/neuralmind"
    TEST_QUERY = "Trace the 'run_experiment' function in 'experiment.py' and explain how it modifies the 'CONTEXT_SELECTOR_PATH' file."

    if not os.path.isdir(PROJECT_PATH):
        print(f"Error: Project path not found at {PROJECT_PATH}")
        return

    mind = NeuralMind(PROJECT_PATH)
    
    print(f"Project: {PROJECT_PATH}")
    print(f"Query: '{TEST_QUERY}'\n")

    start_time = time.time()
    
    # The query method now returns a simple string
    context_string = mind.query(TEST_QUERY)
    
    end_time = time.time()
    peak_memory_mb = get_memory_usage()
    execution_time = end_time - start_time
    
    print("--- Results ---")
    print(f"Execution Time: {execution_time:.2f} seconds")
    print(f"Peak Memory (Children): {peak_memory_mb:.2f} MB")
    
    # Estimate token count from the final string
    output_tokens = len(context_string.split())
    print(f"Approx. Output Tokens: {output_tokens}")
    
    print("\n--- Output Snippet ---")
    print(context_string[:500] + '...' if len(context_string) > 500 else context_string)

if __name__ == "__main__":
    run_benchmark()
