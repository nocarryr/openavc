"""Tests for state-coverage validator message severity (A33).

The validator used to warn "X not in simulator initial_state — auto-gen
default may not be appropriate" with severity=warning. The supporting
comment claimed the simulator section "overrides initial_state
completely" — actually `yaml_auto._merge_simulator_section` merges
per-key, so the auto-gen default stays active for any variable not
explicitly listed. A misleading WARN made driver authors think they
had a problem to fix when they didn't.

The fix: surface the auto-gen default as `info` (not `warning`) and
update the text to read like a heads-up, not a complaint.
"""

from simulator.validate import ValidationResult, _check_state_coverage


def _result() -> ValidationResult:
    return ValidationResult(driver_path="x", driver_id="x", driver_type="yaml")


def test_state_coverage_emits_info_not_warning_for_auto_gen_fallback():
    """Variable in state_variables but not in simulator.initial_state
    should produce a single info-severity issue, no warning.
    """
    state_vars = {"power": {"type": "enum", "values": ["off", "on"], "label": "P"}}
    sim_initial: dict = {}
    sim = {"initial_state": {}}  # non-empty truthy sim section, missing the key

    r = _result()
    _check_state_coverage(r, state_vars, sim_initial, sim)

    assert not r.warnings, (
        f"_check_state_coverage emitted warnings for an auto-gen fallback: "
        f"{[i.message for i in r.warnings]}"
    )
    assert len(r.infos) == 1
    msg = r.infos[0].message
    assert "auto-gen default" in msg
    # The wording should hint at the fix, not just describe the gap.
    assert "override" in msg.lower() or "initial_state" in msg


def test_state_coverage_passes_silently_when_all_vars_covered():
    """No coverage gap = no issues of any severity."""
    state_vars = {"power": {"type": "enum", "values": ["off", "on"]}}
    sim_initial = {"power": "off"}
    sim = {"initial_state": sim_initial}

    r = _result()
    _check_state_coverage(r, state_vars, sim_initial, sim)

    assert not r.errors
    assert not r.warnings
    assert not r.infos
    assert r.passed


def test_info_issues_do_not_make_result_fail():
    """`passed` is errors-only — info messages are not failures."""
    r = _result()
    r.info("state_coverage", "auto-gen default heads-up")
    assert r.passed
    assert not r.errors
    assert not r.warnings
    assert len(r.infos) == 1
