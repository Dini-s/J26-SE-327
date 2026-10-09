from __future__ import annotations

import numpy as np


class SentenceTransformerEmbedder:
    def __init__(
        self,
        model_name: str,
    ):
        self.model_name = (
            model_name
        )

        self._model = None

    @property
    def model(
        self,
    ):
        if self._model is None:
            from sentence_transformers import (
                SentenceTransformer,
            )

            self._model = (
                SentenceTransformer(
                    self.model_name
                )
            )

        return self._model

    def encode(
        self,
        texts: list[str],
    ) -> np.ndarray:

        if not texts:
            return np.empty(
                (0, 0)
            )

        return self.model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )