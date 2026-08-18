# coding: utf-8
# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.

"""layout:拖入 YAML 配置的判定、应用与「存为可选配置」。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from jiuwensymbiosis.gui import registry
from jiuwensymbiosis.gui.app_state import AppState
from jiuwensymbiosis.gui.layout import Layout

_BASE_YAML = "env:\n  cfg:\n    low_level:\n      port: /dev/base\n"
_DROPPED_YAML = "env:\n  cfg:\n    low_level:\n      port: /dev/dropped\n"


@pytest.fixture
def layout(tmp_path, monkeypatch):
    """把 ``configs/`` 引到临时目录后装配整页,免得用例写进仓库配置。"""
    monkeypatch.setattr(registry, "configs_dir", lambda: tmp_path)
    body_key = registry.list_bodies()[0].key
    body_dir = registry.get_body(body_key).config_path().parent
    body_dir.mkdir(parents=True, exist_ok=True)
    registry.get_body(body_key).config_path().write_text(_BASE_YAML, encoding="utf-8")
    return Layout(AppState())


def _drop(layout: Layout, name: str, text: str) -> None:
    layout._on_yaml_dropped(SimpleNamespace(args=[{"name": name, "text": text}]))


def test_drop_of_body_config_opens_dialog_defaulting_to_apply_only(layout):
    _drop(layout, "arm.local.yaml", _DROPPED_YAML)
    assert layout._drop_dialog.value is True
    assert layout._drop_name.text == "arm.local.yaml"
    assert layout._drop_choice.value == "apply"


def test_drop_of_non_body_yaml_is_rejected(layout):
    _drop(layout, "tasks.yaml", "tasks: []\n")
    assert layout._drop_dialog.value is False


def test_apply_only_updates_config_without_writing_file(layout):
    _drop(layout, "arm.local.yaml", _DROPPED_YAML)
    layout._confirm_drop()

    state = layout._state
    assert state.current_config().get("env.cfg.low_level.port") == "/dev/dropped"
    assert not registry.body_config_path(state.current_body, "arm.local").exists()


def test_saving_dropped_config_lands_in_body_dir_and_dropdown(layout):
    _drop(layout, "arm.local.yaml", _DROPPED_YAML)
    layout._drop_choice.set_value("save")
    layout._confirm_drop()

    state = layout._state
    saved = registry.body_config_path(state.current_body, "arm.local")
    assert saved.read_text(encoding="utf-8") == _DROPPED_YAML
    assert str(saved) in layout._home._config_file.options  # 主页下拉即刻多出这份配置
    assert state.current_config().get("env.cfg.low_level.port") == "/dev/dropped"
