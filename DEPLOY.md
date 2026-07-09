# YOLO-Forge SP — 部署与操作手册

> 版本 1.0.0-sp | 最后更新: 2026-06-26

---

## 目录

1. [系统要求](#1-系统要求)
2. [快速开始](#2-快速开始)
3. [开发环境搭建](#3-开发环境搭建)
4. [项目架构详解](#4-项目架构详解)
5. [配置指南](#5-配置指南)
6. [功能模块说明](#6-功能模块说明)
7. [生产构建与打包](#7-生产构建与打包)
8. [部署方案](#8-部署方案)
9. [故障排除](#9-故障排除)
10. [开发者参考](#10-开发者参考)

---

## 1. 系统要求

### 必需环境

| 组件 | 最低版本 | 推荐版本 | 说明 |
|------|---------|---------|------|
| **Node.js** | 18.x | 20.x LTS | JavaScript运行时 |
| **npm** | 9.x | 10.x | 包管理器 |
| **Python** | 3.9+ | 3.11+ | YOLO计算后端 |
| **pip** | 最新 | 最新 | Python包管理 |

### 可选依赖（按功能需求）

| 组件 | 用途 | 安装命令 |
|------|------|---------|
| **CUDA/cuDNN** | GPU加速训练 | 见NVIDIA官方文档 |
| **Git** | 版本控制 | 系统包管理器 |

### 操作系统支持

| 系统 | 架构 | 状态 |
|------|------|------|
| macOS 12+ | x64, arm64 (M1/M2/M3) | ✅ 完全支持 |
| Ubuntu 20.04+ / Debian 11+ | x64 | ✅ 完全支持 |
| Windows 10/11 | x64 | ✅ 完全支持 |

### 磁盘空间

- 开发环境: ~2GB (含node_modules)
- 生产构建: ~300MB (含Electron运行时)
- Python依赖: ~1.5GB (含PyTorch/Ultralytics)

---

## 2. 快速开始

### 一键安装

```bash
# 克隆项目
git clone https://github.com/your-username/yolo-forge-sp.git
cd yolo-forge-sp

# 运行安装脚本
chmod +x scripts/setup.sh
./scripts/setup.sh
```

### 手动安装

```bash
# 1. 安装Node.js依赖
npm install

# 2. 安装Python依赖
pip install -r electron/python/requirements.txt

# 3. 启动开发模式
npm run electron:dev
```

### 首次运行配置

1. 启动应用后，左侧导航栏点击 ⚙️ Settings
2. 选择LLM Provider (OpenAI 或 Anthropic)
3. 输入API Key
4. 点击 "Test Connection" 验证连接
5. 点击 "Save Settings" 保存

---

## 3. 开发环境搭建

### 3.1 获取源码

```bash
git clone https://github.com/your-username/yolo-forge-sp.git
cd yolo-forge-sp
```

### 3.2 安装依赖

```bash
# Node.js 依赖
npm install

# Python 依赖（YOLO功能必需）
pip install -r electron/python/requirements.txt

# 验证Python worker
python3 -c "
import sys; sys.path.insert(0,'electron/python')
from worker import HANDLERS
print(f'Workers: {list(HANDLERS.keys())}')
"
```

### 3.3 开发命令

| 命令 | 用途 |
|------|------|
| `npm run dev` | 仅启动Vite开发服务器（前端） |
| `npm run electron:dev` | 启动Electron + Vite完整开发环境 |
| `npm run typecheck` | TypeScript类型检查 |
| `npm run build` | 构建Vite前端 |
| `npm run build:all` | 构建前端 + Electron主进程 |
| `npm run clean` | 清理构建产物 |

### 3.4 开发流程

```
npm run electron:dev
  │
  ├─ Vite Dev Server (http://localhost:5173)
  │   └─ React HMR 热更新
  │
  └─ Electron Main Process
      ├─ 加载 http://localhost:5173
      ├─ 启动 Python Worker 子进程
      └─ 注册 IPC 处理器
```

### 3.5 项目结构

```
yolo-forge-sp/
├── electron/                      # Electron 主进程
│   ├── main.ts                    # 入口：窗口创建、初始化
│   ├── preload.ts                 # 安全IPC桥接 (contextBridge)
│   ├── store.ts                   # JSON持久化配置
│   ├── agent/                     # ★ Agent 核心系统
│   │   ├── orchestrator.ts        # Agent编排器 (ReAct循环)
│   │   ├── types.ts               # 类型定义
│   │   ├── providers/             # LLM Provider层
│   │   │   ├── openai-provider.ts  # OpenAI SDK 集成
│   │   │   └── anthropic-provider.ts # Anthropic SDK 集成
│   │   ├── tools/                 # 工具系统
│   │   │   ├── registry.ts        # 工具注册中心
│   │   │   ├── inspect-dataset.ts # 数据集检测
│   │   │   ├── convert-dataset.ts # 数据集转换
│   │   │   ├── train-model.ts     # 模型训练
│   │   │   ├── generate-report.ts # 报告生成
│   │   │   ├── read-file.ts       # 文件读取
│   │   │   ├── write-file.ts      # 文件写入
│   │   │   └── shell.ts           # Shell执行
│   │   ├── permissions/           # 权限系统
│   │   │   └── manager.ts         # 默认拒绝+拒绝追踪
│   │   ├── context/               # 上下文管理
│   │   │   └── manager.ts         # 五策略压缩
│   │   └── loop/                  # 会话管理
│   │       └── session.ts         # 多会话持久化
│   ├── ipc/
│   │   └── handlers.ts            # IPC处理器
│   ├── workers/
│   │   └── python-manager.ts      # Python子进程管理
│   └── python/
│       ├── worker.py              # ★ Python YOLO Worker
│       └── requirements.txt       # Python依赖
├── src/                           # React 渲染进程
│   ├── main.tsx                   # React入口
│   ├── App.tsx                    # 主应用
│   ├── stores/
│   │   └── app-store.ts           # Zustand 状态管理
│   ├── components/
│   │   ├── layout/                # 布局组件
│   │   ├── chat/                  # Agent聊天界面
│   │   └── panels/                # 功能面板
│   └── styles/                    # 样式文件
├── build/                         # 构建资源
├── scripts/                       # 辅助脚本
├── package.json
├── tsconfig.json
├── tsconfig.electron.json
├── vite.config.ts
└── postcss.config.js
```

---

## 4. 项目架构详解

### 4.1 进程架构

```
┌─────────────────────────────────────────────┐
│              Electron Main Process            │
│                                               │
│  ┌─────────────────────────────────────────┐ │
│  │       Agent Orchestrator (核心)          │ │
│  │  ┌─────────────────────────────────────┐ │ │
│  │  │  ReAct Loop (async generator ×7)    │ │ │
│  │  │  1. user_message    2. context      │ │ │
│  │  │  3. compaction      4. llm_call     │ │ │
│  │  │  5. text_delta      6. complete     │ │ │
│  │  │  7. tool_execution                  │ │ │
│  │  └─────────────────────────────────────┘ │ │
│  │  ┌──────────┬──────────┬───────────────┐ │ │
│  │  │ OpenAI   │Anthropic │ Context Mgr   │ │ │
│  │  │ Provider │ Provider │ (5 strategies)│ │ │
│  │  └──────────┴──────────┴───────────────┘ │ │
│  │  ┌─────────────────────────────────────┐ │ │
│  │  │  Tool Registry (9 tools)            │ │ │
│  │  │  Permission Manager (default-deny)  │ │ │
│  │  └─────────────────────────────────────┘ │ │
│  └─────────────────────────────────────────┘ │
│                                               │
│  ┌─────────────────────────────────────────┐ │
│  │  Python Worker (子进程, NDJSON IPC)      │ │
│  │  inspect | convert | train | report      │ │
│  └─────────────────────────────────────────┘ │
├─────────────────────────────────────────────┤
│           IPC Bridge (contextBridge)          │
├─────────────────────────────────────────────┤
│          Renderer Process (React)             │
│  ┌──────┬──────────────────┬──────────────┐ │
│  │ Side │   Main Panel     │  Agent Chat  │ │
│  │ bar  │ Inspector/Conv/  │  (streaming) │ │
│  │ 56px │ Trainer/Settings │  420px       │ │
│  └──────┴──────────────────┴──────────────┘ │
└─────────────────────────────────────────────┘
```

### 4.2 Agent 循环工作流

```
用户输入 → 构建提示词 → 调用LLM (流式SSE)
  ↓
LLM响应 → 解析: 文本 / 工具调用
  ↓
文本 → 流式显示给用户
  ↓
工具调用 → 权限检查 → 执行 → 结果追加 → 重新调用LLM
  ↓
无工具调用 → Agent完成 → 保存会话
```

### 4.3 数据流

```
React UI → IPC (electronAPI) → Main Process Handler
  → Agent Orchestrator → LLM Provider (OpenAI/Anthropic)
  → Tool Registry → Python Worker (YOLO操作)
  → 结果回传 → IPC → UI更新
```

### 4.4 权限决策流程

```
工具调用 → 检查用户规则 (alwaysAllow/alwaysDeny)
  → 自动模式: 低风险自动允许, 高风险询问
  → 拒绝追踪降级: 3次连续拒绝 → 始终询问
  → 需要询问 → 发送权限请求到UI → 等待用户响应
  → 允许/拒绝 → 继续/跳过工具执行
```

---

## 5. 配置指南

### 5.1 LLM Provider配置

配置文件位置: `~/.yolo-forge-sp/config.json`

#### OpenAI配置

```json
{
  "agent": {
    "provider": "openai",
    "model": "gpt-4o",
    "apiKey": "sk-...",
    "baseUrl": "https://api.openai.com/v1",
    "temperature": 0.3,
    "maxTokens": 4096
  }
}
```

支持的OpenAI模型:
- `gpt-4o` — 推荐，性能最佳
- `gpt-4o-mini` — 经济选择
- `gpt-4-turbo` — 旧版GPT-4

自定义端点（DeepSeek, 通义千问等）:
```json
{
  "agent": {
    "provider": "openai",
    "model": "deepseek-chat",
    "apiKey": "sk-...",
    "baseUrl": "https://api.deepseek.com/v1"
  }
}
```

#### Anthropic配置

```json
{
  "agent": {
    "provider": "anthropic",
    "model": "claude-sonnet-4-20250514",
    "apiKey": "sk-ant-...",
    "temperature": 0.3,
    "maxTokens": 4096
  }
}
```

支持的Anthropic模型:
- `claude-sonnet-4-20250514` — 推荐，性价比最佳
- `claude-opus-4-20250514` — 最强能力
- `claude-3-5-sonnet-20241022` — 旧版Sonnet

### 5.2 YOLO配置

```json
{
  "yolo": {
    "defaultDatasetDir": "",
    "defaultOutputDir": "./yolo_output",
    "defaultModel": "yolov8n.pt",
    "autoInspect": true
  }
}
```

### 5.3 权限配置

```json
{
  "permissions": {
    "autoMode": false,
    "rules": {
      "inspect_dataset": "allow",
      "read_file": "allow",
      "shell": "deny"
    }
  }
}
```

### 5.4 Python Worker配置

环境变量:
```bash
# 指定Python解释器路径
export YOLO_FORGE_PYTHON=/usr/bin/python3

# 或者使用conda环境
export YOLO_FORGE_PYTHON=/path/to/conda/envs/yolo/bin/python
```

---

## 6. 功能模块说明

### 6.1 数据集检测 (Inspector)

**用途**: 扫描数据集目录，检测结构和格式

**支持格式**:
- YOLO (归一化坐标 class_id cx cy w h)
- VOC (Pascal XML格式)
- COCO (instances.json格式)
- raw_px (像素坐标 class_id x1 y1 x2 y2)
- none (纯背景图片)

**使用方式**:
1. 在Inspector面板输入路径 → 点击Inspect
2. 或在Agent Chat中: "检测 /path/to/dataset 目录"

### 6.2 数据集转换 (Converter)

**用途**: 将多种格式数据集统一转换为YOLO格式

**特性**:
- YAML Profile声明式转换配置
- 支持多来源、多格式混合
- 自动类别映射和重编号
- train/val/test随机分割
- Dry-run预览模式
- 自动生成data.yaml和转换报告

**使用方式**:
1. 在Converter面板粘贴YAML Profile → 预览/执行
2. 或在Agent Chat中: "帮我将VOC格式数据集转换为YOLO格式"

### 6.3 模型训练 (Trainer)

**用途**: 配置并启动YOLO模型训练

**支持模型**: YOLOv8n/s/m/l/x
**训练后端**: Ultralytics (自动检测GPU/CPU)

**使用方式**:
1. 在Trainer面板配置参数 → 开始训练
2. 或在Agent Chat中: "用yolov8n训练我的数据集"

### 6.4 Agent聊天

**用途**: 通过自然语言与AI助手交互，自动编排工具

**工具列表** (9个):
| 工具 | 风险级别 | 只读 | 说明 |
|------|---------|------|------|
| inspect_dataset | 低 | 是 | 扫描数据集结构 |
| list_templates | 低 | 是 | 列出转换模板 |
| get_template | 低 | 是 | 获取模板内容 |
| read_file | 低 | 是 | 读取文件 |
| generate_report | 低 | 是 | 生成训练报告 |
| write_file | 中 | 否 | 写入文件 |
| train_model | 中 | 否 | 启动训练 |
| convert_dataset | 高 | 否 | 执行数据转换 |
| shell | 高 | 否 | 执行Shell命令 |

---

## 7. 生产构建与打包

### 7.1 构建流程

```bash
# 完整构建
npm run build:all

# 或分步构建
npm run build          # 构建前端 (Vite)
npm run build:electron # 构建主进程 (TypeScript → CommonJS)
```

### 7.2 打包为安装程序

```bash
# macOS (DMG + ZIP)
npm run electron:build:mac

# Linux (AppImage + DEB)
npm run electron:build:linux

# Windows (NSIS安装器 + Portable)
npm run electron:build:win

# 所有平台
npm run electron:build
```

### 7.3 输出位置

```
release/
├── YOLO-Forge SP-1.0.0-sp.dmg          # macOS
├── YOLO-Forge SP-1.0.0-sp-mac.zip       # macOS (zip)
├── YOLO-Forge SP-1.0.0-sp.AppImage      # Linux
├── yolo-forge-sp_1.0.0-sp_amd64.deb     # Linux (deb)
├── YOLO-Forge SP Setup 1.0.0-sp.exe     # Windows
└── YOLO-Forge SP 1.0.0-sp.exe           # Windows (portable)
```

### 7.4 代码签名 (macOS)

```bash
# 设置签名身份
export CSC_NAME="Developer ID Application: Your Name (TEAM_ID)"

# 构建签名版本
npm run electron:build:mac
```

### 7.5 打包注意事项

1. **Python Worker**: 打包时Python脚本会被复制到 `Resources/python/`，需要目标机器自行安装Python和依赖
2. **Ultralytics**: 首次训练时会自动下载模型权重 (~6MB-200MB)
3. **CUDA**: GPU训练需要目标机器预装CUDA/cuDNN

---

## 8. 部署方案

### 8.1 桌面应用分发

**推荐方式**: 通过GitHub Releases分发安装包

```bash
# 1. 构建
npm run electron:build

# 2. 上传 release/ 中的文件到 GitHub Release
gh release create v1.0.0-sp release/*
```

### 8.2 内网部署

```bash
# 1. 在构建机器上构建
npm run electron:build

# 2. 将安装包复制到内网文件服务器
scp release/* user@internal-server:/share/yolo-forge-sp/

# 3. 用户安装后，需要配置Python环境
pip install -r electron/python/requirements.txt
```

### 8.3 开发环境Docker化（可选）

```dockerfile
FROM node:20-slim

# 安装Python
RUN apt-get update && apt-get install -y python3 python3-pip

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

COPY electron/python/requirements.txt /app/electron/python/
RUN pip3 install -r /app/electron/python/requirements.txt

COPY . .
RUN npm run build:all

CMD ["npm", "run", "electron:dev"]
```

---

## 9. 故障排除

### 9.1 常见问题

#### Q: 启动时提示 "Python worker not available"

**A**: Python Worker启动失败，应用会降级到Mock模式。解决方法:
```bash
# 检查Python是否可用
python3 --version

# 安装依赖
pip3 install -r electron/python/requirements.txt

# 验证worker
echo '{"id":"test","command":"ping","args":{}}' | python3 electron/python/worker.py
```

#### Q: API连接测试失败

**A**: 检查以下几点:
1. API Key是否正确
2. 网络代理设置（公司网络可能需要配置代理）
3. Base URL是否正确（特别是使用第三方API时）
4. 模型名称是否正确

#### Q: 训练时GPU不可用

**A**:
```bash
# 检查CUDA
nvidia-smi

# 检查PyTorch CUDA支持
python3 -c "import torch; print(torch.cuda.is_available())"

# 重新安装CUDA版本的PyTorch
pip3 install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

#### Q: 转换后标签全部为空

**A**: 常见原因是class_mapping配置错误:
- 确保source class ID/name与class_mapping的key匹配
- 检查label格式是否正确检测（先用inspect_dataset确认）

#### Q: Electron窗口白屏

**A**:
```bash
# 开发模式检查Vite是否在运行
curl http://localhost:5173

# 生产模式检查文件是否存在
ls dist/renderer/index.html

# 检查开发者控制台错误
# 快捷键: Cmd+Option+I (macOS) / Ctrl+Shift+I (Windows/Linux)
```

### 9.2 日志位置

| 类型 | 路径 |
|------|------|
| 应用配置 | `~/.yolo-forge-sp/config.json` |
| 会话数据 | `~/.yolo-forge-sp/sessions/*.json` |
| 上下文缓存 | `~/.yolo-forge-sp/context/*.json` |
| Electron日志 | 开发者控制台 → Console |

### 9.3 重置配置

```bash
# 重置所有配置和数据
rm -rf ~/.yolo-forge-sp

# 仅重置配置
rm ~/.yolo-forge-sp/config.json
```

---

## 10. 开发者参考

### 10.1 添加新工具

1. 在 `electron/agent/tools/` 创建新工具文件:

```typescript
// electron/agent/tools/my-tool.ts
import { Tool, ToolExecutionContext } from './registry';
import { ToolDefinition } from '../types';

export class MyTool implements Tool {
  definition: ToolDefinition = {
    name: 'my_tool',
    description: 'Description of what this tool does',
    riskLevel: 'low',       // low | medium | high
    isReadOnly: true,        // true = 不会修改文件
    isDestructive: false,    // true = 可能造成数据损失
    parameters: {
      type: 'object',
      properties: {
        input: {
          type: 'string',
          description: 'Input parameter description',
        },
      },
      required: ['input'],
    },
  };

  async execute(args: any, context: ToolExecutionContext): Promise<any> {
    // 实现工具逻辑
    return { result: 'done' };
  }
}
```

2. 在 `electron/agent/tools/registry.ts` 注册:

```typescript
import { MyTool } from './my-tool';
// 在 registerBuiltinTools() 中:
this.register(new MyTool());
```

### 10.2 添加新LLM Provider

1. 在 `electron/agent/providers/` 创建新provider:

```typescript
// 实现 LLMProvider 接口
export class MyProvider implements LLMProvider {
  readonly name = 'my-provider';

  updateConfig(config: Partial<LLMProviderConfig>): void { ... }
  async chat(request: LLMChatRequest): Promise<LLMChatResponse> { ... }
  async *chatStream(request: LLMChatRequest): AsyncIterable<LLMStreamEvent> { ... }
  estimateTokens(messages: LLMPayloadMessage[]): number { ... }
}
```

2. 在 `orchestrator.ts` 注册:
```typescript
this.providers.set('my-provider', new MyProvider());
```

### 10.3 IPC通道命名规范

| 前缀 | 用途 | 示例 |
|------|------|------|
| `agent:` | Agent操作 | `agent:sendMessage` |
| `config:` | 配置管理 | `config:get` |
| `yolo:` | YOLO操作 | `yolo:inspect` |
| `fs:` | 文件系统 | `fs:openDirectory` |
| `system:` | 系统信息 | `system:getVersion` |

### 10.4 样式变量

```css
/* 颜色系统 */
--bg-primary: #0a0a0c;      /* 主背景 */
--bg-secondary: #0f0f12;    /* 次要背景 */
--text-primary: #e8e8ed;    /* 主文字 */
--accent-primary: #5E6AD2;  /* 强调色 */

/* 间距 */
--sidebar-width: 280px;     /* 侧边栏 */
--chat-width: 420px;        /* 聊天面板 */
```
