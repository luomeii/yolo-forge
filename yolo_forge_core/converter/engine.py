"""转换引擎核心：执行 DatasetProfile, 把源数据集转成干净的 YOLO 目录结构.

输出目录结构（flatten=True 时）::

    output_dir/
    ├── images/
    │   ├── train/  *.jpg
    │   ├── val/    *.jpg
    │   └── test/   *.jpg   (可选)
    ├── labels/
    │   ├── train/  *.txt
    │   ├── val/    *.txt
    │   └── test/   *.txt   (可选)
    ├── data.yaml
    ├── conversion_report.json
    └── background/    (background=dedicated_folder 时)
"""
from __future__ import annotations

import json
import os
import random
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..utils import (
    IMG_EXTS,
    coco_to_yolo,
    ensure_dir,
    log,
    px_to_yolo,
    stem_of,
    voc_to_yolo,
)
from .profiles import (
    BackgroundHandling,
    DatasetProfile,
    LabelFormat,
    Source,
)


# ─────────────────────────────────────────────────────────────
#  报告
# ─────────────────────────────────────────────────────────────
@dataclass
class SourceStat:
    """单个 source 的转换统计."""

    name: str
    total_images: int = 0
    total_boxes: int = 0
    converted: int = 0          # 成功转换的图片数
    skipped: int = 0            # 因 background=skip 跳过的图片数
    errors: int = 0             # 出错的图片数
    class_distribution: Dict[int, int] = field(default_factory=dict)


@dataclass
class ConversionReport:
    """整个转换任务的报告."""

    profile_name: str
    output_dir: str
    sources: List[SourceStat] = field(default_factory=list)
    train_count: int = 0
    val_count: int = 0
    test_count: int = 0
    background_count: int = 0
    total_boxes: int = 0
    final_classes: List[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self, path: str | Path) -> None:
        ensure_dir(Path(path).parent)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    def print_summary(self) -> None:
        log.hl(f"═══ Conversion Report: {self.profile_name} ═══")
        log.info(f"Output:        {self.output_dir}")
        log.info(f"Train/Val/Test: {self.train_count} / {self.val_count} / {self.test_count}")
        log.info(f"Background:    {self.background_count}")
        log.info(f"Total boxes:   {self.total_boxes}")
        log.info(f"Classes:       {self.final_classes}")
        log.info(f"Elapsed:       {self.elapsed_seconds:.2f}s")
        print()
        for s in self.sources:
            log.info(
                f"  [{s.name}] images={s.total_images} converted={s.converted} "
                f"skipped={s.skipped} errors={s.errors} boxes={s.total_boxes}"
            )
            if s.class_distribution:
                dist_str = ", ".join(f"cls{k}:{v}" for k, v in sorted(s.class_distribution.items()))
                log.info(f"      class dist: {dist_str}")


# ─────────────────────────────────────────────────────────────
#  标签读取器（按格式分发）
# ─────────────────────────────────────────────────────────────
def _read_yolo_label(path: str) -> List[Tuple[int, Tuple[float, float, float, float]]]:
    """读 YOLO 格式标签."""
    boxes = []
    if not os.path.exists(path):
        return boxes
    with open(path, "r", encoding="utf-8") as f:
        for ln in f:
            parts = ln.strip().split()
            if len(parts) >= 5:
                try:
                    cid = int(parts[0])
                    xywh = tuple(float(x) for x in parts[1:5])
                    boxes.append((cid, xywh))
                except ValueError:
                    continue
    return boxes


def _read_raw_px_label(path: str) -> List[Tuple[int, Tuple[int, int, int, int]]]:
    """读绝对像素坐标 (class_id x1 y1 x2 y2)."""
    boxes = []
    if not os.path.exists(path):
        return boxes
    with open(path, "r", encoding="utf-8") as f:
        for ln in f:
            parts = ln.strip().split()
            if len(parts) >= 5:
                try:
                    cid = int(parts[0])
                    x1, y1, x2, y2 = (int(float(v)) for v in parts[1:5])
                    boxes.append((cid, (x1, y1, x2, y2)))
                except ValueError:
                    continue
    return boxes


