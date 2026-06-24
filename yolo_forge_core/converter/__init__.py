"""Converter 子包：声明式 YAML 驱动的数据集转换引擎.

Public API: :class:`DatasetProfile`, :func:`convert_dataset`
"""
from __future__ import annotations

from .engine import convert_dataset, ConversionReport
from .profiles import (
    DatasetProfile,
    Source,
    ClassMapping,
    BackgroundHandling,
    LabelFormat,
)

__all__ = [
    "DatasetProfile",
    "Source",
    "ClassMapping",
    "ConversionReport",
    "convert_dataset",
    "BackgroundHandling",
    "LabelFormat",
]
