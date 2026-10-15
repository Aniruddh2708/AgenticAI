"""Score predeclared held-out authentic-source questions, optionally requiring vectors."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vibefinance.rag.evaluate import evaluate
from vibefinance.rag.retriever import Retriever


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, default=Path(".runtime/retrieval-evaluation"))
    parser.add_argument("--require-vectors", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Existing evaluation preserved")
    questions = json.loads(args.questions.read_text())
    retriever = Retriever(embeddings=args.require_vectors, corpus_path=args.corpus, state_dir=args.state_dir)
    report = evaluate(retriever, questions)
    report["vector_requirement_satisfied"] = not args.require_vectors or retriever.mode == "hybrid_embedding_bm25"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as handle:
        json.dump(report, handle, indent=2)
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=2))
    return 0 if report["vector_requirement_satisfied"] and report["judgment_pool_complete"] and report["all_spans_exact"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