def _read_voc_label(path: str) -> List[Tuple[str, Tuple[float, float, float, float]]]:
    """读 VOC XML 标签, 返回 (class_name, (xmin, ymin, xmax, ymax))."""
    import xml.etree.ElementTree as ET
    if not os.path.exists(path):
        return []
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        size = root.find("size")
        W = int(size.find("width").text) if size is not None and size.find("width") is not None else 0
        H = int(size.find("height").text) if size is not None and size.find("height") is not None else 0
        boxes = []
        for obj in root.findall("object"):
            name_el = obj.find("name")
            bnd = obj.find("bndbox")
            if name_el is None or bnd is None:
                continue
            name = name_el.text.strip()
            xmin = float(bnd.find("xmin").text)
            ymin = float(bnd.find("ymin").text)
            xmax = float(bnd.find("xmax").text)
            ymax = float(bnd.find("ymax").text)
            # 不在这里归一化, 因为有时候 XML 不含 size, 后面用实际图片尺寸归一化
            boxes.append((name, (xmin, ymin, xmax, ymax, W, H)))
        return boxes
    except Exception as e:
        log.warn(f"读取 VOC XML 失败 {path}: {e}")
        return []


def _read_coco_label(json_path: str) -> Dict[str, List[Tuple[str, Tuple[float, float, float, float], int, int]]]:
    """读 COCO JSON, 返回 {file_stem: [(category_name, (x,y,w,h), W, H), ...]}.

    注意 COCO 的 (x, y) 是左上角, w/h 是绝对像素.
    """
    if not os.path.exists(json_path):
        return {}
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 类别 id → name
    cat_map = {c["id"]: c["name"] for c in data.get("categories", [])}
    # 图片 id → (file_stem, W, H)
    img_map = {
        im["id"]: (stem_of(im["file_name"]), im.get("width", 0), im.get("height", 0))
        for im in data.get("images", [])
    }

    result: Dict[str, List] = {}
    for ann in data.get("annotations", []):
        img_id = ann["image_id"]
        if img_id not in img_map:
            continue
        stem, W, H = img_map[img_id]
        cat_name = cat_map.get(ann["category_id"], f"cat_{ann['category_id']}")
        x, y, w, h = ann["bbox"]
        result.setdefault(stem, []).append((cat_name, (float(x), float(y), float(w), float(h)), W, H))
    return result


# ─────────────────────────────────────────────────────────────
#  转换核心
# ─────────────────────────────────────────────────────────────
def _resolve_split(rand: float, train_split: float, val_split: float) -> str:
    """根据随机数和切分比例决定一个样本属于哪个 split."""
    if rand < train_split:
        return "train"
    elif rand < train_split + val_split:
        return "val"
    else:
        return "test"


def _copy_or_link(src_path: str, dst_path: str, strategy: str) -> None:
    """按策略复制 / 软链接 / 移动文件."""
    ensure_dir(os.path.dirname(dst_path))
    if strategy == "symlink":
        if os.path.exists(dst_path):
            os.remove(dst_path)
        os.symlink(os.path.abspath(src_path), dst_path)
    elif strategy == "move":
        shutil.move(src_path, dst_path)
    else:  # copy
        shutil.copy2(src_path, dst_path)


