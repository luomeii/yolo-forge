# 贡献指南 / Contributing

感谢你有兴趣为 yolo-forge 贡献代码！/ Thanks for your interest in contributing!

## 开发环境设置 / Dev setup

```bash
git clone https://github.com/luomeii/yolo-forge.git
cd yolo-forge
pip install -e ".[dev]"
```

跑测试:

```bash
pytest tests/ -v
```

## 项目结构 / Project structure

```
yolo_forge/
├── reviewer/        # YOLO 标签审查 GUI (OpenCV)
├── converter/       # 数据集转换引擎 (YAML profile 驱动)
│   ├── profiles.py  #   数据模型 + YAML 加载
│   ├── engine.py    #   转换核心
│   └── builtins.py  #   内置 profile 模板
├── cli.py           # 命令行入口
└── utils.py         # 共享工具
```

## 贡献方向 / What to contribute

### 容易上手 / Beginner-friendly
- **新增内置 profile 模板** — 你常用但还没收录的数据集结构
- **完善文档** — 修错别字、补示例、翻译
- **新增测试用例** — 覆盖更多边界情况

### 进阶 / Intermediate
- **支持新的 label_format** — 比如 KITTI、CreateML JSON
- **新增 splitter 策略** — 按类别分层抽样、按文件名规则切分
- **Inspector 模块** — 自动扫描陌生数据集结构, 生成 profile 草稿

### 进阶 / Advanced (v0.2+)
- **LLM Agent 层** — OpenAI 兼容 API 接入, 自动结构分析、训练报告生成
- **插件系统** — 让用户能注册自定义 label_format

## PR 流程 / PR workflow

1. Fork → 新建分支 (`feat-xxx` 或 `fix-xxx`)
2. 写代码 + 加测试
3. `pytest tests/ -v` 全过
4. PR 描述清楚改了什么、为什么改
5. 等待 review, 一般 48 小时内回复

## 代码风格 / Code style

- 用 ruff 检查 (`ruff check yolo_forge/`)
- 函数写 type hints
- 公共函数写 docstring (中英双语优先)
- 单文件不超过 ~500 行, 超了就拆

## 发布 / Release

由 maintainer 统一打 tag 和发 PyPI, 贡献者不需要关心.
