# 🔨 yolo-forge

**Local-first Python-native YOLO dataset workstation: review, convert, train, analyze — unified in one PySide6 desktop app.**

**本地优先、Python 原生的 YOLO 数据集工作站：审查 / 转换 / 训练 / 分析，统一在一个 PySide6 桌面应用里。**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Version: 0.2.0](https://img.shields.io/badge/version-0.2.0-orange.svg)]()

> **核心原则**: 重复性劳动用确定性引擎完成, 创造性判断用 LLM Agent 辅助. **Agent 只生成配置和报告, 绝不直接修改数据.**
>
> **Core principle**: Deterministic engines handle repetitive work; LLM agents help with creative judgment. **Agents only generate configs and reports, never directly modify data.**

---

## Architecture / 架构

```
yolo-forge/
├── yolo_forge_core/         # 纯 Python 核心库, 无 GUI 依赖
│   ├── converter/           #   数据集转换引擎 (YAML profile 驱动) ✅
│   ├── reviewer/            #   标签审查 GUI (OpenCV) ✅
│   ├── trainer.py           #   训练封装 (薄包 Ultralytics) ✅
│   ├── inspector.py         #   确定性数据集探查 ✅
│   └── utils.py             #   共享工具
│
├── yolo_forge_agent/        # LLM Agent 模块 (依赖 core)
│   ├── config.py            #   ~/.yolo-forge/config.yaml 读写 ✅
│   ├── llm_client.py        #   OpenAI 兼容客户端 ✅
│   ├── base.py              #   Agent 基类 ✅
│   ├── structure_agent.py   #   结构探查 Agent ✅
│   └── report_agent.py      #   训练报告 Agent ✅
│
├── yolo_forge_desktop/      # PySide6 桌面 GUI (依赖 core + agent)
│   ├── main_window.py       #   类 Codex 三栏布局 ✅
│   ├── panels/              #   6 个功能面板 ✅
│   ├── theme.py             #   暗色 IDE 主题 ✅
│   └── app.py               #   入口 ✅
│
├── examples/profiles/       # 5 个内置 YAML 模板
├── tests/                   # 43 个单元测试
└── docs/                    # 文档
```

**模块依赖关系 (高内聚低耦合)**:
```
desktop  →  agent  →  core  →  (numpy/opencv/ultralytics/pyyaml)
   ↑          ↑
   └──────────┴─  共享 config.yaml
```

---

## Why? / 解决什么问题

If you do YOLO object detection, you've probably hit these pain points:

1. **Auto-labeling produces 90% correct boxes, but reviewing them is painful.** LabelImg is dead, CVAT is too heavy for solo use.
2. **Real-world datasets come in weird shapes.** Your advisor hands you 6 folders with mixed label formats, different class id conventions, and "background" folders. You write a one-off conversion script every time.
3. **No unified toolchain.** You jump between LabelImg (review), custom scripts (convert), terminal (train), and Jupyter (analyze). Each step is a context switch.

`yolo-forge` solves all three in one local app:

- **Reviewer** — OpenCV canvas embedded in Qt, review/patch/delete/move boxes, archive satisfied/unsatisfied.
- **Converter** — Declarative YAML profile converts heterogeneous datasets to clean YOLO layout.
- **Inspector** — Deterministic structure scanner (no LLM), generates report + LLM prompt.
- **Trainer** — Thin wrapper over Ultralytics, runs in subprocess, real-time progress.
- **Agent** — LLM agents for structure inference and training report (with graceful fallback).
- **Unified** — All in one PySide6 window, dark IDE theme.

如果你做 YOLO 检测, 这三个痛点你应该都熟:

1. **自动标注 90% 准, 但 review 起来很痛苦.** LabelImg 停更, CVAT 单人用太重.
2. **真实数据集结构千奇百怪.** 老师丢给你 6 个文件夹, 标签格式不统一, class id 含义不一致, 还有几个"纯背景"文件夹.
3. **没有统一工具链.** 在 LabelImg (审查) / 自写脚本 (转换) / 终端 (训练) / Jupyter (分析) 之间反复横跳.

`yolo-forge` 一次解决:

- **Reviewer** — OpenCV 画布嵌入 Qt, 审查/补标/删除/拖动框, 满意/不满意归档
- **Converter** — 声明式 YAML profile, 一键转换异构数据集
- **Inspector** — 确定性结构扫描 (不调 LLM), 生成报告 + LLM prompt
- **Trainer** — Ultralytics 薄封装, 子进程跑, 实时进度
- **Agent** — LLM 智能体 (结构推断 + 训练报告), 失败时优雅降级
- **统一** — 一个 PySide6 窗口, 暗色 IDE 主题

---

## Install / 安装

```bash
# 完整安装 (core + agent + desktop)
pip install "yolo-forge[all]"

# 或按需安装
pip install yolo-forge                    # 仅 core
pip install "yolo-forge[desktop]"         # + GUI
pip install "yolo-forge[agent]"           # + LLM agent
```

**Dependencies**:
- Core: `numpy`, `opencv-python`, `pyyaml`, `pillow`, `tqdm`, `pydantic`, `ultralytics`
- Desktop: `PySide6>=6.5`
- Agent: `openai>=1.0`

---

## Quick Start / 快速上手

### Launch the desktop app / 启动桌面应用

```bash
yolo-forge-desktop
```

A window like VS Code / Cursor opens with three panels:
- **Left**: Navigation (Converter / Inspector / Reviewer / Trainer / Settings)
- **Center**: Main workspace (switches by left selection)
- **Right**: Agent chat panel (with LLM when configured)

打开后是一个类 VS Code / Cursor 的三栏窗口:
- **左栏**: 功能导航 (Converter / Inspector / Reviewer / Trainer / Settings)
- **中栏**: 主工作区 (根据左栏切换)
- **右栏**: Agent 对话面板

### 1. Configure LLM / 配置 LLM

Switch to **Settings** panel, fill in:
- API Key (e.g. `sk-...`)
- Base URL (e.g. `https://api.openai.com/v1` or `https://api.deepseek.com/v1`)
- Model (e.g. `gpt-4o-mini` / `deepseek-chat` / `glm-4-flash`)

Click **Test Connection** to verify, then **Save**.

Config is stored at `~/.yolo-forge/config.yaml` (chmod 600).

### 2. Convert a messy dataset / 转换杂乱数据集

Two ways:

**A) Use Agent** (right panel): type `分析 /path/to/dataset`. Agent scans structure, generates a profile YAML draft. Review it, then run.

