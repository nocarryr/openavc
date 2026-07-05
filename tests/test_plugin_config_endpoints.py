"""Plugin REST endpoint hardening: config validation, restart outcome,
context-action guards.

The REST config path persisted whatever JSON arrived (the cloud AI path
validated against CONFIG_SCHEMA — the IDE's own path could break a plugin
the AI path would have protected), the config-update restart discarded the
start result (a bad config silently left the plugin stopped with
enabled=true), and the context-action endpoint emitted events for any
plugin id / action name / payload shape the client sent.

Uses an invented plugin (acme_widget) throughout.
"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import server.core.plugin_loader as pl
from server.api.plugins import emit_context_action, update_plugin_config
from server.core.event_bus import EventBus
from server.core.plugin_config import missing_required_fields, validate_plugin_config
from server.core.plugin_loader import PluginLoader
from server.core.project_loader import PluginConfig, ProjectConfig, ProjectMeta
from server.core.state_store import StateStore


class _AcmeWidgetPlugin:
    PLUGIN_INFO = {"id": "acme_widget", "name": "Acme Widget"}
    CONFIG_SCHEMA = {
        "host": {"type": "string", "required": True},
        "port": {"type": "integer"},
        "advanced": {
            "type": "group",
            "fields": {"retries": {"type": "integer"}},
        },
    }


class _FakeRequest:
    def __init__(self, body):
        self._body = body

    async def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


class _RecordingEvents:
    def __init__(self):
        self.emitted = []

    async def emit(self, event, payload):
        self.emitted.append((event, payload))


def _project():
    return ProjectConfig(
        project=ProjectMeta(id="t", name="Test"),
        devices=[],
        connections={},
        plugins={"acme_widget": PluginConfig(enabled=True, config={"host": "10.0.0.9"})},
    )


def _engine(monkeypatch, *, restart_outcome="restarted"):
    outcomes = []

    async def _restart(plugin_id, config):
        outcomes.append((plugin_id, config))
        return restart_outcome

    engine = SimpleNamespace(
        project=_project(),
        project_path="unused.avc",
        plugin_loader=SimpleNamespace(restart_or_apply=_restart),
        events=_RecordingEvents(),
        bump_project_revision=lambda: None,
    )
    monkeypatch.setattr("server.api.plugins._engine", engine)

    async def _no_save(*a, **k):
        return None

    monkeypatch.setattr("server.api.plugins.save_project_async", _no_save)
    return engine


# ── validate_plugin_config (shared core module) ──


def test_validator_flags_wrong_types_but_tolerates_missing_required():
    schema = _AcmeWidgetPlugin.CONFIG_SCHEMA
    # Missing required fields are a warning concern (the form saves
    # incrementally during setup), not a type error.
    assert validate_plugin_config({}, schema) is None
    assert missing_required_fields({}, schema) == ["host"]
    assert missing_required_fields({"host": "x"}, schema) == []
    err = validate_plugin_config({"host": "x", "port": "not-an-int"}, schema)
    assert err is not None and "port" in err
    # Group fields recurse
    err = validate_plugin_config(
        {"host": "x", "advanced": {"retries": "three"}}, schema
    )
    assert err is not None and "retries" in err
    # Valid config passes
    assert validate_plugin_config({"host": "x", "port": 80}, schema) is None


def test_missing_required_reports_group_fields_dotted():
    schema = {
        "creds": {
            "type": "group",
            "fields": {"api_key": {"type": "string", "required": True}},
        },
    }
    assert missing_required_fields({}, schema) == ["creds.api_key"]
    assert missing_required_fields({"creds": {"api_key": "k"}}, schema) == []


def test_cloud_path_uses_shared_validator():
    """The cloud AI path must use the identical validator (parity pin)."""
    import inspect

    from server.cloud.tools import plugin_tools

    src = inspect.getsource(plugin_tools)
    assert "server.core.plugin_config" in src
    assert "validate_config_for_plugin" in src
    assert "missing_required_for_plugin" in src


# ── PUT /plugins/{id}/config ──


@pytest.mark.asyncio
async def test_update_config_rejects_schema_violations(monkeypatch):
    engine = _engine(monkeypatch)
    monkeypatch.setitem(pl._PLUGIN_CLASS_REGISTRY, "acme_widget", _AcmeWidgetPlugin)

    with pytest.raises(HTTPException) as exc:
        await update_plugin_config("acme_widget", _FakeRequest({"port": "eighty"}))
    assert exc.value.status_code == 400
    assert "validation failed" in exc.value.detail
    # Nothing persisted
    assert engine.project.plugins["acme_widget"].config == {"host": "10.0.0.9"}


@pytest.mark.asyncio
async def test_update_config_rejects_non_object_body(monkeypatch):
    _engine(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await update_plugin_config("acme_widget", _FakeRequest(["not", "a", "dict"]))
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_update_config_accepts_valid_and_reports_outcome(monkeypatch):
    engine = _engine(monkeypatch, restart_outcome="hot_applied")
    monkeypatch.setitem(pl._PLUGIN_CLASS_REGISTRY, "acme_widget", _AcmeWidgetPlugin)

    result = await update_plugin_config(
        "acme_widget", _FakeRequest({"host": "10.0.0.10", "port": 81})
    )
    assert result["status"] == "updated"
    assert result["applied"] == "hot_applied"
    assert "warning" not in result
    assert engine.project.plugins["acme_widget"].config == {"host": "10.0.0.10", "port": 81}


@pytest.mark.asyncio
async def test_update_config_partial_save_persists_with_warning(monkeypatch):
    """First-time setup saves the config form incrementally — a save that
    still lacks a required field must persist (with a warning naming the
    field), not 400. Rejecting it made the IDE's autosave toast an error
    after every keystroke until the whole form was filled."""
    engine = _engine(monkeypatch, restart_outcome="start_failed")
    monkeypatch.setitem(pl._PLUGIN_CLASS_REGISTRY, "acme_widget", _AcmeWidgetPlugin)

    result = await update_plugin_config("acme_widget", _FakeRequest({"port": 81}))
    assert result["status"] == "updated"
    assert "host" in result["warning"]
    assert "can't run" in result["warning"]
    assert engine.project.plugins["acme_widget"].config == {"port": 81}


@pytest.mark.asyncio
async def test_update_config_surfaces_restart_failure(monkeypatch):
    """A config that breaks the plugin must not report a clean update —
    the plugin is left stopped and the user needs to know."""
    _engine(monkeypatch, restart_outcome="start_failed")
    monkeypatch.setitem(pl._PLUGIN_CLASS_REGISTRY, "acme_widget", _AcmeWidgetPlugin)

    result = await update_plugin_config("acme_widget", _FakeRequest({"host": "x"}))
    assert result["applied"] == "start_failed"
    assert "failed to restart" in result["warning"]


@pytest.mark.asyncio
async def test_update_config_without_installed_plugin_still_saves(monkeypatch):
    """Config for a missing (not-installed) plugin persists unvalidated so
    it survives until the plugin is installed."""
    engine = _engine(monkeypatch, restart_outcome="not_running")
    pl._PLUGIN_CLASS_REGISTRY.pop("acme_widget", None)

    result = await update_plugin_config("acme_widget", _FakeRequest({"anything": True}))
    assert result["status"] == "updated"
    assert engine.project.plugins["acme_widget"].config == {"anything": True}


# ── restart_or_apply outcome (loader) ──


@pytest.mark.asyncio
async def test_restart_or_apply_reports_start_failure(monkeypatch):
    loader = PluginLoader(StateStore(), EventBus(), None, None)
    monkeypatch.setattr(loader, "is_running", lambda pid: True)

    async def _no_hot(pid, cfg):
        return False

    async def _stop(pid):
        return None

    async def _start_fails(pid, config=None):
        return False

    monkeypatch.setattr(loader, "apply_config", _no_hot)
    monkeypatch.setattr(loader, "_stop_plugin_locked", _stop)
    monkeypatch.setattr(loader, "_start_plugin_locked", _start_fails)

    assert await loader.restart_or_apply("acme_widget", {"x": 1}) == "start_failed"


# ── POST /plugins/{id}/context-action/{action} ──


@pytest.mark.asyncio
async def test_context_action_unknown_plugin_404s(monkeypatch):
    engine = _engine(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await emit_context_action("not_in_project", "route", _FakeRequest({}))
    assert exc.value.status_code == 404
    assert engine.events.emitted == []


@pytest.mark.asyncio
async def test_context_action_invalid_action_id_400s(monkeypatch):
    engine = _engine(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await emit_context_action("acme_widget", "x.y/z", _FakeRequest({}))
    assert exc.value.status_code == 400
    assert engine.events.emitted == []


@pytest.mark.asyncio
async def test_context_action_non_dict_payload_400s(monkeypatch):
    engine = _engine(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await emit_context_action("acme_widget", "route", _FakeRequest([1, 2]))
    assert exc.value.status_code == 400
    assert engine.events.emitted == []


@pytest.mark.asyncio
async def test_context_action_emits_dict_payload(monkeypatch):
    engine = _engine(monkeypatch)
    result = await emit_context_action(
        "acme_widget", "route", _FakeRequest({"row": "a", "col": "b"})
    )
    assert result["status"] == "emitted"
    assert engine.events.emitted == [
        ("plugin.acme_widget.action.route", {"row": "a", "col": "b"})
    ]


@pytest.mark.asyncio
async def test_context_action_missing_body_emits_empty_dict(monkeypatch):
    engine = _engine(monkeypatch)
    await emit_context_action("acme_widget", "refresh", _FakeRequest(ValueError("no body")))
    assert engine.events.emitted == [("plugin.acme_widget.action.refresh", {})]
