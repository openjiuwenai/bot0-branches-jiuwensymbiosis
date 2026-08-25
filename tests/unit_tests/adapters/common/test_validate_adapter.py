# coding: utf-8
# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.

"""Tests for scripts/validate_adapter.py — the A-13 capability-tag check.

Guards against the silent-failure regression where the check read a different
attribute name (``_tool_meta``) than the decorator sets (``__robot_tool__``),
which made the check always return an empty list.
"""

from __future__ import annotations

from types import SimpleNamespace

import scripts.validate_adapter as va
from jiuwensymbiosis.api.base import BaseRobotApi
from jiuwensymbiosis.api.decorators import robot_tool
from jiuwensymbiosis.api.mixins import MotionMixin
from jiuwensymbiosis.env.base import KNOWN_CAPABILITIES as BASE_KNOWN_CAPABILITIES


class _ApiWithBadCapability(MotionMixin, BaseRobotApi):
    capability = "motion.cartesian"

    @robot_tool(desc="a tool that claims a capability the env does not have", capability="myvendor.special")
    def do_special(self) -> None:
        return None


class _ApiWithAlignedCapability(MotionMixin, BaseRobotApi):
    capability = "motion.cartesian"

    @robot_tool(desc="a tool whose capability matches the env", capability="motion.cartesian")
    def do_aligned(self) -> None:
        return None


class TestCheckToolTags:
    def test_detects_capability_not_in_env(self):
        # env declares only motion.cartesian; the tool claims myvendor.special.
        env_caps = {"motion.cartesian"}
        warnings = va._check_tool_tags(_ApiWithBadCapability, env_caps)
        assert any("do_special" in w and "myvendor.special" in w for w in warnings)

    def test_clean_when_capability_aligned(self):
        env_caps = {"motion.cartesian"}
        warnings = va._check_tool_tags(_ApiWithAlignedCapability, env_caps)
        assert warnings == []

    def test_tools_without_explicit_capability_are_not_flagged(self):
        # MotionMixin.home has no explicit capability; it must not warn even
        # when env_caps is empty (its owning capability comes from the mixin).
        env_caps = set()
        warnings = va._check_tool_tags(_ApiWithAlignedCapability, env_caps)
        # do_aligned IS flagged (its explicit motion.cartesian not in empty env_caps),
        # but inherited `home` must not appear in any warning.
        assert all("home" not in w for w in warnings)


class TestKnownCapabilitiesSingleSource:
    def test_validate_adapter_known_capabilities_matches_base(self):
        assert va.KNOWN_CAPABILITIES == BASE_KNOWN_CAPABILITIES


class TestCalibrationIntegrationCheck:
    _MODULE = "jiuwensymbiosis.adapters.new_arm"
    _WRAPPER = "jiuwensymbiosis.calibration.adapters.new_arm"

    def test_missing_wrapper_is_optional_info(self, monkeypatch):
        def _missing(name: str):
            raise ModuleNotFoundError(f"No module named {name!r}", name=name)

        monkeypatch.setattr(va.importlib, "import_module", _missing)

        results = va._check_calibration_integration(self._MODULE)

        assert len(results) == 1
        assert results[0][0:2] == ("C-16", va._SEVERITY_INFO)

    def test_wrapper_dependency_failure_is_error(self, monkeypatch):
        def _dependency_missing(_name: str):
            raise ModuleNotFoundError("optional vendor SDK", name="optional_vendor_sdk")

        monkeypatch.setattr(va.importlib, "import_module", _dependency_missing)

        results = va._check_calibration_integration(self._MODULE)

        assert results[0][0:2] == ("C-16", va._SEVERITY_ERROR)
        assert "optional_vendor_sdk" in results[0][2]

    def test_wrapper_runtime_failure_is_error(self, monkeypatch):
        def _broken(_name: str):
            raise RuntimeError("spec construction failed")

        monkeypatch.setattr(va.importlib, "import_module", _broken)

        results = va._check_calibration_integration(self._MODULE)

        assert results[0][0:2] == ("C-16", va._SEVERITY_ERROR)
        assert "spec construction failed" in results[0][2]

    def test_malformed_spec_is_error(self, monkeypatch):
        monkeypatch.setattr(
            va.importlib,
            "import_module",
            lambda _name: SimpleNamespace(CALIBRATION_ADAPTER_SPEC=object()),
        )

        results = va._check_calibration_integration(self._MODULE)

        assert results[0][0:2] == ("C-16", va._SEVERITY_ERROR)
