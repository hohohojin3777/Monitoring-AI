"""중앙 후보 설정 — 후보군 변경 시 이 파일만 수정하면 전체 반영됨."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class CandidateConfig:
    name: str
    color: str
    current_candidate: bool
    candidate_group: Literal["party_leader_main", "former_or_potential", "other"]
    display_group: str
    issue_tracking: bool
    poll_main_candidate: bool
    dashboard_main_candidate: bool
    aliases: list[str] = field(default_factory=list)


CANDIDATE_CONFIGS: list[CandidateConfig] = [
    CandidateConfig(
        name="김민석", color="#005BAC",
        current_candidate=True, candidate_group="party_leader_main",
        display_group="당대표 핵심 후보", issue_tracking=True,
        poll_main_candidate=True, dashboard_main_candidate=True,
        aliases=["김민석"],
    ),
    CandidateConfig(
        name="정청래", color="#7950f2",
        current_candidate=True, candidate_group="party_leader_main",
        display_group="당대표 핵심 후보", issue_tracking=True,
        poll_main_candidate=True, dashboard_main_candidate=True,
        aliases=["정청래"],
    ),
    CandidateConfig(
        name="송영길", color="#e6a817",
        current_candidate=True, candidate_group="party_leader_main",
        display_group="당대표 핵심 후보", issue_tracking=True,
        poll_main_candidate=True, dashboard_main_candidate=True,
        aliases=["송영길"],
    ),
    CandidateConfig(
        name="고민정", color="#0d9488",
        current_candidate=True, candidate_group="party_leader_main",
        display_group="당대표 핵심 후보", issue_tracking=True,
        poll_main_candidate=True, dashboard_main_candidate=True,
        aliases=["고민정"],
    ),
    CandidateConfig(
        name="김용민", color="#9ca3af",
        current_candidate=False, candidate_group="former_or_potential",
        display_group="기타/과거 언급", issue_tracking=True,
        poll_main_candidate=False, dashboard_main_candidate=False,
        aliases=["김용민"],
    ),
    CandidateConfig(
        name="김두관", color="#0c8599",
        current_candidate=False, candidate_group="other",
        display_group="기타", issue_tracking=False,
        poll_main_candidate=False, dashboard_main_candidate=False,
        aliases=["김두관"],
    ),
    CandidateConfig(
        name="강훈식", color="#d6336c",
        current_candidate=False, candidate_group="other",
        display_group="기타", issue_tracking=False,
        poll_main_candidate=False, dashboard_main_candidate=False,
        aliases=["강훈식"],
    ),
]

# 편의 접근자
MAIN_CANDIDATES      = [c for c in CANDIDATE_CONFIGS if c.dashboard_main_candidate]
POLL_MAIN_CANDIDATES = [c for c in CANDIDATE_CONFIGS if c.poll_main_candidate]
ALL_CANDIDATES       = CANDIDATE_CONFIGS

MAIN_CANDIDATE_NAMES      = [c.name for c in MAIN_CANDIDATES]
POLL_MAIN_CANDIDATE_NAMES = [c.name for c in POLL_MAIN_CANDIDATES]
ALL_CANDIDATE_NAMES       = [c.name for c in ALL_CANDIDATES]
