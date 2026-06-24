"""转换引擎端到端测试.

构造一个迷你的"多文件夹混合"数据集 (类似用户的真实场景),
跑一遍 convert_dataset, 验证输出结构.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from yolo_forge_core.converter.engine import convert_dataset
from yolo_forge_core.converter.profiles import (
    BackgroundHandling,
    DatasetProfile,
    LabelFormat,
    Source,
)


def _make_dummy_image(path: Path, w: int = 100, h: int = 100, color=(128, 128, 128)):
    """创建一张占位 PNG."""
    arr = np.full((h, w, 3), color, dtype=np.uint8)
    Image.fromarray(arr).save(path)


def _make_yolo_label(path: Path, boxes):
    """写一个 YOLO 标签文件. boxes = [(cid, (cx, cy, w, h)), ...]"""
    with open(path, "w", encoding="utf-8") as f:
        for cid, xywh in boxes:
            f.write(f"{cid} {xywh[0]:.6f} {xywh[1]:.6f} {xywh[2]:.6f} {xywh[3]:.6f}\n")


@pytest.fixture
def mini_dataset(tmp_path) -> Path:
    """构造一个迷你版"多文件夹混合"数据集, 模仿用户的真实场景.

    结构:
        tmp_path/
        ├── face/      (2 张有标注, 仅 id=0)
        ├── line/      (2 张有标注, id=0+id=1)
        └── oil/       (2 张无标注, 背景图)
    """
    root = tmp_path / "datasets"

    # face 文件夹 (id=0 = pit)
    face = root / "face"
    (face / "images").mkdir(parents=True)
    (face / "labels").mkdir()
    for i in range(2):
        _make_dummy_image(face / "images" / f"face_{i}.jpg")
        _make_yolo_label(face / "labels" / f"face_{i}.txt", [(0, (0.5, 0.5, 0.2, 0.2))])

    # line 文件夹 (id=0 = pit, id=1 = scratch)
    line = root / "line"
    (line / "images").mkdir(parents=True)
    (line / "labels").mkdir()
    for i in range(2):
        _make_dummy_image(line / "images" / f"line_{i}.jpg")
        _make_yolo_label(line / "labels" / f"line_{i}.txt", [
            (0, (0.3, 0.3, 0.1, 0.1)),
            (1, (0.7, 0.7, 0.15, 0.15)),
        ])

    # oil 文件夹 (纯背景, 无标签)
    oil = root / "oil"
    (oil / "images").mkdir(parents=True)
    for i in range(2):
        _make_dummy_image(oil / "images" / f"oil_{i}.jpg")

    return root


def test_convert_multi_folder_mixed(mini_dataset, tmp_path):
    """端到端: 转换多文件夹混合数据集, 验证输出结构正确."""
    out_dir = tmp_path / "yolo_output"

    profile = DatasetProfile(
        name="test_mixed",
        sources=[
            Source(
                name="face",
                path=str(mini_dataset / "face"),
                label_format=LabelFormat.YOLO,
                class_mappings=[],
                background=BackgroundHandling.INCLUDE,
            ),
            Source(
                name="line",
                path=str(mini_dataset / "line"),
                label_format=LabelFormat.YOLO,
                class_mappings=[],
                background=BackgroundHandling.INCLUDE,
            ),
            Source(
                name="oil",
                path=str(mini_dataset / "oil"),
                label_format=LabelFormat.NONE,
                background=BackgroundHandling.INCLUDE,
            ),
        ],
        output_dir=str(out_dir),
        classes=["pit", "scratch"],
        train_split=1.0,
        val_split=0.0,
        test_split=0.0,
        seed=42,
    )

    report = convert_dataset(profile)

    # 验证报告
    assert report.profile_name == "test_mixed"
    assert len(report.sources) == 3
    assert report.train_count == 6  # 2 + 2 + 2
    assert report.val_count == 0

    # 验证目录结构
    assert (out_dir / "images" / "train").is_dir()
    assert (out_dir / "labels" / "train").is_dir()
    assert (out_dir / "data.yaml").is_file()
    assert (out_dir / "conversion_report.json").is_file()

    # 验证图片命名 (带 source 前缀防重)
    train_imgs = sorted(os.listdir(out_dir / "images" / "train"))
    assert "face_face_0.jpg" in train_imgs
    assert "line_line_0.jpg" in train_imgs
    assert "oil_oil_0.jpg" in train_imgs

    # 验证标签内容
    face_label = out_dir / "labels" / "train" / "face_face_0.txt"
    assert face_label.is_file()
    content = face_label.read_text().strip()
    parts = content.split()
    assert int(parts[0]) == 0  # pit

    # 验证背景图 (oil) 的 label 文件是空的
    oil_label = out_dir / "labels" / "train" / "oil_oil_0.txt"
    assert oil_label.is_file()
    assert oil_label.read_text().strip() == ""

    # 验证 data.yaml 内容
    data_yaml = (out_dir / "data.yaml").read_text()
    assert "pit" in data_yaml
    assert "scratch" in data_yaml

    # 验证 report JSON
    with open(out_dir / "conversion_report.json") as f:
        report_data = json.load(f)
    assert report_data["profile_name"] == "test_mixed"
    assert report_data["train_count"] == 6


def test_convert_dry_run(mini_dataset, tmp_path):
    """dry-run 不应产生任何输出文件, 但应统计源文件数."""
    out_dir = tmp_path / "yolo_output"

    profile = DatasetProfile(
        name="dry_run_test",
        sources=[
            Source(name="face", path=str(mini_dataset / "face"), label_format=LabelFormat.YOLO),
        ],
        output_dir=str(out_dir),
        classes=["pit"],
    )

    report = convert_dataset(profile, dry_run=True)
    assert not out_dir.exists()  # dry-run 不创建输出目录
    assert report.sources[0].total_images == 2


def test_convert_with_background_skip(mini_dataset, tmp_path):
    """background=skip 的源不应出现在输出里."""
    out_dir = tmp_path / "yolo_output"

    profile = DatasetProfile(
        name="skip_bg_test",
        sources=[
            Source(name="face", path=str(mini_dataset / "face"), label_format=LabelFormat.YOLO),
            Source(
                name="oil",
                path=str(mini_dataset / "oil"),
                label_format=LabelFormat.NONE,
                background=BackgroundHandling.SKIP,
            ),
        ],
        output_dir=str(out_dir),
        classes=["pit"],
        train_split=1.0,
        val_split=0.0,
    )

    report = convert_dataset(profile)
    # 只应该有 face 的 2 张图, oil 应该被跳过
    assert report.train_count == 2
    train_imgs = os.listdir(out_dir / "images" / "train")
    assert all("oil" not in f for f in train_imgs)


def test_convert_with_class_remapping(mini_dataset, tmp_path):
    """class_mappings 应当正确重映射 class_id."""
    out_dir = tmp_path / "yolo_output"

    # face 的 id=0 → target_id=1 (互换)
    profile = DatasetProfile(
        name="remap_test",
        sources=[
            Source(
                name="face",
                path=str(mini_dataset / "face"),
                label_format=LabelFormat.YOLO,
                class_mappings=[{"source_id": 0, "target_id": 1}],
            ),
        ],
        output_dir=str(out_dir),
        classes=["pit", "scratch"],
        train_split=1.0,
        val_split=0.0,
    )

    convert_dataset(profile)

    face_label = out_dir / "labels" / "train" / "face_face_0.txt"
    content = face_label.read_text().strip()
    parts = content.split()
    # 源 id=0 应被映射为 target id=1
    assert int(parts[0]) == 1
