from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum


class EvidenceType(str, Enum):
    POSITIVE = "positive"
    FREE = "free"
    NON_CONFIRMATION = "non_confirmation"
    OCCLUDED = "occluded"
    UNKNOWN = "unknown"
    ACCESS_BLOCKED = "access_blocked"
    SCENE_CHANGED = "scene_changed"


class DecisionType(str, Enum):
    TRUST = "trust"
    VERIFY = "verify"
    SEARCH = "search"
    RETIRE = "retire"


@dataclass(frozen=True)
class MemoryBelief:
    p_existence: float
    p_location_valid: float
    p_usable: float

    def __post_init__(self) -> None:
        for name, value in (
            ("p_existence", self.p_existence),
            ("p_location_valid", self.p_location_valid),
            ("p_usable", self.p_usable),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")

    @property
    def p_valid(self) -> float:
        return self.p_existence * self.p_location_valid * self.p_usable


@dataclass(frozen=True)
class EvidenceEvent:
    evidence_type: EvidenceType
    strength: float = 1.0
    dt: float = 1.0
    quarantined: bool = False

    def __post_init__(self) -> None:
        if self.strength < 0.0:
            raise ValueError("strength must be non-negative")
        if self.dt < 0.0:
            raise ValueError("dt must be non-negative")


@dataclass(frozen=True)
class DecisionContext:
    d_nav: float
    d_verify: float
    c_fail: float
    c_search: float
    b_remaining: float
    user_requested_specific_instance: bool = False
    verification_repeatedly_failed: bool = False
    current_positive_evidence: bool = False

    def __post_init__(self) -> None:
        for name, value in (
            ("d_nav", self.d_nav),
            ("d_verify", self.d_verify),
            ("c_fail", self.c_fail),
            ("c_search", self.c_search),
            ("b_remaining", self.b_remaining),
        ):
            if value < 0.0:
                raise ValueError(f"{name} must be non-negative")


@dataclass(frozen=True)
class DecisionResult:
    decision: DecisionType
    p_valid: float
    expected_costs: dict[DecisionType, float]


class UsabilityUpdater:
    def __init__(self, retire_threshold: float = 0.2) -> None:
        if not 0.0 <= retire_threshold <= 1.0:
            raise ValueError("retire_threshold must be in [0, 1]")
        self.retire_threshold = retire_threshold

    def apply(self, belief: MemoryBelief, event: EvidenceEvent) -> MemoryBelief:
        if event.quarantined and event.evidence_type is not EvidenceType.POSITIVE:
            return belief
        if event.evidence_type is EvidenceType.POSITIVE:
            return MemoryBelief(
                p_existence=_increase(belief.p_existence, 0.25, event),
                p_location_valid=_increase(belief.p_location_valid, 0.45, event),
                p_usable=_increase(belief.p_usable, 0.55, event),
            )
        if event.evidence_type is EvidenceType.FREE:
            return MemoryBelief(
                p_existence=_decay(belief.p_existence, 0.04, event),
                p_location_valid=_decay(belief.p_location_valid, 0.85, event),
                p_usable=_decay(belief.p_usable, 0.45, event),
            )
        if event.evidence_type is EvidenceType.NON_CONFIRMATION:
            return MemoryBelief(
                p_existence=belief.p_existence,
                p_location_valid=_decay(belief.p_location_valid, 0.05, event),
                p_usable=_decay(belief.p_usable, 0.24, event),
            )
        if event.evidence_type is EvidenceType.OCCLUDED:
            return MemoryBelief(
                p_existence=belief.p_existence,
                p_location_valid=_decay(belief.p_location_valid, 0.02, event),
                p_usable=_decay(belief.p_usable, 0.12, event),
            )
        if event.evidence_type is EvidenceType.UNKNOWN:
            return MemoryBelief(
                p_existence=belief.p_existence,
                p_location_valid=belief.p_location_valid,
                p_usable=_decay(belief.p_usable, 0.02, event),
            )
        if event.evidence_type is EvidenceType.ACCESS_BLOCKED:
            return MemoryBelief(
                p_existence=belief.p_existence,
                p_location_valid=_decay(belief.p_location_valid, 0.04, event),
                p_usable=_decay(belief.p_usable, 0.45, event),
            )
        if event.evidence_type is EvidenceType.SCENE_CHANGED:
            return MemoryBelief(
                p_existence=_decay(belief.p_existence, 0.03, event),
                p_location_valid=_decay(belief.p_location_valid, 0.30, event),
                p_usable=_decay(belief.p_usable, 0.35, event),
            )
        raise ValueError(f"unknown evidence type: {event.evidence_type}")

    def should_retire(self, belief: MemoryBelief) -> bool:
        return belief.p_usable < self.retire_threshold


class UsabilityDecisionPolicy:
    def __init__(
        self,
        retire_threshold: float = 0.2,
        current_positive_trust_threshold: float = 0.88,
    ) -> None:
        if not 0.0 <= retire_threshold <= 1.0:
            raise ValueError("retire_threshold must be in [0, 1]")
        if not 0.0 <= current_positive_trust_threshold <= 1.0:
            raise ValueError("current_positive_trust_threshold must be in [0, 1]")
        self.retire_threshold = retire_threshold
        self.current_positive_trust_threshold = current_positive_trust_threshold

    def choose(
        self,
        belief: MemoryBelief,
        context: DecisionContext,
    ) -> DecisionResult:
        p_valid = belief.p_valid
        search_cost = context.c_search
        trust_cost = (
            p_valid * context.d_nav
            + (1.0 - p_valid)
            * (context.d_nav + context.c_fail + context.c_search)
        )
        verify_cost = (
            context.d_verify
            + p_valid * context.d_nav
            + (1.0 - p_valid) * search_cost
        )
        retire_penalty = 0.0 if not context.user_requested_specific_instance else context.c_fail
        retire_cost = search_cost + retire_penalty
        costs = {
            DecisionType.TRUST: trust_cost,
            DecisionType.VERIFY: verify_cost,
            DecisionType.SEARCH: search_cost,
            DecisionType.RETIRE: retire_cost,
        }

        if (
            belief.p_usable < self.retire_threshold
            and not context.user_requested_specific_instance
            and (
                context.verification_repeatedly_failed
                or retire_cost <= min(trust_cost, verify_cost, search_cost)
            )
        ):
            return DecisionResult(
                decision=DecisionType.RETIRE,
                p_valid=p_valid,
                expected_costs=costs,
            )

        if (
            context.current_positive_evidence
            and p_valid >= self.current_positive_trust_threshold
            and belief.p_usable >= self.retire_threshold
        ):
            return DecisionResult(
                decision=DecisionType.TRUST,
                p_valid=p_valid,
                expected_costs=costs,
            )

        active_costs = {
            DecisionType.TRUST: trust_cost,
            DecisionType.VERIFY: verify_cost,
            DecisionType.SEARCH: search_cost,
        }
        decision = min(active_costs, key=active_costs.get)
        return DecisionResult(
            decision=decision,
            p_valid=p_valid,
            expected_costs=costs,
        )


def _decay(value: float, rate: float, event: EvidenceEvent) -> float:
    return _clamp01(value * math.exp(-rate * event.strength * event.dt))


def _increase(value: float, rate: float, event: EvidenceEvent) -> float:
    gain = 1.0 - math.exp(-rate * event.strength * event.dt)
    return _clamp01(value + (1.0 - value) * gain)


def _clamp01(value: float) -> float:
    return min(1.0, max(0.0, value))
