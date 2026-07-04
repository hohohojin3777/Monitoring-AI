"""Claude 보강 — 감정 분류, 클러스터 요약, 대응안 초안.

키가 없으면 안전하게 degrade(감정=neutral, 요약=제목). 환각 방지를 위해
'제공된 텍스트만 사용, 없는 사실 생성 금지'를 모든 프롬프트에 명시한다.
"""
from __future__ import annotations

import json
import re

from loguru import logger

from ..collectors.base import RawItem
from ..config import Settings, get_settings

_VALID = {"positive", "neutral", "negative", "attack"}
_JSON_RE = re.compile(r"\[.*\]|\{.*\}", re.DOTALL)


def _extract_json(text: str):
    m = _JSON_RE.search(text or "")
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


class ClaudeAnalyzer:
    def __init__(self, settings: Settings | None = None) -> None:
        self._s = settings or get_settings()
        self._client = None

    def available(self) -> bool:
        return bool(self._s.anthropic_api_key)

    def _get_client(self):
        if self._client is None:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(api_key=self._s.anthropic_api_key)
        return self._client

    async def _call(self, model: str, system: str, user: str, max_tokens: int = 1024) -> str:
        client = self._get_client()
        resp = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")

    # ── 감정 분류 (배치) ───────────────────────────────────────
    async def classify_sentiments(
        self, items: list[RawItem], target_name: str, batch_size: int = 20
    ) -> None:
        if not items:
            return
        if not self.available():
            for it in items:
                it.sentiment = it.sentiment or "neutral"
            logger.warning("[claude] 키 없음 — 감정=neutral 처리")
            return

        system = (
            f"너는 '{target_name}' 관점의 여론 분석가다. 각 글이 '{target_name}'에 대해 "
            "positive(우호), neutral(중립), negative(부정), attack(공격/비방) 중 무엇인지 분류한다. "
            "제공된 텍스트만 근거로 판단하고 없는 사실을 만들지 마라. "
            '반드시 JSON 배열로 라벨만 반환: ["neutral","negative",...] (입력 순서와 동일 길이).'
        )
        for start in range(0, len(items), batch_size):
            chunk = items[start : start + batch_size]
            numbered = "\n".join(
                f"{i}. {it.text[:200]}" for i, it in enumerate(chunk)
            )
            try:
                out = await self._call(
                    self._s.claude_model_fast, system, numbered, max_tokens=512
                )
                labels = _extract_json(out) or []
            except Exception as e:  # noqa: BLE001
                logger.error("[claude] 감정 분류 실패: {}", e)
                labels = []
            for i, it in enumerate(chunk):
                label = labels[i] if i < len(labels) else "neutral"
                it.sentiment = label if label in _VALID else "neutral"

    # ── 클러스터 요약 ──────────────────────────────────────────
    async def summarize_cluster(self, title: str, sample_texts: list[str]) -> str:
        if not self.available() or not sample_texts:
            return title
        system = (
            "여러 매체에 보도된 같은 사건을 1~2문장으로 객관 요약한다. "
            "제공된 텍스트만 사용하고 추측·과장 금지."
        )
        joined = "\n---\n".join(t[:300] for t in sample_texts[:8])
        try:
            return (await self._call(self._s.claude_model_fast, system, joined, 256)).strip() or title
        except Exception as e:  # noqa: BLE001
            logger.error("[claude] 요약 실패: {}", e)
            return title

    # ── eventKey 배치 추출 ────────────────────────────────────────
    async def extract_event_keys(
        self, items: list[RawItem], batch_size: int = 15
    ) -> None:
        """각 item에 event_key (str) 를 채운다. 이미 있으면 건너뜀.

        event_key 형식: "핵심이벤트/장소/날짜" — 같은 사건이면 동일, 다른 사건이면 다름.
        키 없으면 title 해시 폴백.
        """
        targets = [it for it in items if not getattr(it, "event_key", None)]
        if not targets:
            return
        if not self.available():
            import hashlib
            for it in targets:
                it.event_key = hashlib.md5((it.title or it.text[:50]).encode()).hexdigest()[:12]
            return

        system = (
            "정치 뉴스 기사 제목 목록을 보고, 각 기사가 어떤 사건(이벤트)을 다루는지 "
            "핵심 이벤트 키를 추출해라.\n"
            "규칙:\n"
            "- 형식: '핵심이벤트명/핵심장소/날짜(YYYY-MM-DD)'\n"
            "- 같은 사건이면 반드시 같은 키, 다른 사건이면 반드시 다른 키\n"
            "- 후보 이름만 같다고 같은 이벤트가 아님\n"
            "- 날짜 모르면 'unknown' 사용\n"
            "- 반드시 JSON 배열로만 반환: [\"키1\", \"키2\", ...] (입력 순서와 동일 길이)\n"
            "예시: [\"워크숍_한테이블신경전/국회/2026-07-03\", \"주말행보_3인3색/익산·광주/2026-07-04\"]"
        )

        for start in range(0, len(targets), batch_size):
            chunk = targets[start : start + batch_size]
            numbered = "\n".join(
                f"{i}. {it.title or it.text[:120]}" for i, it in enumerate(chunk)
            )
            try:
                out = await self._call(
                    self._s.claude_model_fast, system, numbered, max_tokens=512
                )
                keys = _extract_json(out) or []
            except Exception as e:  # noqa: BLE001
                logger.error("[claude] eventKey 추출 실패: {}", e)
                keys = []
            import hashlib
            for i, it in enumerate(chunk):
                if i < len(keys) and isinstance(keys[i], str) and keys[i]:
                    it.event_key = keys[i].strip()[:120]
                else:
                    it.event_key = hashlib.md5((it.title or it.text[:50]).encode()).hexdigest()[:12]
        logger.info("[claude] eventKey 추출 완료: {}건", len(targets))

    # ── 대응안 초안 (관리자 'AI 추천' 버튼) ─────────────────────
    async def suggest_response(self, cluster_info: dict) -> dict:
        """{plan, steps:[{order,text}], note} 반환. 관리자가 검토·수정 후 발행."""
        if not self.available():
            return {"plan": "", "steps": [], "note": "Claude 키 없음"}
        system = (
            "정치 캠프 위기대응 전문가로서, 주어진 이슈에 대한 대응 방안과 단계별 대응 순서를 제안한다. "
            "사실관계는 제공된 정보에만 근거하고, 외부 발송 콘텐츠는 반드시 변호사 검토가 필요함을 note 에 명시한다. "
            'JSON 으로만 반환: {"plan": "...", "steps": [{"order":1,"text":"..."}], "note": "..."}'
        )
        user = json.dumps(cluster_info, ensure_ascii=False)
        try:
            out = await self._call(self._s.claude_model_main, system, user, 1024)
            data = _extract_json(out) or {}
        except Exception as e:  # noqa: BLE001
            logger.error("[claude] 대응안 생성 실패: {}", e)
            return {"plan": "", "steps": [], "note": f"생성 실패: {e}"}
        data.setdefault("plan", "")
        data.setdefault("steps", [])
        data.setdefault("note", "외부 발송 콘텐츠는 캠프 자문 변호사 사전 검토 필요.")
        return data
