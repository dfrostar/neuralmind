#!/usr/bin/env python3
"""
Logos v7 — Checkpoint Uploader (v3.1)

FIX B-6: Checkpoint pruning now uses directory matching (trailing /)
instead of file prefix matching (which never matched).

Called by CheckpointUploadCallback in train_sft_70b_v3.py.
Uploads a checkpoint to HF, keeping only the latest N checkpoints.

Non-blocking: spawned as subprocess by the Trainer callback.
Exits cleanly on failure (does not crash training).

Usage:
    python3 logos-checkpoint-upload.py <checkpoint_dir> --repo <repo_id> --max-checkpoints <N>
"""

import argparse
import os
import sys
import time

def main():
    parser = argparse.ArgumentParser(description="Upload checkpoint to HF Hub")
    parser.add_argument("checkpoint_dir", help="Path to checkpoint directory")
    parser.add_argument("--repo", required=True, help="HF repo ID")
    parser.add_argument("--max-checkpoints", type=int, default=3, help="Max checkpoints to keep on HF")
    args = parser.parse_args()

    hf_token = os.environ.get("HF_TOKEN", "")
    if not hf_token:
        print("[CKPT UPLOAD] HF_TOKEN not set — skipping")
        sys.exit(0)

    if not os.path.isdir(args.checkpoint_dir):
        print(f"[CKPT UPLOAD] Directory not found: {args.checkpoint_dir}")
        sys.exit(0)

    try:
        from huggingface_hub import HfApi
        api = HfApi()

        # Create repo if needed
        api.create_repo(args.repo, token=hf_token, repo_type="model", exist_ok=True)

        # Upload
        ckpt_name = os.path.basename(args.checkpoint_dir)
        print(f"[CKPT UPLOAD] Uploading {ckpt_name} to {args.repo}...")
        api.upload_folder(
            folder_path=args.checkpoint_dir,
            repo_id=args.repo,
            repo_type="model",
            token=hf_token,
            path_in_repo=ckpt_name,
        )

        # FIX B-6: Prune old checkpoints — match directories (trailing /)
        files = api.list_repo_files(args.repo, repo_type="model", token=hf_token)
        # HF API returns directory entries with trailing /
        ckpts = sorted([f for f in files if f.startswith("checkpoint-") and f.endswith("/")])
        if len(ckpts) > args.max_checkpoints:
            to_delete = ckpts[:len(ckpts) - args.max_checkpoints]
            print(f"[CKPT UPLOAD] Pruning {len(to_delete)} old checkpoints: {to_delete}")
            for old in to_delete:
                api.delete_file(
                    path_in_repo=old.rstrip("/"),  # remove trailing / for delete
                    repo_id=args.repo,
                    repo_type="model",
                    token=hf_token,
                )
        print(f"[CKPT UPLOAD] Done: {ckpt_name} uploaded to {args.repo}")

    except Exception as e:
        print(f"[CKPT UPLOAD ERROR] {e}")
        # Don't crash — training continues
        sys.exit(0)

if __name__ == "__main__":
    main()
