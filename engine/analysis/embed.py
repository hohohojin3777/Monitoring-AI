"""임베딩 — 텍스트를 벡터로. 제공자 교체 가능.

provider:
- tfidf    : 의존성 0(sklearn). 배치 내 상대 비교용. 즉시 사용 가능, 정확도 보통.
- kosimcse : 로컬 한국어 문장 임베딩(고정밀). requirements-embed 설치 필요(torch).
- voyage   : Voyage AI 임베딩 API.
- openai   : OpenAI 임베딩 API.

모든 provider 는 embed(texts) -> L2 정규화된 (n, d) ndarray 를 반환한다.
정규화했으므로 코사인 유사도 = 내적.
"""
from __future__ import annotations

from typing import Protocol

import numpy as np
from loguru import logger

from ..config import Settings, get_settings


def _l2_normalize(mat: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> np.ndarray: ...


class TfidfEmbedder:
    """문자 n-gram TF-IDF. 언어 무관, 배치 단위로 fit. (cross-run 비교 X)"""

    def embed(self, texts: list[str]) -> np.ndarray:
        from sklearn.feature_extraction.text import TfidfVectorizer

        if not texts:
            return np.zeros((0, 1), dtype=np.float32)
        vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1, max_features=5000)
        mat = vec.fit_transform(texts).astype(np.float32).toarray()
        return _l2_normalize(mat)


class KoSimCSEEmbedder:
    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            logger.info("[embed] KoSimCSE 로드: {}", self._model_name)
            self._model = SentenceTransformer(self._model_name)
        return self._model

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, 1), dtype=np.float32)
        model = self._load()
        vecs = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(vecs, dtype=np.float32)


class _APIEmbedder:
    """Voyage/OpenAI 공통 — httpx 로 임베딩 API 호출."""

    def __init__(self, url: str, model: str, api_key: str, headers: dict) -> None:
        self._url, self._model, self._key, self._headers = url, model, api_key, headers

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, 1), dtype=np.float32)
        import httpx

        resp = httpx.post(
            self._url,
            headers=self._headers,
            json={"model": self._model, "input": texts},
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        vecs = np.asarray([d["embedding"] for d in data], dtype=np.float32)
        return _l2_normalize(vecs)


def get_embedder(settings: Settings | None = None) -> Embedder:
    s = settings or get_settings()
    provider = s.embed_provider

    if provider == "kosimcse":
        try:
            import sentence_transformers  # noqa: F401

            return KoSimCSEEmbedder(s.kosimcse_model)
        except ImportError:
            logger.warning("[embed] sentence-transformers 미설치 → tfidf 폴백")
            return TfidfEmbedder()

    if provider == "voyage" and s.voyage_api_key:
        return _APIEmbedder(
            "https://api.voyageai.com/v1/embeddings",
            "voyage-3",
            s.voyage_api_key,
            {"Authorization": f"Bearer {s.voyage_api_key}"},
        )

    if provider == "openai" and s.openai_api_key:
        return _APIEmbedder(
            "https://api.openai.com/v1/embeddings",
            "text-embedding-3-small",
            s.openai_api_key,
            {"Authorization": f"Bearer {s.openai_api_key}"},
        )

    if provider != "tfidf":
        logger.warning("[embed] '{}' 사용 불가 → tfidf 폴백", provider)
    return TfidfEmbedder()
