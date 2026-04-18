import subprocess
import os
import re
import datetime

# --- Configuration ---
BENCHMARK_SCRIPT_PATH = "/a0/usr/workdir/neuralmind/benchmark.py"
RESULTS_LOG_PATH = "/a0/usr/workdir/neuralmind/optimization/results.tsv"
PROJECT_VENV_PYTHON = "/a0/usr/workdir/neuralmind/.venv/bin/python"
CONTEXT_SELECTOR_PATH = "/a0/usr/workdir/neuralmind/neuralmind/context_selector.py"

def run_experiment(experiment_name: str, params: dict):
    """Runs a single experiment, logs the results, and returns the metrics."""
    print(f"\n--- Starting Experiment: {experiment_name} ---")
    original_content = None

    try:
        # --- 1. Modify Parameters (The Core Logic) ---
        if params:
            print(f"Applying parameters: {params}")
            with open(CONTEXT_SELECTOR_PATH, 'r') as f:
                original_content = f.read()
            
            modified_content = original_content
            for key, value in params.items():
                pattern = re.compile(f"({key}\s*=\s*)\d+")
                replacement = f"\g<1>{value}"
                modified_content, count = pattern.subn(replacement, modified_content)
                if count == 0:
                    print(f"Warning: Parameter '{key}' not found in {CONTEXT_SELECTOR_PATH}")

            with open(CONTEXT_SELECTOR_PATH, 'w') as f:
                f.write(modified_content)
        else:
            print("Modification step skipped for this baseline run.")

        # --- 2. Run Benchmark ---
        command = [PROJECT_VENV_PYTHON, BENCHMARK_SCRIPT_PATH]
        print(f"Running command: {' '.join(command)}")
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        output = result.stdout
        print(output)

        # --- 3. Parse Results ---
        time_match = re.search(r"Execution Time: (\d+\.\d+) seconds", output)
        mem_match = re.search(r"Peak Memory \(Children\): (\d+\.\d+) MB", output)
        tokens_match = re.search(r"Approx. Output Tokens: (\d+)", output)

        if not (time_match and mem_match and tokens_match):
            print("--- PARSING FAILED: Could not extract all metrics from benchmark output. ---")
            return None

        metrics = {
            "time_sec": float(time_match.group(1)),
            "memory_mb": float(mem_match.group(1)),
            "tokens": int(tokens_match.group(1))
        }

        print(f"--- Metrics Extracted: {metrics} ---")

        # --- 4. Log Results ---
        log_results(experiment_name, params, metrics)
        return metrics

    except subprocess.CalledProcessError as e:
        print("--- EXPERIMENT FAILED: Benchmark script returned a non-zero exit code. ---")
        print(e.stderr)
        return None
    except Exception as e:
        print(f"--- EXPERIMENT FAILED: An unexpected error occurred. Error: {e} ---")
        return None
    finally:
        # --- 5. Revert Changes ---
        if original_content:
            with open(CONTEXT_SELECTOR_PATH, 'w') as f:
                f.write(original_content)
            print(f"Restored original content of {CONTEXT_SELECTOR_PATH}")

def log_results(experiment_name: str, params: dict, metrics: dict):
    """Appends the experiment results to the TSV log file."""
    file_exists = os.path.isfile(RESULTS_LOG_PATH)
    
    with open(RESULTS_LOG_PATH, "a") as f:
        if not file_exists:
            headers = ["timestamp", "experiment_name", "param_keys", "time_sec", "memory_mb", "tokens"]
            f.write("\t".join(headers) + "\n")

        timestamp = datetime.datetime.now().isoformat()
        param_str = ",".join([f"{k}={v}" for k, v in params.items()]) if params else "baseline"
        
        log_entry = [ 
            timestamp, 
            experiment_name, 
            param_str, 
            str(metrics['time_sec']), 
            str(metrics['memory_mb']), 
            str(metrics['tokens'])
        ]
        f.write("\t".join(log_entry) + "\n")
    print(f"Results logged to {RESULTS_LOG_PATH}")

if __name__ == "__main__":
    # Run a series of experiments
    
    # 1. Establish a baseline with no parameter changes.
    run_experiment(experiment_name="baseline_v2", params={})

    # 2. Test a tight budget to optimize for speed and low token count
    tight_budget_params = {
        "L2_MAX_TOKENS": 400, # Default is 800
        "L3_MAX_TOKENS": 500  # Default is 1000
    }
    run_experiment(experiment_name="tight_budget_v1", params=tight_budget_params)

    # 3. Test a generous budget to see if more context improves quality (at a cost)
    generous_budget_params = {
        "L2_MAX_TOKENS": 1200,
        "L3_MAX_TOKENS": 1500
    }
    run_experiment(experiment_name="generous_budget_v1", params=generous_budget_params)
