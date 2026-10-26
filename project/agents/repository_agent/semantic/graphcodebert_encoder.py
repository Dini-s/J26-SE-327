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
    """Discover Java files using common and legacy source layouts."""

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

        if any(part in skip_dirs for part in directory_parts):
            continue

        if production_only:
            is_standard_production = any(
                lower_parts[i : i + 3] == ("src", "main", "java")
                for i in range(len(lower_parts) - 2)
            )

            is_src_java = any(
                lower_parts[i : i + 2] == ("src", "java")
                for i in range(len(lower_parts) - 1)
            )

            is_legacy_src = (
                len(lower_parts) >= 5
                and lower_parts[0] == "src"
                and lower_parts[1] not in {"main", "test", "tests"}
                and lower_parts[2] == "src"
            )

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
    """Generate one normalized 768-dimensional embedding per Java file."""

    # Split source into subword tokens without creating a full-file tensor.
    tokens = tokenizer.tokenize(source)

    if not tokens:
        raise ValueError("Source contains no tokens.")

    token_ids = tokenizer.convert_tokens_to_ids(tokens)

    cls_id = tokenizer.cls_token_id
    sep_id = tokenizer.sep_token_id
    pad_id = tokenizer.pad_token_id

    if cls_id is None or sep_id is None or pad_id is None:
        raise ValueError("Tokenizer is missing required special-token IDs.")

    # Reserve space for the CLS and SEP tokens.
    chunk_length = MAX_LENGTH - 2
    step = chunk_length - STRIDE

    if step <= 0:
        raise ValueError("STRIDE must be smaller than the chunk length.")

    chunk_vectors = []
    model.eval()

    with torch.inference_mode():
        for start in range(0, len(token_ids), step):
            content_ids = token_ids[start : start + chunk_length]

            if not content_ids:
                break

            # Build one sequence manually: CLS + content + SEP.
            sequence = [cls_id] + content_ids + [sep_id]
            actual_length = len(sequence)
            padding_length = MAX_LENGTH - actual_length

            if padding_length < 0:
                raise ValueError("Chunk exceeds MAX_LENGTH.")

            padded_ids = sequence + [pad_id] * padding_length
            attention_values = [1] * actual_length + [0] * padding_length

            # RoBERTa uses <s> and </s> as special tokens.
            # Exclude them and padding from mean pooling.
            special_values = [1] + [0] * len(content_ids) + [1] + [1] * padding_length

            input_ids = torch.tensor([padded_ids], dtype=torch.long, device=device)
            attention_mask = torch.tensor(
                [attention_values], dtype=torch.long, device=device
            )
            special_mask = torch.tensor(
                [special_values], dtype=torch.long, device=device
            )

            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
            )

            content_mask = (
                (attention_mask * (1 - special_mask))
                .unsqueeze(-1)
                .to(outputs.last_hidden_state.dtype)
            )

            counts = content_mask.sum(dim=1).clamp(min=1)

            vector = (outputs.last_hidden_state * content_mask).sum(dim=1) / counts

            chunk_vectors.append(vector.squeeze(0).cpu())

            del (
                outputs,
                input_ids,
                attention_mask,
                special_mask,
                content_mask,
                counts,
                vector,
            )

            if start + chunk_length >= len(token_ids):
                break

    if not chunk_vectors:
        raise ValueError("No chunk embeddings were generated.")

    embedding = torch.stack(chunk_vectors).mean(dim=0).numpy()

    norm = np.linalg.norm(embedding)
    if norm > 0:
        embedding = embedding / norm

    if embedding.shape != (768,):
        raise ValueError(f"Expected 768 dimensions, got {embedding.shape}.")

    return embedding.astype(np.float32), len(token_ids), len(chunk_vectors)


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
    model = AutoModel.from_pretrained(MODEL_NAME).to(device)
    model.eval()

    embeddings = []
    metadata = []
    failed = []

    start_time = time.time()

    for index, path in enumerate(java_files, start=1):
        try:
            source = path.read_text(
                encoding="utf-8",
                errors="replace",
            )

            if not source.strip():
                print(f"[{index}/{len(java_files)}] Empty file: {path.name}")
                continue

            vector, token_count, chunk_count = embed_file(
                source,
                tokenizer,
                model,
                device,
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
                {
                    "file_path": path.relative_to(repo_path).as_posix(),
                    "error": str(exc),
                }
            )

            print(f"[{index}/{len(java_files)}] FAILED: {path.name}: {exc}")

    # Save embeddings and metadata if any files succeeded.
    if embeddings:
        vectors_path = output_path / f"{args.repo_id}_embeddings.npy"
        metadata_path = output_path / f"{args.repo_id}_metadata.csv"

        np.save(vectors_path, np.stack(embeddings))

        with metadata_path.open(
            "w",
            newline="",
            encoding="utf-8-sig",
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=list(metadata[0].keys()),
            )
            writer.writeheader()
            writer.writerows(metadata)

        print(f"Embeddings saved: {vectors_path}")
        print(f"Metadata saved: {metadata_path}")

    # Save the failed-file report, including an empty report if all succeeded.
    failed_path = output_path / f"{args.repo_id}_failed.csv"

    with failed_path.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["file_path", "error"],
        )
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
