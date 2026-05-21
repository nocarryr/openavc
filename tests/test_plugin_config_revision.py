"""Regression guard for the plugin enable/config clobber bug.

Server-side project saves that bypass the reload path (plugin enable/disable and
plugin-config saves such as the Video Streams editor) must bump the project
revision. Otherwise an open editor's cached ETag still matches the server, so its
next full-project ``PUT /api/project`` silently overwrites the change — which is
how enabling the Video Panel plugin (and picking a stream) kept getting wiped by
the UI Builder's autosave.
"""

import pytest

from server.core.engine import Engine
from server.core.project_loader import PluginConfig, ProjectConfig, ProjectMeta


def _engine(tmp_path, monkeypatch):
    # Don't touch disk; we only care about the in-memory revision counter.
    monkeypatch.setattr("server.core.engine.save_project", lambda *a, **k: None)
    engine = Engine(str(tmp_path / "t.avc"))
    engine.project = ProjectConfig(
        project=ProjectMeta(id="t", name="Test"),
        devices=[],
        connections={},
        plugins={"video_panel": PluginConfig(enabled=True, config={})},
    )
    return engine


def test_bump_project_revision_increments(tmp_path, monkeypatch):
    engine = _engine(tmp_path, monkeypatch)
    engine._project_revision = 3
    engine.bump_project_revision()
    assert engine._project_revision == 4


@pytest.mark.asyncio
async def test_save_plugin_config_persists_and_bumps_revision(tmp_path, monkeypatch):
    engine = _engine(tmp_path, monkeypatch)
    engine._project_revision = 5

    await engine._save_plugin_config(
        "video_panel", {"streams": [{"stream_id": "cam1"}]}
    )

    # Config persisted to the project...
    assert engine.project.plugins["video_panel"].config == {
        "streams": [{"stream_id": "cam1"}]
    }
    # ...and the revision advanced, so a stale editor PUT will 409 rather than
    # clobber this change.
    assert engine._project_revision == 6


@pytest.mark.asyncio
async def test_save_plugin_config_unknown_plugin_does_not_bump(tmp_path, monkeypatch):
    engine = _engine(tmp_path, monkeypatch)
    engine._project_revision = 9

    await engine._save_plugin_config("not_installed", {"x": 1})

    # No matching plugin entry -> nothing saved -> revision unchanged.
    assert engine._project_revision == 9