**B) Manual**: Switch to **Converter** panel, pick a YAML profile (or template), click **Run Conversion**.

See [`examples/profiles/multi_folder_mixed.yaml`](examples/profiles/multi_folder_mixed.yaml) for the "advisor's 6-folder mixed dataset" case.

### 3. Review labels / 审查标签

**Reviewer** panel → fill image/label dirs → **Start Reviewing**.

OpenCV canvas is embedded in Qt. Use keyboard shortcuts:
- `j`/`l` prev/next, `k` satisfied, `d` unsatisfied, `a` enter draw mode
- `0-9` `[` `]` switch class, `n` new class, `Backspace` delete
- Click box to select, drag to move, right-click to deselect
- Scroll = zoom, middle-drag = pan, `f` = fit screen

### 4. Train / 训练

**Trainer** panel → fill data.yaml + hyperparams → **Start Training**.

Training runs in subprocess; logs stream in real-time. When done, click **Generate Report** to let the Report Agent analyze results.

### 5. CLI (without GUI) / 命令行用法

```bash
# Inspect dataset structure (deterministic, no LLM)
yolo-forge inspect /path/to/dataset --markdown

# Convert
yolo-forge convert --profile my_profile.yaml

# Train (subprocess)
yolo-forge train --data data.yaml --model yolo11n.pt --epochs 100

# Launch reviewer (standalone OpenCV window)
yolo-forge review --images ./images --labels ./labels --classes pit,car

# List builtin profile templates
yolo-forge templates --list
```

