import math

from objectnav_core.memory.usability import (
    DecisionContext,
    DecisionType,
    EvidenceEvent,
    EvidenceType,
    MemoryBelief,
    UsabilityDecisionPolicy,
    UsabilityUpdater,
)


def test_non_confirmation_and_access_blocked_retire_ghost_memory() -> None:
    updater = UsabilityUpdater()
    belief = MemoryBelief(
        p_existence=0.95,
        p_location_valid=0.9,
        p_usable=0.9,
    )

    for _ in range(5):
        belief = updater.apply(belief, EvidenceEvent(EvidenceType.NON_CONFIRMATION))
    for _ in range(2):
        belief = updater.apply(belief, EvidenceEvent(EvidenceType.ACCESS_BLOCKED))

    assert belief.p_existence > 0.8
    assert belief.p_usable < 0.25
    assert updater.should_retire(belief)


def test_occluded_and_unknown_preserve_existence_but_reduce_usability_slowly() -> None:
    updater = UsabilityUpdater()
    belief = MemoryBelief(
        p_existence=0.92,
        p_location_valid=0.88,
        p_usable=0.85,
    )

    for _ in range(4):
        belief = updater.apply(belief, EvidenceEvent(EvidenceType.OCCLUDED))
        belief = updater.apply(belief, EvidenceEvent(EvidenceType.UNKNOWN))

    assert belief.p_existence == 0.92
    assert belief.p_location_valid > 0.75
    assert 0.25 < belief.p_usable < 0.85


def test_positive_evidence_revives_retired_memory_without_overflowing_probabilities() -> None:
    updater = UsabilityUpdater()
    belief = MemoryBelief(
        p_existence=0.75,
        p_location_valid=0.22,
        p_usable=0.12,
    )

    revived = updater.apply(
        belief,
        EvidenceEvent(EvidenceType.POSITIVE, strength=2.0),
    )

    assert revived.p_existence > belief.p_existence
    assert revived.p_location_valid > belief.p_location_valid
    assert revived.p_usable > belief.p_usable
    assert revived.p_existence <= 1.0
    assert revived.p_location_valid <= 1.0
    assert revived.p_usable <= 1.0


def test_free_evidence_hits_location_more_than_existence() -> None:
    updater = UsabilityUpdater()
    belief = MemoryBelief(
        p_existence=0.9,
        p_location_valid=0.9,
        p_usable=0.9,
    )

    updated = updater.apply(belief, EvidenceEvent(EvidenceType.FREE))

    assert updated.p_location_valid < 0.45
    assert updated.p_usable < belief.p_usable
    assert updated.p_existence > 0.8


def test_quarantined_negative_evidence_does_not_clear_memory() -> None:
    updater = UsabilityUpdater()
    belief = MemoryBelief(
        p_existence=0.9,
        p_location_valid=0.9,
        p_usable=0.9,
    )

    for _ in range(20):
        belief = updater.apply(
            belief,
            EvidenceEvent(EvidenceType.FREE, quarantined=True),
        )

    assert belief == MemoryBelief(
        p_existence=0.9,
        p_location_valid=0.9,
        p_usable=0.9,
    )


def test_decision_policy_prefers_verify_for_uncertain_cheap_verification() -> None:
    policy = UsabilityDecisionPolicy()
    result = policy.choose(
        MemoryBelief(p_existence=0.85, p_location_valid=0.65, p_usable=0.65),
        DecisionContext(
            d_nav=12.0,
            d_verify=2.0,
            c_fail=4.0,
            c_search=30.0,
            b_remaining=60.0,
        ),
    )

    assert result.decision is DecisionType.VERIFY
    assert math.isclose(
        result.p_valid,
        0.85 * 0.65 * 0.65,
        rel_tol=1e-12,
    )


def test_decision_policy_does_not_clip_failed_trust_into_a_cheap_gamble() -> None:
    policy = UsabilityDecisionPolicy()
    result = policy.choose(
        MemoryBelief(
            p_existence=0.5006860759990526,
            p_location_valid=0.30975371300498283,
            p_usable=0.20863488197699184,
        ),
        DecisionContext(
            d_nav=12.260317472151208,
            d_verify=2.392239780554443,
            c_fail=8.512317704341259,
            c_search=57.59063419781607,
            b_remaining=47.27821320409082,
        ),
    )

    assert result.p_valid < 0.04
    assert result.decision is not DecisionType.TRUST
    assert result.expected_costs[DecisionType.TRUST] > result.expected_costs[DecisionType.VERIFY]


def test_decision_policy_retires_low_usability_default_memory() -> None:
    policy = UsabilityDecisionPolicy(retire_threshold=0.2)
    result = policy.choose(
        MemoryBelief(p_existence=0.85, p_location_valid=0.5, p_usable=0.08),
        DecisionContext(
            d_nav=10.0,
            d_verify=15.0,
            c_fail=5.0,
            c_search=18.0,
            b_remaining=40.0,
            verification_repeatedly_failed=True,
        ),
    )

    assert result.decision is DecisionType.RETIRE


def test_decision_policy_trusts_high_validity_memory() -> None:
    policy = UsabilityDecisionPolicy()
    result = policy.choose(
        MemoryBelief(p_existence=0.98, p_location_valid=0.95, p_usable=0.95),
        DecisionContext(
            d_nav=6.0,
            d_verify=5.0,
            c_fail=5.0,
            c_search=35.0,
            b_remaining=50.0,
        ),
    )

    assert result.decision is DecisionType.TRUST


def test_decision_policy_trusts_current_positive_high_validity_memory() -> None:
    policy = UsabilityDecisionPolicy()
    belief = MemoryBelief(
        p_existence=0.9550671035882778,
        p_location_valid=0.9644608361976817,
        p_usable=0.9741932704265424,
    )
    context = DecisionContext(
        d_nav=2.0,
        d_verify=1.5,
        c_fail=14.0,
        c_search=18.0,
        b_remaining=10.0,
    )

    assert policy.choose(belief, context).decision is DecisionType.VERIFY
    assert (
        policy.choose(
            belief,
            DecisionContext(
                d_nav=2.0,
                d_verify=1.5,
                c_fail=14.0,
                c_search=18.0,
                b_remaining=10.0,
                current_positive_evidence=True,
            ),
        ).decision
        is DecisionType.TRUST
    )
