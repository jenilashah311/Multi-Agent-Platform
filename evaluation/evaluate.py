"""
Lightweight evaluation harness. Install optional RAGAS for full metrics:
  pip install ragas datasets
"""
from __future__ import annotations

import argparse
import json
import sys


def main():
    p = argparse.ArgumentParser(description="Evaluate agent outputs (RAGAS optional).")
    p.add_argument("--payload", type=str, help="Path to JSON with keys: question, answer, contexts (list)")
    args = p.parse_args()
    if not args.payload:
        print(
            json.dumps(
                {
                    "note": "Pass --payload sample.json. For RAGAS: pip install ragas datasets langchain-openai",
                    "faithfulness": None,
                    "answer_relevancy": None,
                },
                indent=2,
            )
        )
        return 0
    with open(args.payload, encoding="utf-8") as f:
        data = json.load(f)
    try:
        from ragas import evaluate  # type: ignore
        from ragas.metrics import answer_relevancy, faithfulness  # type: ignore
        from datasets import Dataset  # type: ignore

        ds = Dataset.from_dict(
            {
                "question": [data["question"]],
                "answer": [data["answer"]],
                "contexts": [data.get("contexts", [])],
            }
        )
        out = evaluate(ds, metrics=[faithfulness, answer_relevancy])
        print(out.to_pandas().to_json(orient="records", indent=2))
    except ImportError:
        print(
            json.dumps(
                {
                    "skipped": "ragas not installed",
                    "payload_keys": list(data.keys()),
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
