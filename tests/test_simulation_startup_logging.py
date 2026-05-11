"""Tests for simulator subprocess startup log forwarding (A34).

The readiness loop in SimulationManager reads stderr chunks while waiting
for "Uvicorn running" to appear. Before A34, those chunks were collected
into a local list and then discarded the moment readiness was reached —
so any diagnostic uvicorn or simulator code emitted during startup was
invisible to the operator. Subsequent drain tasks pick up everything
AFTER the loop exits, but startup-window output is gone.
"""

import asyncio
import logging

import pytest

from server.core.simulation import SimulationManager


class _FakeStream:
    """Async stream that returns a fixed sequence of byte chunks."""

    def __init__(self, chunks: list[bytes]):
        self._chunks = list(chunks)

    async def read(self, n: int = -1) -> bytes:
        if self._chunks:
            return self._chunks.pop(0)
        # Drain: nothing more to read, simulate a small wait.
        await asyncio.sleep(0.01)
        return b""


class _FakeProcess:
    """Stand-in for asyncio.subprocess.Process — enough for the readiness loop."""

    def __init__(self, stderr_chunks: list[bytes], returncode: int | None = None):
        self.stderr = _FakeStream(stderr_chunks)
        self.stdout = _FakeStream([])
        self.returncode = returncode


def _manager() -> SimulationManager:
    # _await_simulator_ready never touches self.engine, so any sentinel is
    # safe. Mock it to avoid pulling in the rest of the stack.
    return SimulationManager(engine=object())


@pytest.mark.asyncio
async def test_startup_stderr_lines_are_logged(caplog):
    """Regression for A34: each stderr line emitted during the readiness
    window must be forwarded to the openavc logger, not discarded.
    """
    proc = _FakeProcess(
        stderr_chunks=[
            b"INFO:     Started server process\n",
            b"INFO:     Waiting for application startup\n",
            b"INFO:     Uvicorn running on http://127.0.0.1:19500\n",
        ],
    )
    mgr = _manager()

    with caplog.at_level(logging.INFO, logger="server.core.simulation"):
        await mgr._await_simulator_ready(proc)

    log_messages = [r.getMessage() for r in caplog.records]
    assert any("Started server process" in m for m in log_messages)
    assert any("Waiting for application startup" in m for m in log_messages)
    assert any("Uvicorn running" in m for m in log_messages)


@pytest.mark.asyncio
async def test_startup_ignores_blank_lines(caplog):
    """Blank lines from the subprocess shouldn't clutter the log."""
    proc = _FakeProcess(
        stderr_chunks=[b"\n\nINFO: actual content\n\nUvicorn running\n"],
    )
    mgr = _manager()

    with caplog.at_level(logging.INFO, logger="server.core.simulation"):
        await mgr._await_simulator_ready(proc)

    log_messages = [r.getMessage() for r in caplog.records if "simulator.stderr" in r.getMessage()]
    # Only the two non-blank lines forwarded.
    assert sum(1 for m in log_messages if m.strip()) == 2


@pytest.mark.asyncio
async def test_process_exit_during_startup_raises_with_output():
    """If the subprocess exits during the readiness window, the error
    message must include captured stderr — the operator needs to know
    what went wrong.
    """
    proc = _FakeProcess(
        stderr_chunks=[b"FATAL: bind: address already in use\n"],
        returncode=1,
    )
    mgr = _manager()

    with pytest.raises(RuntimeError, match="exited with code 1"):
        await mgr._await_simulator_ready(proc)


@pytest.mark.asyncio
async def test_no_ready_marker_warns_but_does_not_raise(caplog):
    """The simulator might be silently up if uvicorn's banner changes
    wording — log a warning but don't raise.
    """
    proc = _FakeProcess(stderr_chunks=[])  # nothing emitted
    mgr = _manager()

    with caplog.at_level(logging.WARNING, logger="server.core.simulation"):
        await mgr._await_simulator_ready(proc)

    assert any("readiness not confirmed" in r.getMessage() for r in caplog.records)
