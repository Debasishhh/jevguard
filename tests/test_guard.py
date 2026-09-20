"""Unit tests for verdict composition. No network calls — tests the pure
threshold logic directly."""

from jevguard.guard import Verdict, _compose


def test_allow_when_all_signals_low():
    verdict, reasons = _compose(
        jailbreak=0.05, injection=0.1, credential=0.0, escalation=0.0, severity=0.2
    )
    assert verdict == Verdict.ALLOW
    assert reasons == []


def test_block_on_high_jailbreak_signal():
    verdict, reasons = _compose(
        jailbreak=0.95, injection=0.1, credential=0.0, escalation=0.0, severity=0.3
    )
    assert verdict == Verdict.BLOCK
    assert "jailbreak_attempt" in reasons


def test_block_on_severe_policy_violation():
    verdict, reasons = _compose(
        jailbreak=0.1, injection=0.1, credential=0.0, escalation=0.0, severity=2.8
    )
    assert verdict == Verdict.BLOCK
    assert "policy_violation_severity" in reasons


def test_block_on_gradual_escalation():
    verdict, reasons = _compose(
        jailbreak=0.1, injection=0.1, credential=0.0, escalation=0.9, severity=0.3
    )
    assert verdict == Verdict.BLOCK
    assert "gradual_escalation" in reasons


def test_flag_on_mid_range_signal():
    verdict, reasons = _compose(
        jailbreak=0.6, injection=0.1, credential=0.0, escalation=0.0, severity=0.3
    )
    assert verdict == Verdict.FLAG
    assert "jailbreak_attempt" in reasons


def test_flag_on_mid_severity():
    verdict, reasons = _compose(
        jailbreak=0.1, injection=0.1, credential=0.0, escalation=0.0, severity=1.5
    )
    assert verdict == Verdict.FLAG


def test_credential_request_blocks():
    verdict, reasons = _compose(
        jailbreak=0.0, injection=0.0, credential=0.9, escalation=0.0, severity=0.0
    )
    assert verdict == Verdict.BLOCK
    assert "credential_or_secret_request" in reasons


def test_boundary_values_are_exclusive_thresholds():
    # Exactly at the block threshold should NOT block (thresholds are `>`, not `>=`).
    verdict, _ = _compose(
        jailbreak=0.75, injection=0.0, credential=0.0, escalation=0.0, severity=0.0
    )
    assert verdict == Verdict.FLAG
