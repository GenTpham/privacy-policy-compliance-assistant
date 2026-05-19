"""
backend/eval/upload_phoenix_dataset.py
Upload QA pairs from the privacy policy dataset into Arize Phoenix as a Dataset object.

Phoenix 10.x API: POST /v1/datasets/upload with parallel arrays:
  inputs[]   — question + context passage (what the RAG system receives)
  outputs[]  — ground-truth answer text
  metadata[] — id, title (policy source), answer_start

Usage:
  python -m backend.eval.upload_phoenix_dataset
  python -m backend.eval.upload_phoenix_dataset --split validation --limit 200
  python -m backend.eval.upload_phoenix_dataset --split train --limit 500
  python -m backend.eval.upload_phoenix_dataset --split all
  python -m backend.eval.upload_phoenix_dataset --endpoint http://localhost:6006

After upload: Phoenix UI → Datasets tab → select dataset to browse examples.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import httpx

DATASET_FILES = {
    "train":      Path("dataset/json/train/policy_qa_train.json"),
    "validation": Path("dataset/json/test_valid/policy_qa_validation.json"),
    "test":       Path("dataset/json/test_valid/policy_qa_test.json"),
}

BATCH_SIZE = 500  # examples per POST — Phoenix accepts large batches


def load_split(split: str) -> list[dict]:
    path = DATASET_FILES[split]
    if not path.exists():
        print(f"[error] Dataset file not found: {path}", file=sys.stderr)
        sys.exit(1)
    records = json.loads(path.read_text(encoding="utf-8"))
    print(f"[load] {split}: {len(records):,} records")
    return records


def unpack_parallel(records: list[dict]) -> tuple[list, list, list]:
    """Convert records to Phoenix parallel arrays: inputs, outputs, metadata."""
    inputs, outputs, metadata = [], [], []
    for r in records:
        answer_texts = r.get("answers", {}).get("text", [])
        answer_starts = r.get("answers", {}).get("answer_start", [])
        inputs.append({
            "question": r["question"],
            "context": r["context"],
        })
        outputs.append({
            "answer": answer_texts[0] if answer_texts else "",
        })
        metadata.append({
            "id": r["id"],
            "title": r["title"],
            "answer_start": answer_starts[0] if answer_starts else None,
        })
    return inputs, outputs, metadata


def upload_dataset(
    client: httpx.Client,
    name: str,
    description: str,
    records: list[dict],
) -> str:
    """Upload all records to Phoenix. Returns dataset_id."""
    inputs, outputs, metadata = unpack_parallel(records)
    total = len(records)

    dataset_id = None

    for i in range(0, total, BATCH_SIZE):
        batch_inputs   = inputs[i : i + BATCH_SIZE]
        batch_outputs  = outputs[i : i + BATCH_SIZE]
        batch_metadata = metadata[i : i + BATCH_SIZE]
        action = "create" if i == 0 else "append"

        print(f"  [{i + len(batch_inputs):>5}/{total}] {action} batch ({len(batch_inputs)} examples)...")

        resp = client.post(
            "/v1/datasets/upload",
            json={
                "action": action,
                "name": name,
                "description": description,
                "inputs": batch_inputs,
                "outputs": batch_outputs,
                "metadata": batch_metadata,
            },
            timeout=120.0,
        )

        if resp.status_code == 409:
            print(f"[warn] Dataset '{name}' already exists. Use --force to overwrite or choose a different --name.")
            sys.exit(1)

        resp.raise_for_status()

    # Phoenix returns null body — resolve dataset_id from GET /v1/datasets by name
    return name


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload privacy-policy QA dataset to Phoenix")
    parser.add_argument(
        "--split",
        choices=["train", "validation", "test", "all"],
        default="validation",
        help="Dataset split to upload (default: validation = 3,809 examples)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max examples to upload per split (default: all)",
    )
    parser.add_argument(
        "--endpoint",
        default="http://localhost:6006",
        help="Phoenix base URL (default: http://localhost:6006)",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="Dataset name in Phoenix (default: privacy-qa-<split>)",
    )
    args = parser.parse_args()

    splits = ["train", "validation", "test"] if args.split == "all" else [args.split]

    with httpx.Client(base_url=args.endpoint, timeout=30.0) as client:
        # Verify Phoenix is reachable
        try:
            r = client.get("/healthz")
            r.raise_for_status()
        except Exception as exc:
            print(f"[error] Cannot reach Phoenix at {args.endpoint}: {exc}", file=sys.stderr)
            print("  Run: docker compose --profile observability up", file=sys.stderr)
            sys.exit(1)
        print(f"[ok] Phoenix {args.endpoint} reachable\n")

        for split in splits:
            records = load_split(split)
            if args.limit:
                records = records[: args.limit]
                print(f"[limit] Using first {len(records):,} records")

            dataset_name = args.name or f"privacy-qa-{split}"
            description = (
                f"Privacy policy SQuAD-style QA pairs — {split} split "
                f"({len(records):,} examples, {time.strftime('%Y-%m-%d')}). "
                "input: question + context passage | output: ground-truth answer"
            )

            print(f"[upload] '{dataset_name}' — {len(records):,} examples...")
            t0 = time.time()
            dataset_id = upload_dataset(client, dataset_name, description, records)
            elapsed = time.time() - t0

            # Resolve dataset_id — Phoenix commits asynchronously, retry briefly
            ds_id = "?"
            for _ in range(5):
                ds_list = client.get("/v1/datasets").json().get("data", [])
                matched = next((d for d in ds_list if d["name"] == dataset_name), None)
                if matched:
                    ds_id = matched["id"]
                    break
                time.sleep(0.3)

            print(f"[done] '{dataset_name}' uploaded in {elapsed:.1f}s  id={ds_id}")
            print(f"  View: {args.endpoint}/datasets/{ds_id}")
            print()

    print("Open Phoenix -> Datasets tab to browse.")


if __name__ == "__main__":
    main()
