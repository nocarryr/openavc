"""Tests for Engine project-load recovery paths."""

import json

from server.core.engine import Engine


def test_recovery_creates_parent_directory(tmp_path):
    """Regression for A6: when OPENAVC_PROJECT points at a path whose
    parent directory does not yet exist (fresh dev checkout, custom
    project path with no projects/ dir), `_load_project_safe` must
    mkdir the parent before save_project tries to write a tempfile and
    .avc.bak sibling there. Otherwise startup crashes with
    FileNotFoundError and the splash sticks on 'Startup failed'.
    """
    missing_parent = tmp_path / "missing" / "nested" / "tree"
    project_path = missing_parent / "project.avc"
    assert not missing_parent.exists(), "precondition: parent must not exist"

    eng = Engine(str(project_path))
    project = eng._load_project_safe()

    assert project is not None
    assert project.project.id == "recovery"
    assert missing_parent.is_dir(), "recovery should have created the parent dir"
    assert project_path.exists(), "recovery should have written the empty project"

    # The written project should round-trip through the loader.
    saved = json.loads(project_path.read_text(encoding="utf-8"))
    assert saved["project"]["id"] == "recovery"


def test_recovery_existing_parent_dir_still_works(tmp_path):
    """Sanity check: the mkdir call must be idempotent for the common
    case where the parent dir already exists.
    """
    project_path = tmp_path / "project.avc"  # tmp_path already exists
    eng = Engine(str(project_path))
    project = eng._load_project_safe()

    assert project is not None
    assert project.project.id == "recovery"
    assert project_path.exists()
