"""Guards for the Pi image's starter project seeding.

Every deployment target must ship the canonical starter project from
``installer/seed/default/`` — never a fork. The Pi image used to commit its
own copy under the pi-gen stage's ``files/`` directory, which silently
drifted (it was still on a pre-``device_groups`` schema while every other
target shipped the current seed). Both build paths (the release workflow and
the local ``build.sh``) now stage the canonical seed into ``files/`` at build
time, exactly like ``update-helper.sh`` and ``openavc.service``, and the
staged copy is gitignored so a fork can't be committed again.

These are text-level guards (like test_installer_spec.py) because the image
itself only builds on Linux CI.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release-pi.yml"
BUILD_SH = REPO_ROOT / "installer" / "pi-image" / "build.sh"
STAGE_DIR = REPO_ROOT / "installer" / "pi-image" / "stage-openavc"
RUN_SH = STAGE_DIR / "01-install-openavc" / "00-run.sh"
CHROOT_SH = STAGE_DIR / "02-configure" / "00-run-chroot.sh"
STREAMDECK_RULES = STAGE_DIR / "01-install-openavc" / "files" / "99-streamdeck.rules"
GITIGNORE = REPO_ROOT / ".gitignore"

CANONICAL_SEED = "installer/seed/default/project.avc"
STAGED_SEED = "installer/pi-image/stage-openavc/01-install-openavc/files/project.avc"


def test_release_workflow_stages_canonical_seed():
    """The CI pipeline must copy the canonical seed into the stage files/."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert CANONICAL_SEED in text, (
        f"release-pi.yml does not stage {CANONICAL_SEED} — the image would "
        "build without the canonical starter project"
    )
    assert STAGED_SEED in text, (
        f"release-pi.yml does not stage the seed to {STAGED_SEED}"
    )


def test_local_build_stages_canonical_seed():
    """build.sh mirrors the CI staging for local (Linux) image builds."""
    text = BUILD_SH.read_text(encoding="utf-8")
    assert CANONICAL_SEED in text, (
        f"build.sh does not stage {CANONICAL_SEED} into the stage files dir"
    )


def test_no_forked_seed_is_tracked():
    """No project.avc may be committed anywhere under installer/pi-image/.

    A tracked copy is a fork of the canonical seed by definition — it can
    only drift. The staged copy is created at build time and gitignored.
    """
    if shutil.which("git") is None:
        pytest.skip("git not installed")
    proc = subprocess.run(
        ["git", "ls-files", "installer/pi-image"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=30,
    )
    if proc.returncode != 0:
        pytest.skip("not a git checkout")
    tracked = [line for line in proc.stdout.splitlines() if line.endswith("project.avc")]
    assert not tracked, f"forked seed project committed under installer/pi-image: {tracked}"


def test_staged_seed_is_gitignored():
    text = GITIGNORE.read_text(encoding="utf-8")
    assert STAGED_SEED in text, (
        ".gitignore must cover the build-time staged seed so a fork can't "
        "be committed again"
    )


def test_image_installs_staged_seed_unconditionally():
    """00-run.sh must install the staged seed, and must not hide a missing
    one behind an existence guard — a build without the seed should fail
    loudly, not produce an image with no starter project."""
    text = RUN_SH.read_text(encoding="utf-8")
    assert "project.avc" in text, "00-run.sh no longer installs the seed project"
    assert 'if [ -f "$FILES_DIR/project.avc" ]' not in text, (
        "00-run.sh hides a missing staged seed behind an existence guard"
    )


def test_chroot_has_no_dead_seed_fallback():
    """The server tarball excludes installer/, so /opt/openavc/installer/...
    never exists in the image — a chroot-side fallback that copies from it is
    dead code that only masks staging failures."""
    text = CHROOT_SH.read_text(encoding="utf-8")
    assert "/opt/openavc/installer" not in text, (
        "00-run-chroot.sh references /opt/openavc/installer, which is never "
        "present in the image rootfs (the server tarball excludes installer/)"
    )


def test_build_verification_checks_seed():
    """The image build's hard-check block must verify the seeded project
    actually landed, so a staging regression aborts the build."""
    text = CHROOT_SH.read_text(encoding="utf-8")
    assert '! -s "$DATA_DIR/projects/default/project.avc"' in text, (
        "00-run-chroot.sh build verification does not check the seed project"
    )


def test_streamdeck_rule_is_not_world_writable():
    """The Stream Deck udev rule must not grant world read/write (MODE=0666).

    The server runs as the unprivileged 'openavc' system-service user, so a
    world-writable device node is unnecessary and lets any local user or a
    compromised process issue raw USB HID traffic. Least privilege: a group
    the service user belongs to, with 0660.
    """
    text = STREAMDECK_RULES.read_text(encoding="utf-8")
    assert '0666' not in text, (
        "99-streamdeck.rules is world-writable (MODE=0666) — scope it to a "
        "group with 0660 instead"
    )
    assert 'MODE="0660"' in text, (
        "99-streamdeck.rules should set MODE=0660 (group-writable only)"
    )
    assert 'GROUP="plugdev"' in text, (
        "99-streamdeck.rules should be owned by the plugdev group"
    )


def test_streamdeck_group_membership_is_granted():
    """The openavc service user must be in the group the udev rule grants, or
    the 0660 rule would lock the server out of the Stream Deck entirely."""
    text = CHROOT_SH.read_text(encoding="utf-8")
    assert "plugdev" in text, (
        "00-run-chroot.sh does not add the openavc user to plugdev, so the "
        "group-scoped Stream Deck rule would deny the service access"
    )
