---
name: python-testing
description: Deep pytest guide for jiuwensymbiosis — fixtures, mocking, async tests, and the mock-hardware pattern.
---

# Python Testing

Comprehensive pytest patterns for jiuwensymbiosis. This skill extends
`.claude/rules/python/testing.md` and `.claude/rules/testing.md`.

## The Mock-Hardware Pattern (core convention)

jiuwensymbiosis's defining test convention: **unit tests never touch real
hardware**. The `tests/mocks/` package exports `MockApi`, `MockArmEnvWrapper`,
`MockPiperDriver`, `MockDualArm*`, `MockScene` (and `make_mock_seg_fn`); the
related `tests/helpers.py` provides `make_mock_session`, `FakeCtx`, and
`RecordingRailSink`. Use them instead of hand-rolled fakes.

`jiuwensymbiosis.env.mock.MockArmEnv` is the in-memory 4-DoF arm (capabilities:
`motion.cartesian`, `motion.servo`, `grasp.parallel`, `vision.camera`,
`vision.detection`). It does NOT take a `capabilities` argument — to test
capability gating, subclass `BaseRobotEnv` with the frozenset you want (see
`tests/unit_tests/tools/test_builder.py::TestEnvIntersectionGating`).

```python
from jiuwensymbiosis.env.mock import MockArmEnv
from jiuwensymbiosis.tools.builder import build_robot_tools
from tests.mocks.mock_api import MockApi

def test_motion_tools_emit_when_capable():
    env = MockArmEnv()  # declares motion.cartesian + grasp.parallel + vision.*
    api = MockApi(env)
    tools = {t.card.name for t in build_robot_tools(api, env=env)}
    assert "goto_xyzr" in tools
    assert "close_gripper" in tools
```

`build_mock_model()` (in `jiuwensymbiosis.agent.mock_model`, alongside
`MockModelClient`) replaces the LLM in `--mock` runs and in agent-level tests —
pass it as `RobotAgentConfig(model=build_mock_model())`.

## TDD Workflow

Write tests before implementation. Follow the red-green-refactor cycle:

1. **RED** — Write a failing test that describes the desired behavior
2. **GREEN** — Write the minimal implementation to make the test pass
3. **REFACTOR** — Improve code quality while keeping tests green

`SafetyRail` takes a *session* (not an env) plus keyword bounds, and rails
receive an openjiuwen callback context (`ctx`) — `tests/helpers.py:FakeCtx` is
the stand-in:

```python
import pytest
from jiuwensymbiosis.rails.safety import SafetyRail
from tests.helpers import FakeCtx, make_mock_session

class TestSafetyRail:
    @pytest.mark.asyncio
    async def test_rejects_z_below_floor(self):
        session = make_mock_session()
        rail = SafetyRail(session, z_floor_mm=50.0)
        ctx = FakeCtx(tool_name="goto_xyzr", tool_args={"x": 100, "y": 0, "z": 30, "r": 0})
        with pytest.raises(ValueError, match="below z_floor"):
            await rail.before_tool_call(ctx)

    @pytest.mark.asyncio
    async def test_accepts_z_above_floor(self):
        session = make_mock_session()
        rail = SafetyRail(session, z_floor_mm=50.0)
        ctx = FakeCtx(tool_name="goto_xyzr", tool_args={"x": 100, "y": 0, "z": 100, "r": 0})
        await rail.before_tool_call(ctx)  # does not raise
```

There is also a synchronous `rail.validate_motion(tool_name, tool_args)` for
pure policy checks without a ctx.

## Fixtures

### conftest.py Organization

Define fixtures in `tests/conftest.py` for project-wide fixtures, or in
`tests/unit_tests/<subsystem>/conftest.py` for subsystem-specific fixtures.

```python
# tests/unit_tests/<subsystem>/conftest.py
import pytest
from jiuwensymbiosis.env.mock import MockArmEnv
from tests.helpers import make_mock_session
from tests.mocks.mock_api import MockApi

@pytest.fixture
def mock_env():
    return MockArmEnv()

@pytest.fixture
def mock_api(mock_env):
    return MockApi(mock_env)

@pytest.fixture
def mock_session():
    return make_mock_session()
```

### Factory Fixtures

Useful when tests need slightly different configurations:

