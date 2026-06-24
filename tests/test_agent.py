"""Agent 模块测试 (配置读写 + 结构探查 fallback 模式)."""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

from yolo_forge_agent.config import AppConfig, LLMConfig, get_config, save_config
from yolo_forge_agent.base import BaseAgent, AgentResult, AgentStatus
from yolo_forge_agent.structure_agent import StructureAgent
from yolo_forge_agent.report_agent import ReportAgent


# ─────────────────────────────────────────────────────────────
#  配置
# ─────────────────────────────────────────────────────────────
def test_app_config_defaults():
    cfg = AppConfig()
    assert cfg.llm.api_key == ""
    assert cfg.llm.base_url == "https://api.openai.com/v1"
    assert cfg.llm.model == "gpt-4o-mini"
    assert cfg.theme == "dark_ide"
    assert not cfg.is_llm_configured()


def test_app_config_is_configured():
    cfg = AppConfig(llm=LLMConfig(api_key="sk-test", base_url="http://x", model="gpt-4o"))
    assert cfg.is_llm_configured()


def test_app_config_yaml_roundtrip(tmp_path):
    cfg = AppConfig(
        llm=LLMConfig(api_key="sk-test", base_url="http://localhost:8080", model="qwen-plus"),
        default_dataset_dir="/data",
        default_output_dir="/out",
    )
    path = tmp_path / "config.yaml"
    cfg.save(path)

    loaded = AppConfig.load(path)
    assert loaded.llm.api_key == "sk-test"
    assert loaded.llm.base_url == "http://localhost:8080"
    assert loaded.llm.model == "qwen-plus"
    assert loaded.default_dataset_dir == "/data"


def test_app_config_load_missing_file(tmp_path):
    """加载不存在的文件返回默认值."""
    cfg = AppConfig.load(tmp_path / "nonexistent.yaml")
    assert cfg.llm.api_key == ""
    assert not cfg.is_llm_configured()


# ─────────────────────────────────────────────────────────────
#  Structure Agent (fallback 模式, 不调真 LLM)
# ─────────────────────────────────────────────────────────────
def _make_mini_dataset(root: Path) -> None:
    """构造迷你数据集."""
    # face 文件夹 (id=0)
    face = root / "face"
    (face / "images").mkdir(parents=True)
    (face / "labels").mkdir()
    for i in range(2):
        arr = np.full((50, 50, 3), 128, dtype=np.uint8)
        Image.fromarray(arr).save(face / "images" / f"f_{i}.jpg")
        with open(face / "labels" / f"f_{i}.txt", "w") as fp:
            fp.write(f"0 0.5 0.5 0.2 0.2\n")

    # bg 文件夹 (无标签)
    bg = root / "bg"
    (bg / "images").mkdir(parents=True)
    for i in range(2):
        arr = np.full((50, 50, 3), 200, dtype=np.uint8)
        Image.fromarray(arr).save(bg / "images" / f"b_{i}.jpg")


def test_structure_agent_fallback_when_llm_fails(tmp_path):
    """LLM 调用失败时, agent 应降级到 fallback 模式生成 profile."""
    ds = tmp_path / "datasets"
    _make_mini_dataset(ds)

    agent = StructureAgent()
    # mock LLM chat 抛异常
    agent.llm.chat_with_retry = MagicMock(side_effect=RuntimeError("network down"))

    result = agent.run(str(ds))

    assert result.status == AgentStatus.FALLBACK
    assert "profile_yaml" in result.data
    assert "profile_dict" in result.data
    # 生成的 profile 应该有 face 和 bg 两个 source
    sources = result.data["profile_dict"]["sources"]
    source_names = [s["name"] for s in sources]
    assert "face" in source_names
    assert "bg" in source_names


def test_structure_agent_llm_success(tmp_path):
    """LLM 成功时, agent 应返回 NEEDS_CONFIRMATION."""
    ds = tmp_path / "datasets"
    _make_mini_dataset(ds)

    fake_yaml = """\
name: test
output_dir: ./out
classes: [pit]
train_split: 0.8
val_split: 0.2
test_split: 0.0
sources:
  - name: face
    path: /fake/face
    label_format: yolo
    class_mappings: []
    background: include
"""
    agent = StructureAgent()
    agent.llm.chat_with_retry = MagicMock(return_value=f"```yaml\n{fake_yaml}\n```")

    result = agent.run(str(ds))
    assert result.status == AgentStatus.NEEDS_CONFIRMATION
    assert "profile_yaml" in result.data
    assert "test" in result.data["profile_dict"]["name"]


def test_structure_agent_nonexistent_path(tmp_path):
    """路径不存在应返回失败."""
    agent = StructureAgent()
    result = agent.run(str(tmp_path / "nonexistent"))
    assert result.status == AgentStatus.FAILED


# ─────────────────────────────────────────────────────────────
#  Report Agent
# ─────────────────────────────────────────────────────────────
def test_report_agent_missing_dir(tmp_path):
    agent = ReportAgent()
    result = agent.run(str(tmp_path / "nonexistent"))
    assert result.status == AgentStatus.FAILED


def test_report_agent_no_results_csv(tmp_path):
    agent = ReportAgent()
    result = agent.run(str(tmp_path))  # 空目录
    assert result.status == AgentStatus.FAILED


def test_report_agent_with_results_csv(tmp_path):
    """有 results.csv 时, agent 应能解析并 (fallback) 生成报告."""
    # 写一个最小 results.csv
    csv_path = tmp_path / "results.csv"
    csv_path.write_text(
        "epoch,train/box_loss,train/cls_loss,train/dfl_loss,"
        "metrics/precision(B),metrics/recall(B),metrics/mAP50(B),metrics/mAP50-95(B)\n"
        "1,0.8,0.5,0.9,0.5,0.4,0.45,0.30\n"
        "2,0.6,0.4,0.8,0.7,0.6,0.65,0.45\n"
    )

    agent = ReportAgent()
    # mock LLM 失败, 测试 fallback
    agent.llm.chat_with_retry = MagicMock(side_effect=RuntimeError("no key"))

    result = agent.run(str(tmp_path))
    assert result.status == AgentStatus.FALLBACK
    assert "训练报告" in result.content or "训练" in result.content
    assert "epochs_completed" in result.data["metrics"]
