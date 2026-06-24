# Profile Schema 文档 / Profile Schema Reference

> yolo-forge 用一个 YAML `profile` 文件描述"源数据集长什么样、要变成什么样", 引擎按 profile 执行转换.
> A YAML `profile` describes "what the source dataset looks like and what it should become".

## 顶层字段 / Top-level fields

```yaml
name: my_dataset              # 必填 / required
description: "..."             # 可选 / optional
output_dir: ./yolo_output      # 必填 / required
classes: [pit, scratch]        # 必填 / required — 目标类别名列表, 顺序即 class_id

train_split: 0.8               # 训练集比例 (三者之和必须为 1.0)
val_split: 0.2
test_split: 0.0
seed: 42                       # 切分随机种子, 保证可复现

copy_strategy: copy            # copy | symlink | move
flatten: true                  # 是否把所有 source 平铺到同一个 images/labels 目录
```

## sources[]

每个 source 描述一个源子集. 一个 profile 可以有多个 source.

```yaml
sources:
  - name: face                          # 必填, 唯一标识符
    path: D:/datasets/face              # 必填, 源文件夹根路径
    images_subdir: images              # 默认 images
    labels_subdir: labels              # 默认 labels
    label_format: yolo                 # yolo | voc | coco | raw_px | none
    label_ext: .txt                    # 默认 .txt (voc 强制 .xml)
    class_mappings: []                 # 见下文
    background: include                # include | skip | copy_no_label | dedicated_folder
    filename_prefix: null              # 可选, 给输出文件名加前缀
    image_exts: [.jpg, .png]           # 可选, 自定义图片扩展名
    coco_json: instances_train.json    # 仅 coco 格式用
```

## class_mappings

描述"源 class_id / source_name → 目标 class_id"的映射.

### 三种写法

**1. 空 (`[]`)** — 默认 source_id == target_id, 适合单源已对齐的数据集:
```yaml
class_mappings: []
```

**2. dict 简写** — 适合 YOLO/RAW_PX 的纯 id 映射:
```yaml
class_mappings:
  0: 1     # source id 0 → target id 1
  1: 0     # source id 1 → target id 0
```

**3. 完整列表** — 唯一能处理 VOC/COCO 字符串类别名的写法:
```yaml
class_mappings:
  - {source_name: dog, target_id: 0}
  - {source_name: cat, target_id: 1}
  - {source_id: 0, target_id: 0}      # YOLO/RAW_PX 也可以用这种
```

## background 选项

源文件夹里的图片可能没有标注框 (空标签). 用 `background` 字段决定怎么处理:

| 值 | 行为 |
|---|---|
| `include` (默认) | 复制到 split 目录, 生成空 .txt (YOLO 训练支持负样本) |
| `skip` | 跳过, 不复制 |
| `copy_no_label` | 复制图片但不生成 .txt 文件 |
| `dedicated_folder` | 复制到 `output/background/` 单独目录 |

## label_format 详解

| 格式 | 文件内容 | class 匹配方式 |
|---|---|---|
| `yolo` | `class_id cx cy w h` (归一化) | 按 source_id 数值映射 |
| `raw_px` | `class_id x1 y1 x2 y2` (像素) | 按 source_id 数值映射 |
| `voc` | Pascal VOC XML | 按 source_name 字符串映射 |
| `coco` | COCO JSON | 按 source_name 字符串映射 |
| `none` | 无标签文件 | (纯背景源) |

## 完整示例 / Full example

见 `examples/profiles/multi_folder_mixed.yaml` —— 完整复刻"6 文件夹混合数据集"的真实场景.
