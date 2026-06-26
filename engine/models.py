"""도메인 모델 — Target(모니터링 대상) 등."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Entity:
    name: str
    role: str = ""
    aliases: list[str] = field(default_factory=list)


@dataclass
class Target:
    id: str
    name: str
    keywords: list[str] = field(default_factory=list)
    entities: list[Entity] = field(default_factory=list)
    channels: list[dict] = field(default_factory=list)
    sources: dict = field(default_factory=dict)   # {naver:bool, youtube:bool, rss:bool, ...}
    schedule: dict = field(default_factory=dict)
    _raw: dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_doc(cls, doc_id: str, data: dict) -> "Target":
        entities = [
            Entity(
                name=e.get("name", ""),
                role=e.get("role", ""),
                aliases=e.get("aliases", []) or [],
            )
            for e in (data.get("entities") or [])
        ]
        return cls(
            id=doc_id,
            name=data.get("name", doc_id),
            keywords=data.get("keywords", []) or [],
            entities=entities,
            channels=data.get("channels", []) or [],
            sources=data.get("sources", {}) or {},
            schedule=data.get("schedule", {}) or {},
            _raw=data,
        )

    def search_keywords(self) -> list[str]:
        """수집 검색어 = 키워드 + 인물명 (중복 제거, 순서 유지)."""
        seen: set[str] = set()
        out: list[str] = []
        for kw in list(self.keywords) + [e.name for e in self.entities]:
            kw = (kw or "").strip()
            if kw and kw not in seen:
                seen.add(kw)
                out.append(kw)
        return out

    def relevance_terms(self) -> tuple[list[str], list[str]]:
        """(keywords, entity_terms) — 관련성 필터용. entity_terms 는 이름+별칭."""
        entity_terms: list[str] = []
        for e in self.entities:
            entity_terms.append(e.name)
            entity_terms.extend(e.aliases)
        return self.keywords, [t for t in entity_terms if t]

    def source_enabled(self, name: str, default: bool = True) -> bool:
        return bool(self.sources.get(name, default))

    def browser_site_keys(self) -> list[str]:
        """브라우저로 수집할 사이트 key 목록 (sources.sites). 'all' 가능."""
        return list(self.sources.get("sites", []) or [])

    def watch_accounts(self) -> list[dict]:
        """특정 계정 모니터링 목록 (watchAccounts) — 최상위 필드."""
        return list(self._raw.get("watchAccounts", []) or [])
