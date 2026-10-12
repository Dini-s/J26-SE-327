"""Save the embedding model into models/ (git-ignored) so the project runs offline from its own folder.

Usage (needs internet once):  python scripts/download_model.py [all-MiniLM-L6-v2]
Afterwards ``Embedder`` loads models/<name> automatically.
"""

import sys
from pathlib import Path

name = sys.argv[1] if len(sys.argv) > 1 else "all-MiniLM-L6-v2"
target = Path(__file__).resolve().parent.parent / "models" / name
from sentence_transformers import SentenceTransformer

SentenceTransformer(name).save(str(target))
print("saved to", target)
