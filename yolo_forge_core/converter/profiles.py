"""Profile 数据模型：用 dataclass 描述源数据集结构和目标 YOLO 输出.

Profile 是声明式的 —— 用户在 YAML 里描述"我的源数据长这样、我要变成那样",
引擎按 profile 执行, 不依赖 LLM. 这一层保证可复现、可批量、可 CI.

设计目标
--------
1. 表达力够强：能覆盖 COCO、VOC、KITTI、多文件夹混合（用户案例）等常见结构
2. 不过度抽象：YAML 写出来要"一眼能看懂", 不搞 DSL
3. 校验前置：load 时就报错, 不让用户等转换跑到一半才崩

示例 YAML 见 examples/profiles/
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

from ..utils import IMG_EXTS


# ─────────────────────────────────────────────────────────────
#  枚举 / 常量
# ─────────────────────────────────────────────────────────────
class LabelFormat(str, Enum):
    """支持的源标签格式."""

    YOLO = "yolo"          # class_id cx cy w h (归一化)
    VOC = "voc"            # Pascal VOC XML
    COCO = "coco"          # COCO JSON (单个 json 文件描述整个 source)
    RAW_PX = "raw_px"      # class_id x1 y1 x2 y2 (绝对像素)
    NONE = "none"          # 纯背景图（无标签）


class BackgroundHandling(str, Enum):
    """背景图（无标注框）的处理方式."""

    INCLUDE = "include"    # 照常复制到输出（YOLO 训练支持空标签）
    SKIP = "skip"          # 跳过, 不复制
    COPY_NO_LABEL = "copy_no_label"  # 复制图片但不生成 label 文件
    DEDICATED_FOLDER = "dedicated_folder"  # 复制到单独的 background/ 子目录


# ─────────────────────────────────────────────────────────────
#  数据模型
# ─────────────────────────────────────────────────────────────
@dataclass
class ClassMapping:
    """源 class_id → 目标 YOLO class_id 的映射.

    如果 source 用 VOC/COCO 格式, class_name 字段会被用来匹配字符串类别名.
    """

    source_id: int = 0                  # 源 class id
    target_id: int = 0                  # 目标 class id
    source_name: Optional[str] = None   # 源类别名（VOC/COCO 用）

    @classmethod
    def from_dict(cls, d: dict) -> "ClassMapping":
        return cls(
            source_id=int(d.get("source_id", d.get("from", 0))),
            target_id=int(d.get("target_id", d.get("to", 0))),
            source_name=d.get("source_name") or d.get("name"),
        )


@dataclass
class Source:
    """一个源数据子集的描述.

    一个 source = 一个文件夹 + 一种标签格式 + 一组类别映射.
    一个 profile 可以包含多个 source（对应"多文件夹混合"场景）.
    """

    name: str                                   # source 名（用于日志和子目录命名）
    path: str                                   # 源文件夹根路径
    images_subdir: str = "images"               # 图片子目录（相对 path）
    labels_subdir: str = "labels"               # 标签子目录（相对 path）
    label_format: LabelFormat = LabelFormat.YOLO
    label_ext: str = ".txt"                     # 标签文件扩展名
    class_mappings: List[ClassMapping] = field(default_factory=list)
    background: BackgroundHandling = BackgroundHandling.INCLUDE
    filename_prefix: Optional[str] = None       # 可选: 输出文件名加前缀, 防止多 source 重名
    image_exts: set = field(default_factory=lambda: set(IMG_EXTS))

    # 仅 COCO 用
    coco_json: Optional[str] = None             # COCO instances.json 的相对路径

    def __post_init__(self) -> None:
        # 允许直接传 dict 进来, 自动转 ClassMapping
        if self.class_mappings and isinstance(self.class_mappings[0], dict):
            self.class_mappings = [ClassMapping.from_dict(m) for m in self.class_mappings]
        # 字符串形式兼容: label_format 可以是 str
        if isinstance(self.label_format, str):
            try:
                self.label_format = LabelFormat(self.label_format)
            except ValueError:
                self.label_format = LabelFormat.YOLO
        if isinstance(self.background, str):
            try:
                self.background = BackgroundHandling(self.background)
            except ValueError:
                self.background = BackgroundHandling.INCLUDE

    @classmethod
    def from_dict(cls, d: dict) -> "Source":
        mappings_raw = d.get("class_mappings") or []
        # 简写形式：{0: 0, 1: 1} 直接转列表
        if isinstance(mappings_raw, dict):
            mappings_raw = [
                {"source_id": int(k), "target_id": int(v)}
                for k, v in mappings_raw.items()
            ]
        mappings = [ClassMapping.from_dict(m) for m in mappings_raw]

        bg = d.get("background", "include")
        try:
            bg_enum = BackgroundHandling(bg)
        except ValueError:
            bg_enum = BackgroundHandling.INCLUDE

        fmt = d.get("label_format", "yolo")
        try:
            fmt_enum = LabelFormat(fmt)
        except ValueError:
            fmt_enum = LabelFormat.YOLO

        return cls(
            name=d["name"],
            path=d["path"],
            images_subdir=d.get("images_subdir", "images"),
            labels_subdir=d.get("labels_subdir", "labels"),
            label_format=fmt_enum,
            label_ext=d.get("label_ext", ".txt"),
            class_mappings=mappings,
            background=bg_enum,
            filename_prefix=d.get("filename_prefix"),
            image_exts=set(d.get("image_exts") or IMG_EXTS),
            coco_json=d.get("coco_json"),
        )

    def resolve_image_dir(self) -> Path:
        return Path(self.path) / self.images_subdir

    def resolve_label_dir(self) -> Path:
        return Path(self.path) / self.labels_subdir


@dataclass
class DatasetProfile:
    """完整的转换 profile.

    一个 profile = 多个 source + 目标类别列表 + 输出目录 + 切分规则.
    """

    name: str
    sources: List[Source]
    output_dir: str
    classes: List[str]                          # 目标 YOLO 数据集的类别名列表
    train_split: float = 0.8                    # 训练集比例
    val_split: float = 0.2
    test_split: float = 0.0
    seed: int = 42
    copy_strategy: str = "copy"                 # copy | symlink | move
    flatten: bool = True                        # 是否把所有 source 输出文件平铺到 images/labels 下
    description: str = ""

    def __post_init__(self) -> None:
        # 校验 split 之和 ≈ 1.0
        total = self.train_split + self.val_split + self.test_split
        if abs(total - 1.0) > 0.001:
            raise ValueError(
                f"train_split + val_split + test_split 必须为 1.0, 当前为 {total}"
            )

    @classmethod
    def from_dict(cls, d: dict) -> "DatasetProfile":
        sources = [Source.from_dict(s) for s in d.get("sources", [])]
        if not sources:
            raise ValueError("profile 至少要有一个 source")
        return cls(
            name=d["name"],
            sources=sources,
            output_dir=d["output_dir"],
            classes=list(d.get("classes", [])),
            train_split=float(d.get("train_split", 0.8)),
            val_split=float(d.get("val_split", 0.2)),
            test_split=float(d.get("test_split", 0.0)),
            seed=int(d.get("seed", 42)),
            copy_strategy=d.get("copy_strategy", "copy"),
            flatten=d.get("flatten", True),
            description=d.get("description", ""),
        )

    @classmethod
    def from_yaml(cls, path: str | Path) -> "DatasetProfile":
        """从 YAML 文件加载 profile."""
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f"profile 文件不存在: {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ValueError(f"profile YAML 顶层必须是 dict, 实际为 {type(data)}")
        return cls.from_dict(data)

    def to_yaml(self, path: str | Path) -> None:
        """把 profile 序列化为 YAML（用于 inspector 输出草稿）."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        data = {
            "name": self.name,
            "description": self.description,
            "output_dir": self.output_dir,
            "classes": self.classes,
            "train_split": self.train_split,
            "val_split": self.val_split,
            "test_split": self.test_split,
            "seed": self.seed,
            "copy_strategy": self.copy_strategy,
            "flatten": self.flatten,
            "sources": [
                {
                    "name": s.name,
                    "path": s.path,
                    "images_subdir": s.images_subdir,
                    "labels_subdir": s.labels_subdir,
                    "label_format": s.label_format.value,
                    "label_ext": s.label_ext,
                    "class_mappings": [
                        {"source_id": m.source_id, "target_id": m.target_id,
                         "source_name": m.source_name}
                        for m in s.class_mappings
                    ],
                    "background": s.background.value,
                    "filename_prefix": s.filename_prefix,
                }
                for s in self.sources
            ],
        }
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

    def validate(self) -> Tuple[bool, List[str]]:
        """校验 profile 合法性, 返回 (ok, errors)."""
        errors: List[str] = []
        if not self.name:
            errors.append("name 不能为空")
        if not self.classes:
            errors.append("classes 不能为空")
        for i, src in enumerate(self.sources):
            if not src.name:
                errors.append(f"sources[{i}].name 不能为空")
            if not Path(src.path).is_dir():
                errors.append(f"sources[{i}] ({src.name}) path 不存在: {src.path}")
        if self.copy_strategy not in ("copy", "symlink", "move"):
            errors.append(f"copy_strategy 必须是 copy/symlink/move, 实际 {self.copy_strategy}")
        return (len(errors) == 0), errors
