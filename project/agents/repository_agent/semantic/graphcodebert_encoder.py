import argparse
import csv
import time
from pathlib import Path
import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer

MODEL_NAME = "microsoft/graphcodebert-base"
MAX_LENGTH = 512
STRIDE = 64

SKIP_DIRS = {
    ".git",
    ".venv",
    "target",
    "build",
    "out",
    "node_modules",
    ".idea",
    ".vscode",
}


def find_java_files(repository_path: Path, production_only: bool = False):
    """
    Discover Java files using common and legacy source layouts.

    Supported production layouts:
      - **/src/main/java/**
      - **/src/java/**
      - src/<module>/src/**
      - modules/<module>/src/**

    Test, fixture, build, and generated directories are excluded.
    """
    files = []

    skip_dirs = {part.lower() for part in SKIP_DIRS | {"test", "tests"}}

    excluded_source_parts = {
        "test",
        "tests",
        "test-framework",
        "test-fixtures",
        "spatial-test-fixtures",
        "target",
        "build",
        "generated",
        "benchmark",
        "benchmarks",
        "jmh",
    }

    for path in repository_path.rglob("*.java"):
        if not path.is_file():
            continue

        relative_parts = path.relative_to(repository_path).parts
        lower_parts = tuple(part.lower() for part in relative_parts)
        directory_parts = lower_parts[:-1]

        # Exclude known non-source and tool directories.
        if any(part in skip_dirs for part in directory_parts):
            continue

        if production_only:
            # Maven/Gradle: module/src/main/java/package/Class.java
            is_standard_production = any(
                lower_parts[i : i + 3] == ("src", "main", "java")
                for i in range(len(lower_parts) - 2)
            )

            # Lucene-style: module/src/java/package/Class.java
            is_src_java = any(
                lower_parts[i : i + 2] == ("src", "java")
                for i in range(len(lower_parts) - 1)
            )

            # Legacy: src/<module>/src/package/Class.java
            is_legacy_src = (
                len(lower_parts) >= 5
                and lower_parts[0] == "src"
                and lower_parts[1] not in {"main", "test", "tests"}
                and lower_parts[2] == "src"
            )

            # Legacy: modules/<module>/src/package/Class.java
            is_legacy_modules = (
                len(lower_parts) >= 5
                and lower_parts[0] == "modules"
                and lower_parts[2] == "src"
            )

            is_supported_layout = (
                is_standard_production
                or is_src_java
                or is_legacy_src
                or is_legacy_modules
            )

            # Exclude test modules, fixtures, generated code and benchmarks.
            is_excluded_source = any(
                part in excluded_source_parts
                or part.startswith("test-")
                or part.endswith("-test")
                or part.endswith("-tests")
                or part.endswith("-test-framework")
                or part.endswith("-test-fixtures")
                or ".test" in part
                or part.startswith("benchmark-")
                or part.endswith("-benchmark")
                or part.endswith("-benchmarks")
                or part.startswith("jmh-")
                or part.endswith("-jmh")
                for part in directory_parts
            )

            if not is_supported_layout or is_excluded_source:
                continue

        files.append(path)

    return sorted(files)


def mean_pool(last_hidden_state, attention_mask):
    """Calculate a masked mean embedding for a token sequence."""
    mask = attention_mask.unsqueeze(-1).to(last_hidden_state.dtype)
    summed = (last_hidden_state * mask).sum(dim=1)
    counts = mask.sum(dim=1).clamp(min=1)
    return summed / counts


def embed_file(source, tokenizer, model, device):
    """Generate one normalized embedding per Java file using overlapping chunks."""

    encoded = tokenizer(
        source,
        add_special_tokens=True,
        truncation=True,
        max_length=MAX_LENGTH,
        stride=STRIDE,
        return_overflowing_tokens=True,
        return_attention_mask=True,
        return_special_tokens_mask=True,
        padding=True,
        return_tensors="pt",
    )

    input_ids = encoded["input_ids"].to(device)
    attention_mask = encoded["attention_mask"].to(device)
    special_tokens_mask = encoded["special_tokens_mask"].to(device)

    model.eval()
    with torch.no_grad():
        outputs = model(
            input_ids=input_ids,
            attention_mask=attention_mask,
        )

        # Exclude padding and special tokens from mean pooling.
        content_mask = (
            (attention_mask * (1 - special_tokens_mask))
            .unsqueeze(-1)
            .to(outputs.last_hidden_state.dtype)
        )

        token_counts = content_mask.sum(dim=1).clamp(min=1)

        chunk_vectors = (outputs.last_hidden_state * content_mask).sum(
            dim=1
        ) / token_counts

    # Average the chunk vectors to obtain one vector per Java file.
    embedding = chunk_vectors.mean(dim=0).cpu().numpy()

    norm = np.linalg.norm(embedding)
    if norm > 0:
        embedding = embedding / norm

    total_tokens = int(attention_mask.sum().item())
    number_of_chunks = int(input_ids.shape[0])

    return embedding.astype(np.float32), total_tokens, number_of_chunks


