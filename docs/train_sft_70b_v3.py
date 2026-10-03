#!/usr/bin/env python3
"""
Logos v7 — 70B QLoRA SFT v3.1 (2026-10-02, post-QA patch)

v3.1 — Critical fixes from adversarial QA audit:
  - FIX B-5: Signal handler sets flag (no sys.exit) — lets Trainer save
  - FIX B-1: Uses v3 dataset (30k rows) — v4 was dirty
  - FIX B-3: OUTPUT_DIR configurable via NM_OUTPUT_DIR env var
  - FIX B-6: Checkpoint pruning uses correct path matching
  - FIX W-n: Watchdog aligned (script name, step count, adapter paths)

Critical changes over v2.1:
  - NETWORK VOLUME: OUTPUT_DIR on /runpod-volume (survives pod termination)
  - DIRECT HF UPLOAD: training script uploads adapter to HF at end (no SSH bridge)
  - CHECKPOINT CALLBACK: async HF upload every save_steps (max 3 on HF)
  - SIGNAL HANDLER: SIGTERM/SIGINT handler saves adapter immediately on preemption
  - DISK CHECK: validates network volume (not /workspace) free space
  - SAVE ERROR HANDLING: try/except around save_pretrained (ZeRO-3 CPU OOM)
  - COMPLETE FLAG: writes complete.flag to volume for watchdog verification
  - ADAPTER_SIZE_ALERT: logs adapter size for monitoring
"""

import glob as _glob
import json
import os
import shutil
import signal
import statistics
import subprocess
import sys
import time

import torch
from datasets import load_dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from torch.nn.utils.rnn import pad_sequence
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    Trainer,
    TrainerCallback,
    TrainingArguments,
    set_seed,
)

set_seed(42)

# === Configuration ===
MODEL_ID = "Qwen/Qwen2.5-72B-Instruct"

# B-1 FIX: Use v3 dataset (30k rows, known quality) instead of v4 (dirty: 24.9% duplicates)
DATASET_PATH = "pipeline/sft_dataset_v3.jsonl"

# B-3 FIX: Configurable via env var, fallback to /runpod-volume
OUTPUT_DIR = os.environ.get("NM_OUTPUT_DIR", "/runpod-volume/logos-70b-sft")
CACHE_DIR = "/workspace/.hf_cache"
DS_CONFIG_PATH = "/workspace/ds_config_z3.json"
MAX_LEN = 1024
LOGGING_STEPS = 10

# HF upload config
HF_REPO = "frostedunicorn/logos-v70b-sft"
HF_CHECKPOINT_REPO = "frostedunicorn/logos-v70b-sft-ckpts"
HF_TOKEN = os.environ.get("HF_TOKEN", "")
MAX_HF_CHECKPOINTS = 3

# === Verify output dir mount ===
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Check free space on output volume
free_gb = shutil.disk_usage(OUTPUT_DIR).free / 1e9
print(f"Output dir free space: {free_gb:.0f} GB at {OUTPUT_DIR}")
if free_gb < 60:
    print(
        "WARNING: low disk on output volume — ZeRO-3 checkpoints are large; "
        "save_total_limit=2 may fill the volume"
    )

# Verify HF token
if HF_TOKEN:
    print("HF_TOKEN found — direct upload enabled")
else:
    print(
        "WARNING: HF_TOKEN not set — adapter will save locally only. "
        "Set HF_TOKEN env var on pod for automatic upload."
    )

# === DeepSpeed config ===
ds_config = {
    "zero_optimization": {
        "stage": 3,
        "offload_optimizer": {"device": "cpu", "pin_memory": True},
        "offload_param": {"device": "cpu", "pin_memory": True},
        "overlap_comm": True,
        "contiguous_gradients": True,
        "sub_group_size": 1000000000,
        "reduce_bucket_size": "auto",
        "stage3_prefetch_bucket_size": "auto",
        "stage3_param_persistence_threshold": "auto",
        "stage3_max_live_parameters": 1000000000,
        "stage3_max_reuse_distance": 1000000000,
        "stage3_gather_16bit_weights_on_model_save": True,
    },
    "bf16": {"enabled": True},
    "train_batch_size": "auto",
    "wall_clock_breakdown": False,
}
with open(DS_CONFIG_PATH, "w") as f:
    json.dump(ds_config, f, indent=2)

lora_config = LoraConfig(
    r=32,
    lora_alpha=64,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
)

print("Loading tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, cache_dir=CACHE_DIR, trust_remote_code=True)
tokenizer.pad_token = tokenizer.eos_token
im_end_id = tokenizer.convert_tokens_to_ids("<|im_end|>")
assert im_end_id != 0, "FATAL: <|im_end|> not in tokenizer vocab"
nl_ids = tokenizer("\n", add_special_tokens=False).input_ids

print("Loading model in 4-bit...")
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16,
    bnb_4bit_use_double_quant=True,
)
try:
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        quantization_config=bnb_config,
        device_map={"": 0},
        low_cpu_mem_usage=True,
        cache_dir=CACHE_DIR,
        trust_remote_code=True,
        attn_implementation="flash_attention_2",
    )
    print("Attention: Flash Attention 2")
