"""환경변수·상수 중앙 관리. 하드코딩 금지 — 모든 키는 .env / 환경변수에서 로드."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── 네이버 검색 API ──
    naver_client_id: str = ""
    naver_client_secret: str = ""

    # ── 유튜브 Data API ──
    youtube_api_key: str = ""

    # ── Anthropic ──
    anthropic_api_key: str = ""
    claude_model_fast: str = "claude-haiku-4-5-20251001"
    claude_model_main: str = "claude-sonnet-4-6"

    # ── Firebase (Admin SDK) ──
    # 로컬: 파일 경로 사용 (serviceAccountKey.json)
    # Railway: FIREBASE_CREDENTIALS_JSON 에 JSON 문자열 통째로 붙여넣기 (파일 불필요)
    firebase_credentials_path: str = "serviceAccountKey.json"
    firebase_credentials_json: str = ""  # JSON 문자열 (Railway 등 파일 못 쓰는 환경)
    firebase_project_id: str = ""

    # ── 임베딩 ──
    embed_provider: Literal["kosimcse", "voyage", "openai", "tfidf"] = "tfidf"
    kosimcse_model: str = "jhgan/ko-sroberta-multitask"
    voyage_api_key: str = ""
    openai_api_key: str = ""

    # ── 클러스터링 ──
    # 신경망 임베딩(kosimcse/voyage/openai)용 임계값
    cluster_similarity_threshold: float = 0.62
    # TF-IDF(문자 n-gram)는 유사도가 낮게 나와 별도 임계값 사용
    tfidf_similarity_threshold: float = 0.30
    window_days: int = 30

    def similarity_threshold(self) -> float:
        return (
            self.tfidf_similarity_threshold
            if self.embed_provider == "tfidf"
            else self.cluster_similarity_threshold
        )

    # ── 스케줄 ──
    collect_interval_minutes: int = 30

    # ── 스크래핑 / 브라우저 직접 수집 ──
    apify_api_token: str = ""
    headless: bool = True
    # 로그인 세션이 저장되는 Chrome 프로필 디렉토리 (login.py 로 1회 로그인 후 재사용)
    browser_profile_dir: str = ".browser_profile"
    # 사이트·키워드당 최대 수집 건수
    scrape_limit_per_site: int = 30
    # 스크랩 글의 게시일을 못 구하면 수집 제외(작년글 등 검색 잔재 차단). False 면 보관.
    scrape_require_date: bool = True

    # ── 위기 등급 임계값 (기본값, target 설정으로 override 가능) ──
    grade_red_pattern_count: int = 3
    grade_orange_pattern_count: int = 2
    grade_red_post_count: int = 300
    grade_orange_post_count: int = 30
    negative_keyword_threshold: int = 3   # 위험 키워드 누적 빈도
    multiplatform_min: int = 2            # 부정 다플랫폼 최소 매체 수
    media_diversity_min: int = 3          # 매체 다양성 최소 플랫폼 수

    # ── 위험 키워드 사전 (부정 키워드 패턴 감지용) ──
    risk_keywords: list[str] = Field(
        default_factory=lambda: [
            "의혹", "논란", "비리", "수사", "고발", "폭로", "특혜",
            "거짓", "막말", "사퇴", "스캔들", "부정", "조작", "은폐",
        ]
    )

    def has_firebase_credentials(self) -> bool:
        """JSON 문자열 또는 파일 중 하나라도 있으면 True."""
        import os
        return bool(self.firebase_credentials_json) or os.path.exists(self.firebase_credentials_path)

    def require(self, *names: str) -> None:
        """필수 키가 비어있으면 명확한 오류를 던진다."""
        missing = [n for n in names if not getattr(self, n, None)]
        if missing:
            raise RuntimeError(
                f"필수 환경변수가 비어있습니다: {', '.join(missing)} — .env 를 확인하세요."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
