from __future__ import annotations

import re

from importlib.metadata import (
    PackageNotFoundError,
    version,
)

import numpy as np

from sklearn.feature_extraction.text import (
    TfidfVectorizer,
)
from sklearn.metrics.pairwise import (
    cosine_similarity,
)

from agents.quality_agent.schemas import (
    CandidateEvidenceMatch,
    RequirementValidationUnit,
    ValidationEvidence,
)

from shared.embeddings.embedder import (
    SentenceTransformerEmbedder,
)


class EvidenceRetrievalService:
    STOPWORDS = {
        "a",
        "an",
        "the",
        "is",
        "are",
        "be",
        "to",
        "of",
        "for",
        "and",
        "or",
        "shall",
        "should",
        "must",
        "with",
        "when",
        "while",
        "that",
        "this",
    }

    def __init__(
        self,
        embedding_model: str,
    ):
        self.embedding_model = (
            embedding_model
        )

        self.embedder = (
            SentenceTransformerEmbedder(
                embedding_model
            )
        )

    def retrieve(
        self,
        rvu:
        RequirementValidationUnit,
        evidence: list[
            ValidationEvidence
        ],
        method: str,
        top_k: int = 5,
    ) -> list[
        CandidateEvidenceMatch
    ]:

        if not evidence:
            return []

        method = method.lower()

        query_text = (
            self._build_rvu_text(
                rvu
            )
        )

        evidence_texts = [
            self._build_evidence_text(
                item
            )
            for item
            in evidence
        ]

        if method == "keyword":
            scores = np.array(
                [
                    self._keyword_score(
                        query_text,
                        evidence_text,
                    )
                    for evidence_text
                    in evidence_texts
                ]
            )

            model_name = (
                "keyword-jaccard"
            )

            model_version = "2.0"

        elif method == "tfidf":
            scores = (
                self._tfidf_scores(
                    query_text,
                    evidence_texts,
                )
            )

            model_name = (
                "scikit-learn-tfidf"
            )

            try:
                model_version = (
                    version(
                        "scikit-learn"
                    )
                )

            except PackageNotFoundError:
                model_version = None

        elif method == "semantic":
            scores = (
                self._semantic_scores(
                    query_text,
                    evidence_texts,
                )
            )

            model_name = (
                self.embedding_model
            )

            try:
                model_version = (
                    version(
                        "sentence-transformers"
                    )
                )

            except PackageNotFoundError:
                model_version = None

        else:
            raise ValueError(
                "method must be "
                "keyword, tfidf, "
                "or semantic"
            )

        top_k = min(
            top_k,
            len(evidence),
        )

        ranking = np.argsort(
            scores
        )[::-1][:top_k]

        results: list[
            CandidateEvidenceMatch
        ] = []

        for rank, index in enumerate(
            ranking,
            start=1,
        ):
            item = evidence[
                int(index)
            ]

            results.append(
                CandidateEvidenceMatch(
                    rvu_id=(
                        rvu.rvu_id
                    ),
                    evidence_id=(
                        item.evidence_id
                    ),
                    evidence_title=(
                        item.title
                    ),
                    evidence_type=(
                        item.evidence_type
                    ),
                    retrieval_method=(
                        method
                    ),
                    similarity_score=(
                        round(
                            float(
                                scores[
                                    index
                                ]
                            ),
                            6,
                        )
                    ),
                    rank=rank,
                    model_name=(
                        model_name
                    ),
                    model_version=(
                        model_version
                    ),
                    source_path=(
                        item.source_path
                    ),
                    source_tool=(
                        item.source_tool
                    ),
                    execution_status=(
                        item
                        .execution_status
                    ),
                    synthetic=(
                        item.synthetic
                    ),
                )
            )

        return results

    def _semantic_scores(
        self,
        query_text: str,
        evidence_texts: list[str],
    ) -> np.ndarray:

        embeddings = (
            self.embedder.encode(
                [
                    query_text,
                    *evidence_texts,
                ]
            )
        )

        query_embedding = (
            embeddings[0]
        )

        evidence_embeddings = (
            embeddings[1:]
        )

        return (
            evidence_embeddings
            @ query_embedding
        )

    @staticmethod
    def _tfidf_scores(
        query_text: str,
        evidence_texts: list[str],
    ) -> np.ndarray:

        vectorizer = (
            TfidfVectorizer(
                stop_words="english",
                ngram_range=(1, 2),
            )
        )

        matrix = (
            vectorizer
            .fit_transform(
                [
                    query_text,
                    *evidence_texts,
                ]
            )
        )

        return cosine_similarity(
            matrix[0:1],
            matrix[1:],
        )[0]

    def _keyword_score(
        self,
        query_text: str,
        evidence_text: str,
    ) -> float:

        query_tokens = (
            self._tokens(
                query_text
            )
        )

        evidence_tokens = (
            self._tokens(
                evidence_text
            )
        )

        union = (
            query_tokens
            | evidence_tokens
        )

        if not union:
            return 0.0

        return (
            len(
                query_tokens
                & evidence_tokens
            )
            / len(union)
        )

    def _tokens(
        self,
        text: str,
    ) -> set[str]:

        tokens = {
            token.lower()
            for token
            in re.findall(
                r"[A-Za-z0-9]+",
                text,
            )
        }

        return (
            tokens
            - self.STOPWORDS
        )

    @staticmethod
    def _build_rvu_text(
        rvu:
        RequirementValidationUnit,
    ) -> str:

        return " ".join(
            value
            for value in [
                rvu.atomic_text,
                rvu.behavior_type,
                " ".join(
                    rvu.constraints
                ),
            ]
            if value
        )

    @staticmethod
    def _build_evidence_text(
        evidence:
        ValidationEvidence,
    ) -> str:

        values = [
            evidence.title,
            evidence.description,

            " ".join(
                evidence
                .preconditions
            ),

            " ".join(
                evidence.inputs
            ),

            " ".join(
                evidence.steps
            ),

            (
                evidence
                .expected_result
                or ""
            ),

            " ".join(
                evidence.assertions
            ),

            evidence.metric or "",
            evidence.percentile or "",
            evidence.scope or "",
        ]

        if (
            evidence.threshold
            is not None
        ):
            values.append(
                str(
                    evidence.threshold
                )
            )

        if (
            evidence.load
            is not None
        ):
            values.append(
                f"{evidence.load} "
                f"concurrent users"
            )

        if (
            evidence.duration_seconds
            is not None
        ):
            values.append(
                f"{evidence.duration_seconds} "
                f"seconds"
            )

        return " ".join(
            value
            for value
            in values
            if value
        )