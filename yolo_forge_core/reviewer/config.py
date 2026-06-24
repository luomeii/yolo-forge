"""Reviewer 配置：用 dataclass 替代原来的全局 CFG dict.

把硬编码路径完全去掉，所有配置通过 CLI / YAML 传入。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Set, Tuple

from ..utils import IMG_EXTS


@dataclass
class ReviewerConfig:
    """Reviewer 的运行配置.

    Attributes
    ----------
    image_dir : str
        图片目录
    label_dir : str
        标签目录（YOLO .txt 格式）
    output_dir : str
        归档输出目录（satisfied/unsatisfied 子目录会自动创建）
    classes : list of str
        类别名列表，索引即 class_id
    img_exts : set of str
        支持的图像扩展名
    max_w, max_h : int
        GUI 窗口最大宽高
    """

    image_dir: str
    label_dir: str
    output_dir: str
    classes: List[str] = field(default_factory=lambda: ["object"])
    img_exts: Set[str] = field(default_factory=lambda: set(IMG_EXTS))
    max_w: int = 1280
    max_h: int = 900

    def validate(self) -> Tuple[bool, str]:
        """校验配置合法性，返回 (ok, msg)."""
        if not self.image_dir:
            return False, "image_dir 不能为空"
        if not Path(self.image_dir).is_dir():
            return False, f"image_dir 不存在: {self.image_dir}"
        if not self.label_dir:
            return False, "label_dir 不能为空"
        if not self.classes:
            return False, "classes 至少要有一个"
        if self.max_w < 320 or self.max_h < 240:
            return False, "max_w/max_h 太小（至少 320x240）"
        return True, ""

    @classmethod
    def from_dict(cls, d: dict) -> "ReviewerConfig":
        """从 dict 构造（兼容旧的 CFG dict 风格）."""
        classes = list(d.get("classes") or ["object"])
        # 类别可能是 "a,b,c" 字符串形式
        if len(classes) == 1 and isinstance(classes[0], str) and "," in classes[0]:
            classes = [c.strip() for c in classes[0].split(",") if c.strip()]
        return cls(
            image_dir=d["image_dir"],
            label_dir=d["label_dir"],
            output_dir=d["output_dir"],
            classes=classes,
            img_exts=set(d.get("img_exts") or IMG_EXTS),
            max_w=int(d.get("max_w", 1280)),
            max_h=int(d.get("max_h", 900)),
        )
