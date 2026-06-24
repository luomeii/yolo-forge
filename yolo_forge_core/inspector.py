"""确定性数据集探查器: 不依赖 LLM, 扫描文件夹给出结构化报告.

用途:
1. v0.2 GUI 里给用户看"这个目录到底长什么样"
2. 作为 LLM 结构探查 Agent 的"眼睛", 把扫描结果喂给 LLM 让它写 profile

设计原则:
- 100% 确定性: 同样的输入永远得到同样的输出
- 不修改任何文件, 只读
- 输出是 Pydantic dataclass, 容易序列化和给 LLM
"""
from __future__ import annotations

import os
import random
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .utils import IMG_EXTS, list_images, log


# ─────────────────────────────────────────────────────────────
#  报告数据模型
# ─────────────────────────────────────────────────────────────
@dataclass
class FolderStat:
    """单个子文件夹的扫描结果."""

    name: str
    path: str
    image_count: int = 0
    label_count: int = 0
    label_extensions: List[str] = field(default_factory=list)  # [.txt, .xml, .json]
    image_extensions: List[str] = field(default_factory=list)  # [.jpg, .png]
    has_images_subdir: bool = False
    has_labels_subdir: bool = False
    subfolder_names: List[str] = field(default_factory=list)   # 直接子文件夹名

    # 标签文件抽样分析（最多 5 个文件）
    sample_label_classes: Dict[int, int] = field(default_factory=dict)  # class_id → count
    sample_label_format: str = "unknown"  # yolo | raw_px | voc | coco | none | unknown
    sample_empty_labels: int = 0          # 空标签数
    sample_total_labels: int = 0

    # 是否纯背景文件夹
    looks_like_background: bool = False

    def summary_line(self) -> str:
        """一行总结."""
        cls_str = ", ".join(f"id{k}:{v}" for k, v in sorted(self.sample_label_classes.items())) or "无"
        return (
            f"{self.name}: {self.image_count} imgs, {self.label_count} labels, "
            f"fmt={self.sample_label_format}, classes={{{cls_str}}}"
        )


