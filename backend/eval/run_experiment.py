"""
backend/eval/run_experiment.py
Run a Phoenix experiment against the RAG pipeline.

For each example in the Phoenix dataset:
  1. Call POST /api/chat on the backend
  2. Parse SSE response -> answer + citations
  3. Run 3 CODE evaluators:
     - context_hit   : ground truth found in any retrieved citation text (score 0/1)
     - answer_match  : ground truth substring in generated answer (score 0/1)
     - retrieved     : at least one citation returned (score 0/1)
  4. POST run + evaluations to Phoenix

Results appear in Phoenix -> Datasets -> <dataset> -> Experiments tab.

Usage:
  python -m backend.eval.run_experiment
  python -m backend.eval.run_experiment --limit 50
  python -m backend.eval.run_experiment --dataset privacy-qa-validation --limit 100
  python -m backend.eval.run_experiment --experiment-name "threshold-0.25-baseline"

Credentials (read from env or .env file):
  ADMIN_USERNAME / ADMIN_PASSWORD  — or pass --username / --password
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

# -- .env loader (no dotenv dependency — read key=value manually) ---------------

def _load_dotenv(path: str = ".env") -> None:
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key not in os.environ:
            os.environ[key] = val


_load_dotenv()

# -- Helpers --------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _login(backend: httpx.Client, username: str, password: str) -> str:
    resp = backend.post("/auth/login", json={"username": username, "password": password})
    if resp.status_code != 200:
        print(f"[error] Login failed ({resp.status_code}): {resp.text}", file=sys.stderr)
        sys.exit(1)
    token = resp.json()["access_token"]
    print(f"[auth] Logged in as '{username}'")
    return token


def _call_rag(backend: httpx.Client, question: str, token: str) -> tuple[str, list[dict]]:
    """Call POST /api/chat, parse SSE stream, return (answer, citations)."""
    answer = ""
    citations: list[dict] = []
    with backend.stream(
        "POST",
        "/api/chat",
        json={"message": question, "history": []},
        headers={"Authorization": f"Bearer {token}"},
        timeout=120.0,
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line.startswith("data: "):
                continue
            event = json.loads(line[6:])
            if event["type"] == "done":
                answer = event.get("answer", "")
                citations = event.get("citations", [])
                break
            if event["type"] == "error":
                raise RuntimeError(event.get("message", "RAG error"))
    return answer, citations


def _get_dataset_id(phoenix: httpx.Client, dataset_name: str) -> str:
    resp = phoenix.get("/v1/datasets")
    resp.raise_for_status()
    for ds in resp.json().get("data", []):
        if ds["name"] == dataset_name:
            return ds["id"]
    print(f"[error] Dataset '{dataset_name}' not found in Phoenix.", file=sys.stderr)
    print("  Run: python -m backend.eval.upload_phoenix_dataset", file=sys.stderr)
    sys.exit(1)


def _get_examples(phoenix: httpx.Client, dataset_id: str, limit: int | None) -> list[dict]:
    resp = phoenix.get(f"/v1/datasets/{dataset_id}/examples")
    resp.raise_for_status()
    examples = resp.json()["data"]["examples"]
    if limit:
        examples = examples[:limit]
    return examples


def _create_experiment(
    phoenix: httpx.Client, dataset_id: str, name: str | None, description: str
) -> str:
    payload: dict = {"description": description}
    if name:
        payload["name"] = name
    resp = phoenix.post(f"/v1/datasets/{dataset_id}/experiments", json=payload)
    resp.raise_for_status()
    exp_id = resp.json()["data"]["id"]
    exp_name = resp.json()["data"].get("name", exp_id)
    print(f"[experiment] Created: '{exp_name}' (id={exp_id})")
    return exp_id


def _create_run(
    phoenix: httpx.Client,
    experiment_id: str,
    example_id: str,
    output: dict,
    start: str,
    end: str,
    error: str | None = None,
) -> str:
    resp = phoenix.post(
        f"/v1/experiments/{experiment_id}/runs",
        json={
            "dataset_example_id": example_id,
            "output": output,
            "repetition_number": 0,
            "start_time": start,
            "end_time": end,
            "error": error,
        },
    )
    resp.raise_for_status()
    return resp.json()["data"]["id"]


def _submit_eval(
    phoenix: httpx.Client,
    run_id: str,
    name: str,
    score: float,
    label: str,
    explanation: str,
    start: str,
    end: str,
) -> None:
    phoenix.post(
        "/v1/experiment_evaluations",
        json={
            "experiment_run_id": run_id,
            "name": name,
            "annotator_kind": "CODE",
            "start_time": start,
            "end_time": end,
            "result": {"label": label, "score": score, "explanation": explanation},
        },
    ).raise_for_status()


# -- Evaluators -----------------------------------------------------------------

def eval_context_hit(ground_truth: str, citations: list[dict]) -> tuple[float, str, str]:
    """Score 1.0 if ground truth text appears in any retrieved citation."""
    gt = ground_truth.lower().strip()
    for c in citations:
        if gt in c.get("text", "").lower():
            return 1.0, "hit", f"Found in citation from '{c.get('title','?')}'"
    if not citations:
        return 0.0, "miss", "No citations retrieved"
    return 0.0, "miss", f"Ground truth not found in {len(citations)} retrieved citation(s)"


def eval_answer_match(ground_truth: str, answer: str) -> tuple[float, str, str]:
    """Score 1.0 if ground truth is a substring of the generated answer."""
    gt = ground_truth.lower().strip()
    ans = answer.lower()
    if gt in ans:
        return 1.0, "match", "Ground truth found verbatim in answer"
    # Partial: at least half the words of gt appear in answer
    gt_words = set(gt.split())
    if gt_words and sum(1 for w in gt_words if w in ans) / len(gt_words) >= 0.5:
        return 0.5, "partial", f"{sum(1 for w in gt_words if w in ans)}/{len(gt_words)} ground-truth words in answer"
    return 0.0, "no_match", "Ground truth not found in answer"


def eval_retrieved(citations: list[dict]) -> tuple[float, str, str]:
    """Score 1.0 if at least one citation was retrieved."""
    if citations:
        return 1.0, "retrieved", f"{len(citations)} citation(s) returned"
    return 0.0, "no_results", "RAG returned no results (below score_threshold)"


# -- Main -----------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phoenix experiment on RAG pipeline")
    parser.add_argument("--backend", default="http://localhost:8000")
    parser.add_argument("--phoenix", default="http://localhost:6006")
    parser.add_argument("--dataset", default="privacy-qa-validation")
    parser.add_argument("--limit", type=int, default=50,
                        help="Max examples to evaluate (default: 50)")
    parser.add_argument("--experiment-name", default=None,
                        help="Experiment name in Phoenix (auto-generated if omitted)")
    parser.add_argument("--username", default=os.environ.get("ADMIN_USERNAME", ""))
    parser.add_argument("--password", default=os.environ.get("ADMIN_PASSWORD", ""))
    args = parser.parse_args()

    if not args.username or not args.password:
        print("[error] Set ADMIN_USERNAME and ADMIN_PASSWORD in .env or pass --username/--password", file=sys.stderr)
        sys.exit(1)

    with (
        httpx.Client(base_url=args.backend, timeout=30.0) as backend,
        httpx.Client(base_url=args.phoenix, timeout=30.0) as phoenix,
    ):
        # Auth
        token = _login(backend, args.username, args.password)

        # Resolve dataset
        dataset_id = _get_dataset_id(phoenix, args.dataset)
        examples = _get_examples(phoenix, dataset_id, args.limit)
        print(f"[dataset] '{args.dataset}' — {len(examples)} examples to run")

        # Create experiment
        exp_id = _create_experiment(
            phoenix,
            dataset_id,
            name=args.experiment_name,
            description=(
                f"RAG pipeline evaluation — {len(examples)} examples from '{args.dataset}'. "
                "Evaluators: context_hit, answer_match, retrieved. "
                f"Model: gemma-4-26b | Embed: nemotron-embed-vl-1b | score_threshold=0.25"
            ),
        )

        # Run
        results = {"context_hit": [], "answer_match": [], "retrieved": []}
        errors = 0

        print(f"\n{'#':>4}  {'Q (truncated)':40}  hit  match  retr  latency")
        print("-" * 80)

        for i, ex in enumerate(examples, 1):
            question = ex["input"]["question"]
            ground_truth = ex["output"].get("answer", "")
            example_id = ex["id"]

            run_start = _now_iso()
            t0 = time.perf_counter()
            run_error = None
            answer = ""
            citations: list[dict] = []

            try:
                answer, citations = _call_rag(backend, question, token)
            except Exception as exc:
                run_error = str(exc)
                errors += 1

            latency_ms = (time.perf_counter() - t0) * 1000
            run_end = _now_iso()

            # Create Phoenix run
            run_id = _create_run(
                phoenix, exp_id, example_id,
                output={"answer": answer, "citations": citations},
                start=run_start, end=run_end,
                error=run_error,
            )

            # Evaluate (skip if error)
            if not run_error and ground_truth:
                eval_start = _now_iso()

                ch_score, ch_label, ch_exp = eval_context_hit(ground_truth, citations)
                am_score, am_label, am_exp = eval_answer_match(ground_truth, answer)
                rt_score, rt_label, rt_exp = eval_retrieved(citations)

                _submit_eval(phoenix, run_id, "context_hit",  ch_score, ch_label, ch_exp, eval_start, _now_iso())
                _submit_eval(phoenix, run_id, "answer_match", am_score, am_label, am_exp, eval_start, _now_iso())
                _submit_eval(phoenix, run_id, "retrieved",    rt_score, rt_label, rt_exp, eval_start, _now_iso())

                results["context_hit"].append(ch_score)
                results["answer_match"].append(am_score)
                results["retrieved"].append(rt_score)

                print(f"{i:>4}  {question[:40]:40}  {ch_score:.0f}    {am_score:.1f}    {rt_score:.0f}   {latency_ms:6.0f}ms")
            else:
                err_msg = run_error or "(no ground truth)"
                print(f"{i:>4}  {question[:40]:40}  ERR  [{err_msg[:30]}]")

        # Summary
        n = len(results["context_hit"])
        print("\n" + "-" * 80)
        print(f"RESULTS  ({n} evaluated, {errors} errors)\n")
        if n:
            print(f"  context_hit  : {sum(results['context_hit'])/n:.1%}  "
                  f"({int(sum(results['context_hit']))}/{n} examples — ground truth in retrieved passages)")
            print(f"  answer_match : {sum(results['answer_match'])/n:.1%}  "
                  f"({int(sum(results['answer_match']))}/{n} exact | "
                  f"{sum(1 for s in results['answer_match'] if s==0.5)} partial)")
            print(f"  retrieved    : {sum(results['retrieved'])/n:.1%}  "
                  f"({int(sum(results['retrieved']))}/{n} queries returned results)")
        print(f"\nView in Phoenix: {args.phoenix}/datasets/{dataset_id}")


if __name__ == "__main__":
    main()
