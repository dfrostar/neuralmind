import subprocess
import re
import os

# --- Configuration ---
TARGET_FILE_PATH = "/a0/usr/workdir/neuralmind/neuralmind/core.py"
BENCHMARK_SCRIPT_PATH = "/a0/usr/workdir/neuralmind/benchmark.py"
RESULTS_FILE_PATH = "/a0/usr/workdir/neuralmind/optimization/results.tsv"
PYTHON_EXECUTABLE = "/a0/usr/workdir/neuralmind/.venv/bin/python"

# Define the experiments to run
EXPERIMENTS = {
    "baseline_v3": "baseline",
    "tight_budget_v2": {"n": 5},
    "generous_budget_v2": {"n": 25},
}


def modify_file(params):
    """Temporarily modifies the target file with new parameters."""
    with open(TARGET_FILE_PATH, "r") as f:
        original_content = f.read()

    modified_content = original_content
    for key, value in params.items():
        # This regex looks for 'searcher.search(..., n=some_number, ...)'
        pattern = re.compile(f"(searcher\\.search\\(.*n=)\\d+(.*\\))")
        replacement = f"\\g<1>{value}\\g<2>"
        modified_content, count = re.subn(pattern, replacement, modified_content)
        if count == 0:
            print(f"Warning: Parameter {key} not found in {TARGET_FILE_PATH}")

    with open(TARGET_FILE_PATH, "w") as f:
        f.write(modified_content)

    return original_content


def run_benchmark():
    """Runs the benchmark script and captures its output."""
    try:
        result = subprocess.run(
            [PYTHON_EXECUTABLE, BENCHMARK_SCRIPT_PATH], capture_output=True, text=True, check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"--- EXPERIMENT FAILED: Benchmark script returned a non-zero exit code. ---")
        print(e.stderr)
        return None


def parse_metrics(output):
    """Parses the benchmark output to extract key metrics."""
    metrics = {}
    try:
        metrics["time_sec"] = float(re.search(r"Execution Time: ([\d.]+) seconds", output).group(1))
        metrics["memory_mb"] = float(re.search(r"Peak Memory: ([\d.]+) MB", output).group(1))
        metrics["tokens"] = int(re.search(r"Approx. Output Tokens: (\d+)", output).group(1))
    except (AttributeError, ValueError) as e:
        print(f"Error parsing metrics: {e}")
        return None
    print(f"--- Metrics Extracted: {metrics} ---")
    return metrics


def log_results(experiment_name, params, metrics):
    """Logs the results of an experiment to a TSV file."""
    if not os.path.exists(RESULTS_FILE_PATH):
        with open(RESULTS_FILE_PATH, "w") as f:
            f.write("Experiment\tParameters\tTime_sec\tMemory_MB\tTokens\n")

    with open(RESULTS_FILE_PATH, "a") as f:
        param_str = str(params) if params != "baseline" else "baseline"
        f.write(
            f'{experiment_name}\t{param_str}\t{metrics["time_sec"]}\t{metrics["memory_mb"]}\t{metrics["tokens"]}\n'
        )
    print(f"Results logged to {RESULTS_FILE_PATH}")


def run_experiment(name, params):
    """Runs a single experiment."""
    print(f"\n--- Starting Experiment: {name} ---")
    original_content = None

    if params == "baseline":
        print("Modification step skipped for this baseline run.")
    else:
        print(f"Applying parameters: {params}")
        original_content = modify_file(params)

    print(f"Running command: {PYTHON_EXECUTABLE} {BENCHMARK_SCRIPT_PATH}")
    output = run_benchmark()

    if output:
        print(f"--- Captured Benchmark Output ---\n{output}\n-----------------------------")
        metrics = parse_metrics(output)
        if metrics:
            log_results(name, params, metrics)

    if original_content:
        with open(TARGET_FILE_PATH, "w") as f:
            f.write(original_content)
        print(f"Restored original content of {TARGET_FILE_PATH}")


def main():
    for name, params in EXPERIMENTS.items():
        run_experiment(name, params)


if __name__ == "__main__":
    main()