---

## Supported source formats / 支持的源格式

| Format | Description | Class matching |
|---|---|---|
| `yolo` | `class_id cx cy w h` (normalized) | by `source_id` |
| `raw_px` | `class_id x1 y1 x2 y2` (pixel) | by `source_id` |
| `voc` | Pascal VOC XML | by `source_name` (string) |
| `coco` | COCO instances.json | by `source_name` (string) |
| `none` | no labels (background only) | n/a |

Background handling: `include` (default) / `skip` / `copy_no_label` / `dedicated_folder`.

See [docs/profile_schema.md](docs/profile_schema.md) for full schema.

---

## LLM Agent design / LLM Agent 设计

**Two agents in v0.2**:

1. **Structure Agent** — Drop a folder path → agent scans (deterministic `inspect_dataset`) → LLM infers `class_mappings` / `background` strategy → outputs profile YAML draft → **user confirms** → converter engine executes.
2. **Report Agent** — Point at training output dir → agent parses `results.csv` → LLM writes markdown analysis (overall performance, per-class weakness, training curve observations, improvement suggestions).

**Security boundary / 安全边界**:
- Agents ONLY generate configs (YAML) and reports (markdown)
- All actual data operations go through tested deterministic engines
- LLM failure triggers graceful fallback to deterministic mode
- 用户始终在循环中 (human-in-the-loop) — profile 草稿必须人工确认才执行

**Why OpenAI-compatible API only / 为什么只支持 OpenAI 兼容 API**:
- One client implementation, broad compatibility
- Works with: OpenAI / DeepSeek / 智谱 GLM / 通义千问 / Moonshot / Ollama / vLLM / One-API
- If you want Claude, run it through an OpenAI-compatible proxy (LiteLLM / One-API)

---

## Tech stack / 技术栈

| Layer | Choice | Reason |
|---|---|---|
| Core lib | Python 3.9+ / Pydantic / PyYAML | Type-safe, minimal deps |
| GUI | PySide6 (Qt6 LGPL) | Python-native, embeds OpenCV, no separate backend |
| CV | OpenCV + Ultralytics | Industry standard |
| Agent | OpenAI Python SDK | Mature, broad provider support |
| Training | Ultralytics native API | Not reinventing the wheel |
| Config | Single `~/.yolo-forge/config.yaml` | Simple, debuggable |

**Monorepo, three modules, one `pip install`**. Each module has clean boundaries:
- `yolo_forge_core` has zero GUI / LLM deps
- `yolo_forge_agent` depends on core only
- `yolo_forge_desktop` depends on both, adds Qt

---

## Roadmap / 路线图

### v0.2 (current / 当前) ✅
- Monorepo: core / agent / desktop
- PySide6 desktop app with dark IDE theme
- 6 panels: Converter / Inspector / Reviewer / Trainer / Settings + Agent chat
- Structure Agent + Report Agent with fallback
- Trainer (Ultralytics subprocess) + Inspector (deterministic)
- 43 unit tests passing

### v0.3 (next / 下一个)
- 🔜 Inspector integration into Structure Agent (auto-scan → auto-profile → auto-convert)
- 🔜 Training execution Agent (multi-step: convert → train → report)
- 🔜 Dataset visualization (class distribution charts, box size heatmap)
- 🔜 Plugin system for custom `label_format`

### v0.4+
- 🔜 Augmentation module
- 🔜 Multi-dataset management
- 🔜 Active learning loop (train → predict → suggest uncertain samples → review)

---

## Contributing / 贡献

See [CONTRIBUTING.md](CONTRIBUTING.md). PRs welcome — especially new profile templates, label format support, and theme variants.

## License / 许可

[MIT](LICENSE)
