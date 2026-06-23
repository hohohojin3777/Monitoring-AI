"""수집기 — 각 소스에서 RawItem 을 가져온다.

모든 수집기는 base.Collector 를 구현하며, 파이프라인은 RawItem 으로만 다룬다.
"""
from .base import Collector, RawItem, canonical_url, strip_html

__all__ = ["Collector", "RawItem", "canonical_url", "strip_html"]
