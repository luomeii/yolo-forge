# YOLO-Forge SP

> 智能YOLO数据集工作站 — 基于Codex/Claude Code架构模式的完全重构版本

[![Version](https://img.shields.io/badge/version-3.0.0-7CB342.svg)]()
[![License](https://img.shields.io/badge/license-MIT-7CB342.svg)]()
[![Electron](https://img.shields.io/badge/Electron-35-7CB342.svg)]()
[![React](https://img.shields.io/badge/React-19-7CB342.svg)]()

## 概述

YOLO-Forge SP 是一个基于 Electron + React + TypeScript + Python Worker 的智能 YOLO 数据集工作站。采用 Codex CLI 和 Claude Code 的架构模式，提供完整的 Agent 循环、工具系统、权限管理和上下文压缩。

### 核心特性

- **智能体系统** — 支持 OpenAI 和 Anthropic SDK，流式输出，多轮工具调用
- **权限管理** — Codex式3选项（本次允许/始终允许/拒绝），安全命令白名单
- **上下文管理** — 五策略压缩（Snip/Microcompact/Autocompact/Collapse/Reactive）
- **数据集检测** — 自动扫描目录结构，识别 YOLO/VOC/COCO/raw_px 格式
- **格式转换** — 多格式互转，YAML Profile 声明式配置，dry-run 预览
- **模型训练** — 基于 Ultralytics，完整参数配置，实时进度同步
- **标签审查** — Canvas 可视化标注，补框/删除/撤销，自动保存
- **任务管理** — 训练任务可视化，实时进度/日志，系统通知

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 桌面框架 | Electron 35 | 跨平台桌面应用 |
| 前端框架 | React 19 | 渲染进程 UI |
| 状态管理 | Zustand 5 | 轻量级全局状态 |
| 构建工具 | Vite 6 | 快速 HMR 开发 |
| LLM SDK | OpenAI SDK + Anthropic SDK | 双 Provider 支持 |
| YOLO计算 | Python Worker (Ultralytics) | 子进程 NDJSON 通信 |
| 样式 | CSS Variables | 花笺主题（浅绿淡雅） |

## 架构

```
┌─────────────────────────────────────────────┐
│              Electron Main Process            │
│  ┌─────────────────────────────────────────┐ │
│  │       Agent Orchestrator (核心)          │ │
│  │  ┌─────────────────────────────────────┐ │ │
│  │  │  ReAct Loop (async generator ×7)    │ │ │
│  │  │  ┌──────────┬───────────────────┐   │ │ │
│  │  │  │ LLM Call │ Tool Execution    │   │ │ │
│  │  │  └──────────┴───────────────────┘   │ │ │
│  │  └─────────────────────────────────────┘ │ │
│  │  ┌──────────┬──────────┬──────────────┐  │ │
│  │  │ OpenAI   │Anthropic │ Context Mgr  │  │ │
│  │  │ Provider │ Provider │ (5 strategies)│  │ │
│  │  └──────────┴──────────┴──────────────┘  │ │
│  │  ┌─────────────────────────────────────┐ │ │
│  │  │  Tool Registry (9 tools)           │ │ │
│  │  │  Permission Manager (Codex-style)  │ │ │
│  │  └─────────────────────────────────────┘ │ │
│  └─────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────┐ │
│  │  Python Worker (subprocess, NDJSON IPC) │ │
│  │  inspect | convert | train | report     │ │
│  └─────────────────────────────────────────┘ │
├─────────────────────────────────────────────┤
│           IPC Bridge (contextBridge)          │
├─────────────────────────────────────────────┤
│            Renderer Process (React)           │
│  ┌──────┬──────────────────┬──────────────┐ │
│  │ Side │   Main Panel     │  Agent Chat  │ │
│  │ bar  │ Inspector/Conv/  │  (streaming) │ │
│  │ 72px │ Trainer/Reviewer │  420px       │ │
│  │      │ Tasks/Settings   │              │ │
│  └──────┴──────────────────┴──────────────┘ │
└─────────────────────────────────────────────┘
```

## 项目结构

```
yolo-forge-sp/
├── electron/                    # Electron 主进程
│   ├── main.ts                  # 入口
│   ├── preload.ts               # 安全 IPC 桥接
│   ├── store.ts                 # JSON 持久化配置
│   ├── agent/                   # Agent 核心系统
│   │   ├── orchestrator.ts      # Agent 编排器
│   │   ├── providers/           # LLM Provider (OpenAI/Anthropic)
│   │   ├── tools/               # 9个工具
│   │   ├── permissions/         # Codex式权限管理
│   │   ├── context/             # 五策略上下文压缩
│   │   └── loop/                # 会话管理
│   ├── ipc/handlers.ts          # IPC 处理器
│   ├── workers/python-manager.ts # Python 子进程管理
│   └── python/worker.py         # YOLO 计算 Worker
├── src/                         # React 渲染进程
│   ├── components/
│   │   ├── layout/              # 布局组件
│   │   ├── chat/                # Agent 聊天
│   │   └── panels/              # 功能面板
│   ├── stores/app-store.ts      # Zustand 状态
│   ├── i18n/index.ts            # 中英文国际化
│   └── styles/globals.css       # 花笺主题
└── package.json
```

## 快速开始

### 环境要求

- Node.js 20+
- Python 3.9+ (conda 推荐)
- CUDA GPU (可选，训练用)

### 安装

```bash
# 1. 安装 Node.js 依赖
npm install

# 2. 安装 Python 依赖
pip install -r electron/python/requirements.txt

# 3. 启动开发模式
npm run electron:dev
```

### 配置

1. 启动应用后进入 Settings 面板
2. 选择 Provider (OpenAI / Anthropic)
3. 输入 API Key
4. 选择模型（可从 API 动态获取模型列表）
5. 保存

### 使用

- **Agent Chat**: 右侧聊天面板，自然语言交互
- **Inspector**: 扫描数据集结构
- **Converter**: 格式转换
- **Trainer**: 模型训练（自动扫描 conda 环境/GPU）
- **Reviewer**: 标签可视化审查
- **Tasks**: 训练任务管理

## 设计理念

### 花笺主题

界面设计灵感来自[花笺项目](https://github.com/Achilng/floral-notepaper)，采用浅绿淡雅的色调，营造生机勃勃但不失沉稳的工作环境：

- **主色调**: 浅绿 `#7CB342`，象征生机
- **背景**: 米白偏绿 `#F9FBF7`，柔和护眼
- **文字**: 深绿灰 `#2E3B2F`，清晰易读
- **质感**: 毛玻璃 + 轻阴影，层次分明

### 对标 Codex / Claude Code

- **Agent 循环**: 7 yield 点的异步生成器状态机
- **权限系统**: 默认拒绝 + 3选项 + 安全命令白名单
- **上下文管理**: 5 策略压缩，自动触发
- **工具系统**: 9 个工具，风险分级，权限控制

## License

MIT