def main():
    parser = argparse.ArgumentParser(
        description="Generate GraphCodeBERT embeddings for Java files."
    )

    parser.add_argument(
        "--repo",
        required=True,
        help="Path to the local repository",
    )

    parser.add_argument(
        "--repo-id",
        default="spring_petclinic",
        help="Identifier used in output metadata",
    )

    parser.add_argument(
        "--production-only",
        action="store_true",
        help="Process Java files from recognized production source layouts",
    )

    parser.add_argument(
        "--output",
        default="data/processed/semantic",
        help="Directory to save embeddings and metadata",
    )

    args = parser.parse_args()

    repo_path = Path(args.repo).resolve()
    output_path = Path(args.output).resolve()

    if not repo_path.is_dir():
        raise SystemExit(f"Repository directory not found: {repo_path}")

    java_files = find_java_files(
        repo_path,
        production_only=args.production_only,
    )

    if not java_files:
        raise SystemExit(f"No Java files found in: {repo_path}")

    output_path.mkdir(parents=True, exist_ok=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    print(f"Repository: {repo_path}")
    print(f"Repository ID: {args.repo_id}")
    print(f"Java files: {len(java_files)}")
    print(f"Device: {device}")
    print(f"Loading model: {MODEL_NAME}")

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModel.from_pretrained(MODEL_NAME)
    model.to(device)
    model.eval()

    embeddings = []
    metadata = []
    failed = []

    start_time = time.time()

    for index, path in enumerate(java_files, start=1):
        try:
            source = path.read_text(encoding="utf-8", errors="replace")

            if not source.strip():
                print(f"[{index}/{len(java_files)}] Empty file: {path.name}")
                continue

            vector, token_count, chunk_count = embed_file(
                source, tokenizer, model, device
            )

            embedding_index = len(embeddings)
            embeddings.append(vector)

            metadata.append(
                {
                    "embedding_index": embedding_index,
                    "repository_id": args.repo_id,
                    "file_path": path.relative_to(repo_path).as_posix(),
                    "token_count": token_count,
                    "chunk_count": chunk_count,
                    "model_name": MODEL_NAME,
                }
            )

            print(
                f"[{index}/{len(java_files)}] "
                f"Embedded {path.relative_to(repo_path)} "
                f"({chunk_count} chunk(s))"
            )

        except Exception as exc:
            failed.append(
                {"file_path": str(path.relative_to(repo_path)), "error": str(exc)}
            )
            print(f"[{index}/{len(java_files)}] FAILED: {path.name}: {exc}")

    if embeddings:
        np.save(output_path / f"{args.repo_id}_embeddings.npy", np.stack(embeddings))

        with (output_path / f"{args.repo_id}_metadata.csv").open(
            "w", newline="", encoding="utf-8-sig"
        ) as file:
            writer = csv.DictWriter(file, fieldnames=list(metadata[0].keys()))
            writer.writeheader()
            writer.writerows(metadata)

    if failed:
        with (output_path / f"{args.repo_id}_failed.csv").open(
            "w", newline="", encoding="utf-8-sig"
        ) as file:
            writer = csv.DictWriter(file, fieldnames=["file_path", "error"])
            writer.writeheader()
            writer.writerows(failed)

    print("\n--- Semantic Analysis Summary ---")
    print(f"Files discovered: {len(java_files)}")
    print(f"Files embedded: {len(embeddings)}")
    print(f"Files failed: {len(failed)}")
    print(f"Elapsed time: {time.time() - start_time:.1f} seconds")
    print(f"Output directory: {output_path}")


if __name__ == "__main__":
    main()