def _convert_one_source(
    source: Source,
    profile: DatasetProfile,
    out_root: Path,
    rng: random.Random,
    stat: SourceStat,
    coco_cache: Optional[Dict] = None,
) -> None:
    """处理一个 source: 遍历图片, 读标签, 转换, 写到目标目录."""

    # 解析路径
    img_dir = source.resolve_image_dir()
    lbl_dir = source.resolve_label_dir()
    if not img_dir.is_dir():
        log.err(f"[{source.name}] 图片目录不存在: {img_dir}")
        return

    # 类别映射查找表
    # 对 YOLO/RAW_PX: source_id → target_id
    # 对 VOC/COCO:    source_name → target_id
    id_map: Dict[int, int] = {m.source_id: m.target_id for m in source.class_mappings}
    name_map: Dict[str, int] = {}
    for m in source.class_mappings:
        if m.source_name:
            name_map[m.source_name] = m.target_id

    # 没有显式映射时, 默认 source_id == target_id (限类别数内)
    if not source.class_mappings:
        id_map = {i: i for i in range(len(profile.classes))}

    # 遍历图片
    img_files = sorted(
        f for f in os.listdir(img_dir)
        if os.path.splitext(f)[1].lower() in source.image_exts
    )
    stat.total_images = len(img_files)

    # COCO 提前加载一次
    coco_data = None
    if source.label_format == LabelFormat.COCO:
        coco_json_path = source.coco_json or "instances.json"
        coco_data = coco_cache or _read_coco_label(str(Path(source.path) / coco_json_path))

    for fname in img_files:
        stem = stem_of(fname)
        img_path = str(img_dir / fname)

        # 输出文件名（可加前缀）
        out_stem = f"{source.filename_prefix}_{stem}" if source.filename_prefix else stem
        # 防止不同 source 间重名: 没显式 prefix 时自动用 source.name 前缀
        if not source.filename_prefix:
            out_stem = f"{source.name}_{stem}"

        # 找标签文件（COCO 除外, COCO 从 json 取）
        label_path: Optional[str] = None
        if source.label_format == LabelFormat.YOLO:
            label_path = str(lbl_dir / (stem + source.label_ext))
        elif source.label_format == LabelFormat.RAW_PX:
            label_path = str(lbl_dir / (stem + source.label_ext))
        elif source.label_format == LabelFormat.VOC:
            label_path = str(lbl_dir / (stem + ".xml"))

        # 读标签
        boxes_normalized: List[Tuple[int, Tuple[float, float, float, float]]] = []
        try:
            if source.label_format == LabelFormat.YOLO:
                raw = _read_yolo_label(label_path) if label_path else []
                for cid, xywh in raw:
                    target_id = id_map.get(cid, cid if cid < len(profile.classes) else -1)
                    if target_id < 0 or target_id >= len(profile.classes):
                        log.warn(f"[{source.name}] {fname}: class_id {cid} 超出目标类别范围, 跳过该框")
                        continue
                    boxes_normalized.append((target_id, xywh))
                    stat.class_distribution[target_id] = stat.class_distribution.get(target_id, 0) + 1

            elif source.label_format == LabelFormat.RAW_PX:
                raw = _read_raw_px_label(label_path) if label_path else []
                # 需要图片尺寸做归一化
                from PIL import Image
                with Image.open(img_path) as im:
                    W, H = im.size
                for cid, (x1, y1, x2, y2) in raw:
                    target_id = id_map.get(cid, cid if cid < len(profile.classes) else -1)
                    if target_id < 0 or target_id >= len(profile.classes):
                        continue
                    xywh = px_to_yolo(x1, y1, x2, y2, W, H)
                    boxes_normalized.append((target_id, xywh))
                    stat.class_distribution[target_id] = stat.class_distribution.get(target_id, 0) + 1

            elif source.label_format == LabelFormat.VOC:
                raw = _read_voc_label(label_path) if label_path else []
                # VOC 可能没存 size, 用实际图片尺寸兜底
                from PIL import Image
                with Image.open(img_path) as im:
                    W, H = im.size
                for name, (xmin, ymin, xmax, ymax, vw, vh) in raw:
                    target_id = name_map.get(name)
                    if target_id is None:
                        # 尝试按名字直接匹配目标类别列表
                        if name in profile.classes:
                            target_id = profile.classes.index(name)
                        else:
                            log.warn(f"[{source.name}] {fname}: 类别 '{name}' 未在 class_mappings 中, 跳过")
                            continue
                    W2 = vw if vw else W
                    H2 = vh if vh else H
                    xywh = voc_to_yolo(xmin, ymin, xmax, ymax, W2, H2)
                    boxes_normalized.append((target_id, xywh))
                    stat.class_distribution[target_id] = stat.class_distribution.get(target_id, 0) + 1

            elif source.label_format == LabelFormat.COCO:
                anns = (coco_data or {}).get(stem, [])
                for name, (x, y, w, h, vw, vh) in anns:
                    target_id = name_map.get(name)
                    if target_id is None and name in profile.classes:
                        target_id = profile.classes.index(name)
                    if target_id is None:
                        continue
                    from PIL import Image
                    with Image.open(img_path) as im:
                        W, H = im.size
                    xywh = coco_to_yolo(x, y, w, h, W, H)
                    boxes_normalized.append((target_id, xywh))
                    stat.class_distribution[target_id] = stat.class_distribution.get(target_id, 0) + 1

            elif source.label_format == LabelFormat.NONE:
                pass  # 纯背景图

        except Exception as e:
            log.err(f"[{source.name}] {fname}: 读取标签失败 {e}")
            stat.errors += 1
            continue

        stat.total_boxes += len(boxes_normalized)

        # 处理空标签背景图
        is_background = len(boxes_normalized) == 0
        if is_background:
            if source.background == BackgroundHandling.SKIP:
                stat.skipped += 1
                continue
            elif source.background == BackgroundHandling.DEDICATED_FOLDER:
                bg_dir = out_root / "background"
                ensure_dir(bg_dir)
                _copy_or_link(img_path, str(bg_dir / f"{out_stem}{os.path.splitext(fname)[1]}"),
                              profile.copy_strategy)
                stat.converted += 1
                continue
            elif source.background == BackgroundHandling.COPY_NO_LABEL:
                # 只复制图片, 不写 label
                pass
            # else: INCLUDE, 照常处理（YOLO 训练支持空 label 文件）

        # 决定 split
        split = _resolve_split(rng.random(), profile.train_split, profile.val_split)

        # 复制图片
        out_img_dir = out_root / "images" / split
        out_img_name = f"{out_stem}{os.path.splitext(fname)[1]}"
        _copy_or_link(img_path, str(out_img_dir / out_img_name), profile.copy_strategy)

        # 写 label
        out_lbl_dir = out_root / "labels" / split
        out_lbl_path = out_lbl_dir / f"{out_stem}.txt"
        ensure_dir(out_lbl_dir)

        if is_background and source.background == BackgroundHandling.COPY_NO_LABEL:
            # 不写 label 文件
            pass
        else:
            with open(out_lbl_path, "w", encoding="utf-8") as f:
                for cid, xywh in boxes_normalized:
                    f.write(f"{cid} {xywh[0]:.10f} {xywh[1]:.10f} {xywh[2]:.10f} {xywh[3]:.10f}\n")

        stat.converted += 1

    # 累计 source 的 split 计数（粗略, 实际应该按 split 分桶）
    # 这里在 source 循环内无法知道全局 split 分布, 留到主函数汇总