@dataclass
class InspectionReport:
    """整个数据集根目录的扫描报告."""

    root_path: str
    folders: List[FolderStat] = field(default_factory=list)
    total_images: int = 0
    total_labels: int = 0
    suggested_classes: List[str] = field(default_factory=list)  # 建议的目标类别名
    suggested_class_count: int = 0

    def to_markdown(self) -> str:
        """转 markdown 给 LLM / 给用户看."""
        lines = [
            f"# Dataset Inspection Report",
            f"",
            f"- **Root**: `{self.root_path}`",
            f"- **Total images**: {self.total_images}",
            f"- **Total label files**: {self.total_labels}",
            f"- **Sub-folders**: {len(self.folders)}",
            f"- **Suggested class count**: {self.suggested_class_count}",
            f"",
            f"## Folders",
            f"",
            f"| Folder | Images | Labels | Format | Detected classes |",
            f"|---|---|---|---|---|",
        ]
        for f in self.folders:
            cls = ", ".join(f"{k}:{v}" for k, v in sorted(f.sample_label_classes.items())) or "—"
            lines.append(
                f"| {f.name} | {f.image_count} | {f.label_count} | "
                f"{f.sample_label_format} | {cls} |"
            )
        return "\n".join(lines)

    def to_llm_prompt(self) -> str:
        """转紧凑文本给 LLM 推断 profile."""
        lines = [f"Dataset at: {self.root_path}"]
        lines.append(f"Total: {self.total_images} images, {self.total_labels} labels, {len(self.folders)} folders.")
        lines.append("")
        for f in self.folders:
            lines.append(f"## {f.name}/")
            lines.append(f"  images: {f.image_count} (exts: {','.join(f.image_extensions) or 'none'})")
            lines.append(f"  labels: {f.label_count} (exts: {','.join(f.label_extensions) or 'none'})")
            lines.append(f"  has images/ subdir: {f.has_images_subdir}")
            lines.append(f"  has labels/ subdir: {f.has_labels_subdir}")
            lines.append(f"  detected label format: {f.sample_label_format}")
            cls_str = ", ".join(f"id{k}:{v}" for k, v in sorted(f.sample_label_classes.items()))
            lines.append(f"  sampled classes: {cls_str or 'none'}")
            lines.append(f"  empty labels in sample: {f.sample_empty_labels}/{f.sample_total_labels}")
            if f.looks_like_background:
                lines.append(f"  **looks like background-only folder**")
            lines.append("")
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
#  探查核心
# ─────────────────────────────────────────────────────────────
def _detect_label_format(label_path: str) -> str:
    """通过文件扩展名 + 内容判断标签格式."""
    if not os.path.exists(label_path):
        return "none"

    ext = os.path.splitext(label_path)[1].lower()
    if ext == ".xml":
        return "voc"
    if ext == ".json":
        # 可能是单文件 COCO 也可能是每图一 json, 这里返回 coco 让上层判断
        return "coco"

    if ext == ".txt":
        # 读首行判断 yolo 还是 raw_px
        try:
            with open(label_path, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
            if not first_line:
                return "yolo"  # 空文件按 yolo 空标签处理
            parts = first_line.split()
            if len(parts) < 5:
                return "unknown"
            vals = [float(p) for p in parts[1:5]]
            # yolo 是归一化 [0,1], raw_px 是绝对像素值
            if all(0.0 <= v <= 1.0 for v in vals):
                return "yolo"
            return "raw_px"
        except Exception:
            return "unknown"

    return "unknown"


def _scan_label_classes(label_path: str, fmt: str, sample_size: int = 5) -> Tuple[Dict[int, int], int, int]:
    """扫描标签文件统计 class_id 分布.

    Returns
    -------
    classes : dict {class_id: count}
    empty_count : 空标签数
    total_count : 扫描的标签总数
    """
    classes: Dict[int, int] = Counter()
    empty = 0
    total = 0

    if not os.path.exists(label_path):
        return dict(classes), empty, total

    # 单文件标签直接返回空
    if fmt in ("voc", "coco"):
        # 这两种格式不好按文件级统计 class, 跳过
        return dict(classes), empty, total

    # 对 .txt 抽样最多 sample_size 个文件
    parent = os.path.dirname(label_path)
    if not os.path.isdir(parent):
        return dict(classes), empty, total

    txt_files = [f for f in os.listdir(parent) if f.endswith(".txt")]
    random.Random(42).shuffle(txt_files)
    for fname in txt_files[:sample_size]:
        total += 1
        fp = os.path.join(parent, fname)
        try:
            with open(fp, "r", encoding="utf-8") as f:
                content = f.read().strip()
            if not content:
                empty += 1
                continue
            for ln in content.splitlines():
                parts = ln.strip().split()
                if len(parts) >= 1:
                    try:
                        cid = int(parts[0])
                        classes[cid] += 1
                    except ValueError:
                        continue
        except Exception:
            continue

    return dict(classes), empty, total


def inspect_folder(folder_path: str | Path, sample_size: int = 5) -> FolderStat:
    """扫描单个文件夹, 返回 FolderStat."""
    folder = Path(folder_path)
    stat = FolderStat(name=folder.name, path=str(folder))

    if not folder.is_dir():
        return stat

    # 直接子文件夹
    stat.subfolder_names = [p.name for p in folder.iterdir() if p.is_dir()]

    # images/labels 子目录
    images_dir = folder / "images"
    labels_dir = folder / "labels"
    stat.has_images_subdir = images_dir.is_dir()
    stat.has_labels_subdir = labels_dir.is_dir()

    # 找图片
    if stat.has_images_subdir:
        img_source = images_dir
    else:
        img_source = folder
    imgs = list_images(img_source)
    stat.image_count = len(imgs)
    stat.image_extensions = sorted({os.path.splitext(f)[1].lower() for f in imgs})

    # 找标签
    if stat.has_labels_subdir:
        lbl_source = labels_dir
    else:
        lbl_source = folder
    if lbl_source.is_dir():
        lbl_files = [f for f in os.listdir(lbl_source)
                     if os.path.splitext(f)[1].lower() in {".txt", ".xml", ".json"}]
        stat.label_count = len(lbl_files)
        stat.label_extensions = sorted({os.path.splitext(f)[1].lower() for f in lbl_files})

        # 抽样一个标签判断格式
        if lbl_files:
            sample_path = str(lbl_source / lbl_files[0])
            stat.sample_label_format = _detect_label_format(sample_path)
            classes, empty, total = _scan_label_classes(sample_path, stat.sample_label_format, sample_size)
            stat.sample_label_classes = classes
            stat.sample_empty_labels = empty
            stat.sample_total_labels = total

    # 是否纯背景
    stat.looks_like_background = (stat.image_count > 0 and stat.label_count == 0)

    return stat


def inspect_dataset(root_path: str | Path, sample_size: int = 5) -> InspectionReport:
    """扫描整个数据集根目录.

    假设: root_path 下每个直接子文件夹是一个"源".
    如果 root_path 本身就是单源数据集, 也会扫一次.
    """
    root = Path(root_path)
    report = InspectionReport(root_path=str(root))

    if not root.is_dir():
        log.err(f"目录不存在: {root}")
        return report

    # 决定要扫哪些文件夹
    subdirs = [p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")]
    if not subdirs:
        # root 本身就是单源
        subdirs = [root]

    all_class_ids: set = set()
    for sd in subdirs:
        stat = inspect_folder(sd, sample_size=sample_size)
        report.folders.append(stat)
        report.total_images += stat.image_count
        report.total_labels += stat.label_count
        all_class_ids.update(stat.sample_label_classes.keys())

    # 建议类别数 = 所有源里出现过的最大 class_id + 1
    if all_class_ids:
        max_id = max(all_class_ids)
        report.suggested_class_count = max_id + 1
        report.suggested_classes = [f"class_{i}" for i in range(max_id + 1)]

    return report
