"""Inspector 模块测试."""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from yolo_forge_core.inspector import inspect_dataset, inspect_folder


def _make_image(path: Path, w=100, h=100):
    arr = np.full((h, w, 3), 128, dtype=np.uint8)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr).save(path)


def _make_yolo_label(path: Path, boxes):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for cid, xywh in boxes:
            f.write(f"{cid} {xywh[0]:.6f} {xywh[1]:.6f} {xywh[2]:.6f} {xywh[3]:.6f}\n")


@pytest.fixture
def mini_dataset(tmp_path) -> Path:
    """构造一个迷你多文件夹数据集."""
    root = tmp_path / "datasets"

    # face 文件夹 (id=0)
    face = root / "face"
    for i in range(3):
        _make_image(face / "images" / f"face_{i}.jpg")
        _make_yolo_label(face / "labels" / f"face_{i}.txt", [(0, (0.5, 0.5, 0.2, 0.2))])

    # line 文件夹 (id=0 + id=1)
    line = root / "line"
    for i in range(2):
        _make_image(line / "images" / f"line_{i}.jpg")
        _make_yolo_label(line / "labels" / f"line_{i}.txt", [
            (0, (0.3, 0.3, 0.1, 0.1)),
            (1, (0.7, 0.7, 0.1, 0.1)),
        ])

    # oil 文件夹 (纯背景)
    oil = root / "oil"
    for i in range(2):
        _make_image(oil / "images" / f"oil_{i}.jpg")

    return root


def test_inspect_single_folder(mini_dataset):
    """扫单文件夹."""
    stat = inspect_folder(mini_dataset / "face")
    assert stat.name == "face"
    assert stat.image_count == 3
    assert stat.label_count == 3
    assert stat.has_images_subdir
    assert stat.has_labels_subdir
    assert stat.sample_label_format == "yolo"
    assert 0 in stat.sample_label_classes


def test_inspect_dataset_root(mini_dataset):
    """扫整个数据集根目录."""
    report = inspect_dataset(mini_dataset)
    assert len(report.folders) == 3  # face, line, oil
    assert report.total_images == 7  # 3+2+2
    assert report.total_labels == 5  # 3+2+0

    # 类别建议: 出现过的最大 class_id 是 1, 建议类别数 = 2
    assert report.suggested_class_count == 2

    # oil 是纯背景
    oil_stat = next(f for f in report.folders if f.name == "oil")
    assert oil_stat.looks_like_background is True
    assert oil_stat.label_count == 0


def test_inspect_report_markdown(mini_dataset):
    """markdown 报告能正常生成."""
    report = inspect_dataset(mini_dataset)
    md = report.to_markdown()
    assert "Dataset Inspection Report" in md
    assert "face" in md
    assert "line" in md
    assert "oil" in md


def test_inspect_report_llm_prompt(mini_dataset):
    """LLM prompt 文本能正常生成."""
    report = inspect_dataset(mini_dataset)
    prompt = report.to_llm_prompt()
    assert "Dataset at" in prompt
    assert "face" in prompt
    assert "looks like background" in prompt  # oil 应该被标记


def test_inspect_raw_px_format(tmp_path):
    """raw_px 格式能被识别."""
    root = tmp_path / "raw"
    (root / "images").mkdir(parents=True)
    (root / "labels").mkdir(parents=True)
    for i in range(2):
        _make_image(root / "images" / f"img_{i}.jpg")
        # 写绝对像素坐标 (大于 1.0)
        with open(root / "labels" / f"img_{i}.txt", "w") as f:
            f.write("0 50 50 100 100\n")

    stat = inspect_folder(root)
    assert stat.sample_label_format == "raw_px"


def test_inspect_empty_folder(tmp_path):
    """扫空文件夹不崩."""
    stat = inspect_folder(tmp_path / "empty")
    assert stat.image_count == 0
    assert stat.label_count == 0
    assert stat.sample_label_format == "unknown"