def _write_data_yaml(out_root: Path, classes: List[str]) -> None:
    """写 YOLO 训练用的 data.yaml."""
    yaml_path = out_root / "data.yaml"
    content = (
        f"path: {out_root.resolve().as_posix()}\n"
        f"train: images/train\n"
        f"val: images/val\n"
    )
    if (out_root / "images" / "test").is_dir():
        content += "test: images/test\n"
    content += "\nnames:\n"
    for i, name in enumerate(classes):
        content += f"  {i}: {name}\n"
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(content)


def _count_split_outputs(out_root: Path) -> Tuple[int, int, int]:
    """统计输出目录里 train/val/test 各自的图片数."""
    counts = [0, 0, 0]
    for i, split in enumerate(["train", "val", "test"]):
        d = out_root / "images" / split
        if d.is_dir():
            counts[i] = sum(1 for f in d.iterdir() if f.suffix.lower() in IMG_EXTS)
    return tuple(counts)  # type: ignore


def convert_dataset(profile: DatasetProfile, *, dry_run: bool = False) -> ConversionReport:
    """执行一次完整的 dataset 转换.

    Parameters
    ----------
    profile : DatasetProfile
        已加载好的 profile 对象
    dry_run : bool
        True 时只扫描源、不写文件, 用于校验 profile 正确性

    Returns
    -------
    ConversionReport
    """
    import time
    t0 = time.time()

    ok, errors = profile.validate()
    if not ok:
        raise ValueError("Profile 校验失败:\n  - " + "\n  - ".join(errors))

    out_root = Path(profile.output_dir)
    if not dry_run:
        ensure_dir(out_root)

    rng = random.Random(profile.seed)
    report = ConversionReport(
        profile_name=profile.name,
        output_dir=str(out_root),
        final_classes=list(profile.classes),
    )

    log.hl(f"═══ Converting dataset: {profile.name} ═══")
    log.info(f"Sources: {len(profile.sources)}  Output: {out_root}  Dry-run: {dry_run}")

    for source in profile.sources:
        stat = SourceStat(name=source.name)
        log.info(f"-> Processing source [{source.name}] ...")
        if dry_run:
            # dry-run 只统计文件数, 不真转
            img_dir = source.resolve_image_dir()
            if img_dir.is_dir():
                stat.total_images = sum(
                    1 for f in os.listdir(img_dir)
                    if os.path.splitext(f)[1].lower() in source.image_exts
                )
            log.ok(f"   [{source.name}] {stat.total_images} images (dry-run)")
            report.sources.append(stat)
            continue

        try:
            _convert_one_source(source, profile, out_root, rng, stat)
            log.ok(f"   [{source.name}] done: {stat.converted}/{stat.total_images} converted")
        except Exception as e:
            log.err(f"   [{source.name}] failed: {e}")
            stat.errors += 1

        report.sources.append(stat)

    if not dry_run:
        _write_data_yaml(out_root, profile.classes)
        report.train_count, report.val_count, report.test_count = _count_split_outputs(out_root)
        report.background_count = sum(
            1 for _ in (out_root / "background").iterdir()
        ) if (out_root / "background").is_dir() else 0
        report.total_boxes = sum(s.total_boxes for s in report.sources)
        report.elapsed_seconds = time.time() - t0

        # 保存报告
        report.save(out_root / "conversion_report.json")

    report.elapsed_seconds = time.time() - t0
    report.print_summary()
    return report
