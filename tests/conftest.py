"""Shared pytest fixtures for ha-garmin-dive."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from aresponses import ResponsesMockServer

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def load_fixture():
    """Return a callable that loads a JSON fixture by name (without extension)."""

    def _load(name: str) -> Any:
        path = FIXTURES_DIR / f"{name}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    return _load


# Enable HA test framework for tests that need a HomeAssistant instance.
pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Allow custom_components/garmin_dive to load in HA tests."""
    return


@pytest.fixture
async def aresponses(socket_enabled):
    """ResponsesMockServer with sockets permitted (overrides HA socket guard)."""
    loop = asyncio.get_running_loop()
    async with ResponsesMockServer(loop=loop) as server:
        yield server
