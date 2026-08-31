"""Compare fixed-size, semantic, and structural chunking on a real document.

This script:
1. Extracts Docs/DocMind.txt (a real, ~34KB multi-paragraph document
   already in this repo) using the same extraction layer the API uses
2. Runs all three chunking strategies against the identical extraction
3. Prints comparative stats and writes them to
   scripts/chunking_comparison.txt

Two proxy metrics stand in for "did this chunk cut something in half":
- starts_lowercase: the chunk's first letter is lowercase, which a
  properly-bounded chunk (starting a new sentence/section) essentially
  never does in English prose — a strong signal the chunk starts mid-sentence
- no_terminal_punctuation: the chunk doesn't end in . ! ? or a Markdown
  table row `|`, suggesting it was cut off mid-thought

These are heuristics, not proof — see the "Critical understanding" note
in Docs/DocMind.txt about chunking strategy. They're good enough to make
the tradeoff between strategies visible in real numbers.

Run with: uv run python scripts/compare_chunking.py
"""

import sys
from pathlib import Path

# This script lives outside the installed package (there's no
# [build-system] in pyproject.toml, so `docmind` is never actually
# installed — only pytest's `pythonpath = ["src"]` makes imports work
# during tests). Standalone scripts need the same path added manually.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from docmind.chunking.fixed_size import chunk_fixed_size  # noqa: E402
from docmind.chunking.models import TextChunk  # noqa: E402
from docmind.chunking.semantic import chunk_semantic  # noqa: E402
from docmind.chunking.structural import chunk_structural  # noqa: E402
from docmind.extraction.router import extract  # noqa: E402

DOCUMENT_PATH = Path("Docs/DocMind.txt")
TARGET_TOKENS = 512

output_lines: list[str] = []


def log(msg: str = "") -> None:
    print(msg)
    output_lines.append(msg)


def looks_cut_off(chunk: TextChunk) -> tuple[bool, bool]:
    text = chunk.text.strip()
    starts_lowercase = bool(text) and text[0].islower()
    no_terminal_punctuation = bool(text) and text[-1] not in ".!?|:"
    return starts_lowercase, no_terminal_punctuation


def report(label: str, chunks: list[TextChunk]) -> None:
    log(f"{'=' * 70}")
    log(f"Strategy: {label}")
    log(f"{'=' * 70}")

    if not chunks:
        log("  (no chunks produced)")
        return

    token_counts = [c.token_count for c in chunks]
    cut_starts = sum(1 for c in chunks if looks_cut_off(c)[0])
    cut_ends = sum(1 for c in chunks if looks_cut_off(c)[1])

    log(f"  chunks produced:        {len(chunks)}")
    log(f"  avg tokens/chunk:       {sum(token_counts) / len(chunks):.1f}")
    log(f"  min/max tokens/chunk:   {min(token_counts)} / {max(token_counts)}")
    log(f"  chunks starting lowercase (likely mid-sentence): {cut_starts}")
    log(f"  chunks with no terminal punctuation (likely cut off): {cut_ends}")
    log()
    log("  First chunk preview:")
    log(f"    {chunks[0].text[:150]!r}")
    log("  Last chunk preview:")
    log(f"    {chunks[-1].text[:150]!r}")
    log()


def main() -> None:
    data = DOCUMENT_PATH.read_bytes()
    extraction = extract(DOCUMENT_PATH.name, data)

    log(
        f"\nDocument: {DOCUMENT_PATH} "
        f"({len(data)} bytes, {len(extraction.pages)} page(s))"
    )
    log(f"Target chunk size: {TARGET_TOKENS} tokens (~{TARGET_TOKENS * 4} chars)\n")

    report(
        "1 — Fixed-size (naive baseline)",
        chunk_fixed_size(extraction, TARGET_TOKENS),
    )
    report(
        "2 — Semantic (sentence + TF-similarity grouping)",
        chunk_semantic(extraction, TARGET_TOKENS),
    )
    report(
        "3 — Structural (paragraph/heading boundaries)",
        chunk_structural(extraction, TARGET_TOKENS),
    )

    with open("scripts/chunking_comparison.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))


if __name__ == "__main__":
    main()