```python
@pytest.fixture
def make_motion_only_env():
    """Factory: an env whose capabilities are exactly what the test wants."""
    from jiuwensymbiosis.env.base import BaseRobotEnv, RobotObservation

    def _make(capabilities):
        class Env(BaseRobotEnv):
            capabilities = frozenset(capabilities)
            name = "custom"

            def connect(self): pass
            def disconnect(self): pass
            def home(self): pass
            def get_observation(self):
                return RobotObservation()

        return Env()

    return _make

def test_gripper_tool_only_when_capable(make_motion_only_env):
    from jiuwensymbiosis.tools.builder import build_robot_tools
    env = make_motion_only_env({"motion.cartesian", "grasp.suction"})
    api = MockApi(env)
    tools = {t.card.name for t in build_robot_tools(api, env=env)}
    assert "activate_suction" not in tools  # MockApi implements no suction action
    assert "close_gripper" not in tools     # grasp.parallel gated out
```

### autouse Fixtures

Use sparingly — only for global setup that must happen for every test.

## Pytest Marks

### Selective Execution

```bash
# Run only fast unit tests (CI default)
pytest -m unit

# Run integration tests on the bench
pytest -m integration

# Run everything
pytest

# Filter by name
pytest -k "test_capabilities"
```

## Mocking

### pytest-mock `mocker` fixture (preferred)

Patch the symbol where it is *used*, by its real module path
(`rails/safety.py`, not a hypothetical `rails/safety_rail.py`):

```python
def test_rail_logs_rejection(mocker, mock_session):
    from jiuwensymbiosis.rails import safety as safety_mod
    log_spy = mocker.patch.object(safety_mod, "get_logger")
    rail = SafetyRail(mock_session, z_floor_mm=50.0)
    # ... exercise a rejection path
    log_spy.return_value.warning.assert_called_once()
```

### Patching module-level symbols

```python
def test_uses_detector_sidecar(mocker):
    mock_init = mocker.patch(
        "jiuwensymbiosis.perception.detector_client.init_detector"
    )
    # ... exercise the path that calls init_detector
    mock_init.assert_called_once()
```

### AsyncMock for async methods

Sidecars are stored on the session as `RobotSession.sidecar_starters` (a list
of zero-arg callables), started in `connect()`:

```python
def test_session_starts_sidecar(mocker, mock_session):
    starter = mocker.Mock()
    mock_session.sidecar_starters.append(starter)
    mock_session.connect()
    starter.assert_called_once()
```

## Async Testing

`pytest-asyncio` is configured with `asyncio_mode = "auto"` in
`pyproject.toml` — async test functions need no `@pytest.mark.asyncio`
decorator (existing tests may still carry it explicitly; both work):

```python
async def test_agent_invoke_with_mock_model(mock_session):
    from jiuwensymbiosis.agent import build_robot_agent
    from jiuwensymbiosis.agent.config import RobotAgentConfig
    from jiuwensymbiosis.agent.mock_model import build_mock_model

    config = RobotAgentConfig(model=build_mock_model())
    agent = build_robot_agent(mock_session, config=config)
    result = await agent.invoke("pick up the box")
    assert result is not None
```

## Test Organization

Mirror the source path in test paths:

| Source | Test |
|--------|------|
| `jiuwensymbiosis/tools/builder.py` | `tests/unit_tests/tools/test_builder.py` |
| `jiuwensymbiosis/rails/safety.py` | `tests/unit_tests/rails/test_safety.py` |
| `jiuwensymbiosis/api/defaults.py` | `tests/unit_tests/api/test_defaults.py` |
| `jiuwensymbiosis/adapters/piper/api.py` | `tests/unit_tests/adapters/piper/test_api.py` |
| `jiuwensymbiosis/agent/trace.py` | `tests/unit_tests/rails/test_trace.py` |

## Adapter Smoke Tests

Two scripts complement unit tests when working on adapters:

```bash
# Static: the adapter package exposes the expected files + symbols
python scripts/validate_adapter.py --module jiuwensymbiosis.adapters.piper

# Runtime: every @implements action is callable + JSON-serializable, on a stub driver
python scripts/smoke_test_adapter.py --module jiuwensymbiosis.adapters.piper
```

Run both before claiming an adapter change is done.

## pyproject.toml Configuration

Already in place:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "unit: no hardware or GPU required",
    "integration: requires real hardware, GPU, or external services",
]
asyncio_mode = "auto"
filterwarnings = [
    "ignore::DeprecationWarning:pymilvus",
    "ignore::DeprecationWarning:openjiuwen",
    "ignore::pydantic.warnings.PydanticDeprecatedSince20",
]
```

> No coverage gate is configured yet. If you add one, target 80% for
> `jiuwensymbiosis/` core (skip `adapters/` vendor-specific code from the
> gate — it's hard to cover without hardware).
