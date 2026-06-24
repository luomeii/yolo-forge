"""内置 profile 模板：常见数据集结构的开箱即用模板.

这些模板在用户没有自己写 YAML 时可以直接通过 --template 引用.
"""
from __future__ import annotations

from typing import Dict

# 模板库：每个 entry 是一个 YAML 字符串, 用户可以基于它修改
BUILTIN_TEMPLATES: Dict[str, str] = {
    "multi_folder_mixed": """\
# 多文件夹混合数据集 → 干净 YOLO 输出
# 典型场景: 6 个子文件夹, 部分有标注部分纯背景, class id 含义需统一
name: my_dataset
description: Multi-folder mixed dataset merged into one YOLO layout

output_dir: ./yolo_output
classes: [pit, scratch]   # 目标类别名（顺序即 class_id）

train_split: 0.8
val_split: 0.2
test_split: 0.0
seed: 42
copy_strategy: copy       # copy | symlink | move
flatten: true

sources:
  # ── 有标注的源 ──
  - name: face
    path: D:/datasets/face
    images_subdir: images
    labels_subdir: labels
    label_format: yolo
    class_mappings:
      - {source_id: 0, target_id: 0}    # face 的 id=0 → 目标 id=0 (pit)
    background: include                 # 空标签图也纳入训练

  - name: line
    path: D:/datasets/line
    label_format: yolo
    class_mappings:
      - {source_id: 0, target_id: 0}    # line 的 id=0 → pit
      - {source_id: 1, target_id: 1}    # line 的 id=1 → scratch
    background: include

  - name: syn
    path: D:/datasets/syn
    label_format: yolo
    class_mappings:
      - {source_id: 0, target_id: 0}
      - {source_id: 1, target_id: 1}
    background: include

  # ── 纯背景源 ──
  - name: oil
    path: D:/datasets/oil
    label_format: none                  # 这个文件夹没有标签
    background: include                 # 当背景图用, 生成空 label

  - name: no_defect
    path: D:/datasets/no_defect
    label_format: none
    background: include

  - name: background
    path: D:/datasets/background
    label_format: none
    background: skip                    # 这个文件夹太杂, 直接跳过
""",

    "single_folder": """\
# 单文件夹 YOLO 数据集 → 标准化输出（加 train/val 切分）
name: single_folder_split
description: Take a single YOLO folder and split into train/val

output_dir: ./yolo_output
classes: [object]

train_split: 0.8
val_split: 0.2
test_split: 0.0
seed: 42

sources:
  - name: main
    path: ./my_dataset
    images_subdir: images
    labels_subdir: labels
    label_format: yolo
    class_mappings: []                 # 空 = source_id == target_id
    background: include
""",

    "voc_to_yolo": """\
# Pascal VOC → YOLO 转换
name: voc_to_yolo
description: Convert Pascal VOC XML annotations to YOLO format

output_dir: ./yolo_output
classes: [dog, cat, person]            # 目标类别名, 必须和 VOC XML 里的 name 一致

train_split: 0.8
val_split: 0.2
test_split: 0.0

sources:
  - name: voc_main
    path: ./VOCdevkit/VOC2012
    images_subdir: JPEGImages
    labels_subdir: Annotations
    label_format: voc
    label_ext: .xml
    # VOC 按类别名匹配, 不需要 id 映射
    class_mappings:
      - {source_name: dog, target_id: 0}
      - {source_name: cat, target_id: 1}
      - {source_name: person, target_id: 2}
    background: skip                   # VOC 通常没有"纯背景图", 但保险起见跳过
""",

    "coco_to_yolo": """\
# COCO JSON → YOLO 转换
name: coco_to_yolo
description: Convert COCO instances.json annotations to YOLO format

output_dir: ./yolo_output
classes: [person, bicycle, car, motorcycle, airplane, bus, train, truck, boat]

train_split: 1.0
val_split: 0.0
test_split: 0.0

sources:
  - name: coco_train
    path: ./coco
    images_subdir: train2017
    labels_subdir: annotations
    label_format: coco
    coco_json: instances_train2017.json   # 相对 source.path
    # COCO 按类别名匹配, 需要把 source_name 映射到 target_id
    class_mappings:
      - {source_name: person, target_id: 0}
      - {source_name: bicycle, target_id: 1}
      - {source_name: car, target_id: 2}
      - {source_name: motorcycle, target_id: 3}
      - {source_name: airplane, target_id: 4}
      - {source_name: bus, target_id: 5}
      - {source_name: train, target_id: 6}
      - {source_name: truck, target_id: 7}
      - {source_name: boat, target_id: 8}
    background: skip
""",

    "raw_px_to_yolo": """\
# 绝对像素坐标标签 → YOLO 归一化
# 适用: 自己标注的 .txt 里是 class_id x1 y1 x2 y2 (像素值)
name: raw_px_to_yolo
description: Convert raw pixel-coord labels to normalized YOLO format

output_dir: ./yolo_output
classes: [object]

train_split: 0.8
val_split: 0.2
test_split: 0.0

sources:
  - name: main
    path: ./raw_dataset
    images_subdir: images
    labels_subdir: labels
    label_format: raw_px
    label_ext: .txt
    class_mappings: []                  # 默认 source_id == target_id
    background: include
""",
}


def list_builtin_templates() -> list:
    """列出所有内置模板名."""
    return list(BUILTIN_TEMPLATES.keys())


def get_builtin_template(name: str) -> str:
    """取一个内置模板的 YAML 文本."""
    if name not in BUILTIN_TEMPLATES:
        raise KeyError(f"未知模板: {name}. 可用: {list(BUILTIN_TEMPLATES.keys())}")
    return BUILTIN_TEMPLATES[name]
