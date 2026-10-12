"""Thin wrapper around sentence-transformers, shared by all agents."""

import os
from pathlib import Path
from typing import Any, Optional, Sequence

from dotenv import load_dotenv


LOCAL_MODELS_DIR = Path(__file__).resolve().parents[2] / "models"  # git-ignored copies of the models, so runs work offline


class Embedder:
    """Turns text into dense vectors using a sentence-transformers model.

    The model is loaded lazily on first use so importing this module (and
    constructing the class in tests) never triggers a model download.
    """

    def __init__(self, model_name: Optional[str] = None) -> None:
        """Create an embedder.

        Args:
            model_name: sentence-transformers model name; if ``models/<name>`` exists in the project it is
                loaded from there (no download, works offline). Falls back to the
                ``EMBEDDING_MODEL_NAME`` environment variable.

        Raises:
            ValueError: If no model name is given or configured.
        """
        load_dotenv()
        name = model_name or os.getenv("EMBEDDING_MODEL_NAME")
        if not name:
            raise ValueError(
                "No embedding model configured: pass model_name or set EMBEDDING_MODEL_NAME."
            )
        local = LOCAL_MODELS_DIR / name
        self.model_name: str = str(local) if local.is_dir() else name  # a copy in models/ wins over the download cache
        self._model: Any = None

    @property
    def model(self) -> Any:
        """The underlying SentenceTransformer, loaded on first access."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed_text(self, text: str) -> list[float]:
        """Embed a single string.

        Args:
            text: Text to embed.

        Returns:
            The embedding vector.
        """
        return self.model.encode(text, convert_to_numpy=True).tolist()

    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed many strings in one call (much faster than looping).

        Args:
            texts: Texts to embed.

        Returns:
            One embedding vector per input text, in order. Empty input gives ``[]``.
        """
        if not texts:
            return []
        return self.model.encode(list(texts), convert_to_numpy=True).tolist()