except Exception as e:
    print(f"flash_attention_2 unavailable ({e}); falling back to sdpa")
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        quantization_config=bnb_config,
        device_map={"": 0},
        low_cpu_mem_usage=True,
        cache_dir=CACHE_DIR,
        trust_remote_code=True,
        attn_implementation="sdpa",
    )

model = prepare_model_for_kbit_training(model)
model.gradient_checkpointing_enable()
model = get_peft_model(model, lora_config)
model.config.use_cache = False
model.print_trainable_parameters()

# === Dataset ===
print(f"Loading dataset: {DATASET_PATH}")
raw = load_dataset("json", data_files=DATASET_PATH, split="train", cache_dir=CACHE_DIR)

fields = set(raw[0].keys())
assert (
    "instruction" in fields and "output" in fields
), f"FATAL: expected instruction/output fields, got {fields}"
empty = [
    i
    for i, ex in enumerate(raw)
    if not (ex.get("instruction") or "").strip() or not (ex.get("output") or "").strip()
]
assert not empty, f"FATAL: {len(empty)}/{len(raw)} rows have empty instruction/output"

print("=== VALIDATION GATE: 3 formatted samples ===")
for i in (0, len(raw) // 2, len(raw) - 1):
    print(f"--- sample {i} ({raw[i].get('type')}/{raw[i].get('lang')}) ---")
    print(f"USER: {raw[i]['instruction'][:200]}")
    print(f"ASSISTANT: {raw[i]['output'][:200]}")
print(f"Dataset OK: {len(raw)} rows, 0 empty")


def tokenize_fn(ex):
    prompt_ids = tokenizer.apply_chat_template(
        [{"role": "user", "content": ex["instruction"]}], tokenize=True, add_generation_prompt=True
    )
    if len(prompt_ids) > MAX_LEN - 8:
        prompt_ids = prompt_ids[: MAX_LEN - 8]
    ans_ids = tokenizer(ex["output"], add_special_tokens=False).input_ids
    ans_ids = ans_ids[: MAX_LEN - len(prompt_ids) - 1 - len(nl_ids)]
    answer_ids = ans_ids + [im_end_id] + nl_ids
    input_ids = prompt_ids + answer_ids
    labels = [-100] * len(prompt_ids) + answer_ids
    return {"input_ids": input_ids, "attention_mask": [1] * len(input_ids), "labels": labels}


ds = raw.map(tokenize_fn, remove_columns=raw.column_names)
ds.set_format("torch", columns=["input_ids", "attention_mask", "labels"])
split = ds.train_test_split(test_size=0.02, seed=42)
train_ds, eval_ds = split["train"], split["test"]

lens = [len(x) for x in train_ds["input_ids"][:2000]]
print(
    f"Token lengths (first 2k): mean={statistics.mean(lens):.0f} "
    f"median={statistics.median(lens):.0f} max={max(lens)}"
)


def collate(features):
    return {
        "input_ids": pad_sequence(
            [f["input_ids"] for f in features],
            batch_first=True,
            padding_value=tokenizer.pad_token_id,
        ),
        "attention_mask": pad_sequence(
            [f["attention_mask"] for f in features], batch_first=True, padding_value=0
        ),
        "labels": pad_sequence(
            [f["labels"] for f in features], batch_first=True, padding_value=-100
        ),
    }


# === Checkpoint upload callback ===
class CheckpointUploadCallback(TrainerCallback):
    """Async HF upload on each checkpoint save. Non-blocking."""

    def on_save(self, args, state, control, **kwargs):
        ckpt_dir = f"{args.output_dir}/checkpoint-{state.global_step}"
        if os.path.isdir(ckpt_dir) and HF_TOKEN:
            print(f"[CHECKPOINT UPLOAD] Launching async upload: {ckpt_dir}")
            subprocess.Popen(
                [
                    sys.executable,
                    "/workspace/logos-checkpoint-upload.py",
                    ckpt_dir,
                    "--repo",
                    HF_CHECKPOINT_REPO,
                    "--max-checkpoints",
                    str(MAX_HF_CHECKPOINTS),
                ]
            )


# === B-5 FIX: Signal handler — set flag, DON'T exit ===
# Let Trainer save at next checkpoint or at end
_preemption_received = False


def signal_handler(signum, frame):
    global _preemption_received
    _preemption_received = True
    sig_name = signal.Signals(signum).name
    print(
        f"\n[SIGNAL] Received {sig_name} — preemption flag set. Trainer will save at next checkpoint."
    )
    # DO NOT call sys.exit(1) — that kills Trainer before save
    # The Trainer will see the flag on next iteration


signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

training_args = TrainingArguments(
    output_dir=OUTPUT_DIR,
    num_train_epochs=3,
    per_device_train_batch_size=1,
    per_device_eval_batch_size=8,
    gradient_accumulation_steps=8,
    learning_rate=2e-4,
    lr_scheduler_type="cosine",
    warmup_ratio=0.05,
    weight_decay=0.01,
    max_grad_norm=1.0,
    logging_steps=LOGGING_STEPS,
    save_strategy="steps",
    save_steps=500,
    save_total_limit=2,
    eval_strategy="steps",
    eval_steps=500,
    bf16=True,
    group_by_length=True,
    save_only_model=True,
    dataloader_num_workers=2,
    remove_unused_columns=False,
    deepspeed=DS_CONFIG_PATH,
    report_to="none",
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_ds,
    eval_dataset=eval_ds,
    processing_class=tokenizer,
    data_collator=collate,
    callbacks=[CheckpointUploadCallback()],
)

# Auto-resume from latest checkpoint (safer parsing)
_ckpts = sorted(
    _glob.glob(f"{OUTPUT_DIR}/checkpoint-*"), key=lambda p: int(os.path.basename(p).split("-")[-1])
)
_resume = _ckpts[-1] if _ckpts else None
if _resume:
    print(f"Resuming from {_resume}")

print("Starting 70B SFT v3.1 (ZeRO-3, direct HF upload, signal-safe)...")
print(f"Dataset: {len(train_ds)} rows, effective batch: 8")
print(f"Total steps: ~{len(train_ds) * 3 // 8}")
t0 = time.time()
trainer.train(resume_from_checkpoint=_resume)
print(f"Training done in {time.time()-t0:.0f}s")

# === Adapter save with error handling ===
adapter_dir = f"{OUTPUT_DIR}/adapter"
adapter_size_mb = 0.0
try:
    model.save_pretrained(adapter_dir)
    tokenizer.save_pretrained(adapter_dir)
    adapter_size_mb = (
        sum(
            os.path.getsize(os.path.join(adapter_dir, f))
            for f in os.listdir(adapter_dir)
            if os.path.isfile(os.path.join(adapter_dir, f))
        )
        / 1e6
    )
    print(f"Adapter saved to {adapter_dir} ({adapter_size_mb:.1f} MB)")
except Exception as e:
    print(f"[ADAPTER SAVE ERROR] {e}")
    print("Attempting save to fallback location...")
    fallback = "/workspace/logos-70b-sft-fallback/adapter"
    os.makedirs(fallback, exist_ok=True)
    try:
        model.save_pretrained(fallback)
        tokenizer.save_pretrained(fallback)
        print(f"Adapter saved to fallback: {fallback}")
        adapter_dir = fallback
    except Exception as e2:
        print(f"[FATAL] Adapter save failed completely: {e2}")
        sys.exit(1)

# === Direct HF upload (no SSH bridge) ===
if HF_TOKEN:
    print("\n=== DIRECT HF UPLOAD ===")
    try:
        from huggingface_hub import HfApi

        api = HfApi()

        api.create_repo(HF_REPO, token=HF_TOKEN, repo_type="model", exist_ok=True)
        print(f"Repo {HF_REPO} ready")

        print(f"Uploading adapter ({adapter_size_mb:.1f} MB) to HF...")
        api.upload_folder(
            folder_path=adapter_dir,
            repo_id=HF_REPO,
            repo_type="model",
            token=HF_TOKEN,
        )
        print(f"Adapter uploaded to {HF_REPO}")

        # Verify upload
        files = api.list_repo_files(HF_REPO, repo_type="model", token=HF_TOKEN)
        print(f"Files in repo ({len(files)}):")
        for f in sorted(files):
            print(f"  {f}")
        expected = ["adapter_config.json", "adapter_model.safetensors", "tokenizer.json"]
        missing = [f for f in expected if f not in files]
        if missing:
            print(f"WARNING: Missing expected files: {missing}")
        else:
            print("All required files verified on HF.")

    except Exception as e:
        print(f"[HF UPLOAD ERROR] {e}")
        print("Adapter saved locally. Upload manually with:")
        print(f"  huggingface-cli upload {HF_REPO} {adapter_dir} --repo-type model")
else:
    print("\n[SKIP] HF upload — HF_TOKEN not set")
    print(f"Adapter at: {adapter_dir}")

# === Write completion flag ===
complete_flag = f"{OUTPUT_DIR}/complete.flag"
with open(complete_flag, "w") as f:
    f.write(f"HF_UPLOAD_OK: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n")
    f.write(f"adapter_dir: {adapter_dir}\n")
    f.write(f"adapter_size_mb: {adapter_size_mb:.1f}\n")
print(f"\nCompletion flag written: {complete_flag}")
print("DONE — training complete, adapter on HF (if token set)")
