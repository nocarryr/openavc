"""Regression tests for PUT /api/project optimistic concurrency.

The revision compare and the save+reload must be atomic. Checked at the
route (outside the engine's reload lock), two concurrent PUTs carrying the
same If-Match can both pass the compare — both save, and the first
writer's edit is silently overwritten despite the 409 contract that exists
to prevent exactly that.
"""

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from server.api import rest, ws
from server.core.engine import Engine
from server.main import app

BODY = {"project": {"id": "t", "name": "Test"}}


@pytest.fixture
def engine(tmp_path):
    eng = Engine(str(tmp_path / "t.avc"))
    rest.set_engine(eng)
    ws.set_engine(eng)
    yield eng
    rest.set_engine(None)
    ws.set_engine(None)


def _client() -> AsyncClient:
    transport = ASGITransport(app=app, client=("127.0.0.1", 50000))
    return AsyncClient(transport=transport, base_url="http://testserver")


def _stub_persistence(engine, monkeypatch, save_delay: float = 0.0):
    """Replace disk save + full reload with counters; keep revision semantics."""
    saves = []

    async def fake_save(path, project):
        saves.append(project)
        if save_delay:
            # Hold the save window open so concurrent PUTs genuinely overlap.
            await asyncio.sleep(save_delay)

    monkeypatch.setattr("server.core.engine.save_project_async", fake_save)
    monkeypatch.setattr(
        "server.api.routes.project.save_project_async", fake_save, raising=False
    )

    async def fake_reload_inner():
        # Mirror the real _reload_project_inner: reload bumps the revision.
        engine._project_revision += 1

    monkeypatch.setattr(engine, "_reload_project_inner", fake_reload_inner)
    return saves


@pytest.mark.asyncio
async def test_put_project_stale_if_match_rejected(engine, monkeypatch):
    saves = _stub_persistence(engine, monkeypatch)
    engine._project_revision = 5

    async with _client() as c:
        resp = await c.put("/api/project", json=BODY, headers={"If-Match": '"3"'})

    assert resp.status_code == 409
    assert saves == []
    assert engine._project_revision == 5


@pytest.mark.asyncio
async def test_put_project_match_saves_and_returns_new_etag(engine, monkeypatch):
    saves = _stub_persistence(engine, monkeypatch)
    engine._project_revision = 5

    async with _client() as c:
        resp = await c.put("/api/project", json=BODY, headers={"If-Match": '"5"'})

    assert resp.status_code == 200
    assert len(saves) == 1
    assert resp.headers["etag"] == '"6"'


@pytest.mark.asyncio
async def test_put_project_concurrent_same_revision_one_loses(engine, monkeypatch):
    saves = _stub_persistence(engine, monkeypatch, save_delay=0.05)
    engine._project_revision = 0

    async with _client() as c:
        r1, r2 = await asyncio.gather(
            c.put("/api/project", json=BODY, headers={"If-Match": '"0"'}),
            c.put("/api/project", json=BODY, headers={"If-Match": '"0"'}),
        )

    # One writer wins, the other must get 409 — not a silent overwrite.
    assert sorted([r1.status_code, r2.status_code]) == [200, 409]
    assert len(saves) == 1
    assert engine._project_revision == 1
