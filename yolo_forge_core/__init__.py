"""yolo_forge_core — 纯 Python 核心库, 无 GUI 依赖.

模块
----
- ``converter``  数据集转换引擎 (YAML profile 驱动)
- ``reviewer``   标签审查与补标 GUI (OpenCV, 不依赖 Qt)
- ``trainer``    训练封装 (薄包装 Ultralytics)
- ``inspector``  确定性数据集结构探查
- ``utils``      共享工具
"""
from __future__ import annotations

__version__ = "0.2.0"
__all__ = ["__version__"]
