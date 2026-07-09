# YOLO-Forge SP — 从下载到运行 完整操作指南

> 📦 你需要下载的文件: `yolo-forge-sp-v1.0.0-sp.zip` (92KB 源码包)

---

## 第一步：下载解压

下载 `yolo-forge-sp-v1.0.0-sp.zip`，然后：

### macOS / Linux
```bash
# 解压到你喜欢的目录
unzip yolo-forge-sp-v1.0.0-sp.zip -d ~/Projects/
cd ~/Projects/yolo-forge-sp
```

### Windows
- 右键 zip → 解压到当前文件夹
- 打开终端进入解压后的目录

---

## 第二步：安装前置环境

### 2.1 安装 Node.js (必须)

如果你还没有 Node.js：

**方式一：官网安装（推荐新手）**
1. 访问 https://nodejs.org/
2. 下载 **20.x LTS** 版本
3. 双击安装，一路 Next

**方式二：nvm安装（推荐开发者）**
```bash
# macOS/Linux
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
source ~/.bashrc
nvm install 20
nvm use 20

# Windows: 下载 nvm-windows https://github.com/coreybutler/nvm-windows/releases
```

**验证安装：**
```bash
node --version    # 应显示 v20.x.x
npm --version     # 应显示 10.x.x
```

### 2.2 安装 Python (YOLO功能需要)

**macOS:**
```bash
brew install python@3.11
```

**Ubuntu/Debian:**
```bash
sudo apt install python3 python3-pip
```

**Windows:**
1. 访问 https://www.python.org/downloads/
2. 下载 Python 3.11+
3. 安装时**勾选 "Add Python to PATH"**

**验证安装：**
```bash
python3 --version   # 应显示 Python 3.x.x
pip3 --version      # 应显示 pip 2x.x.x
```

---

## 第三步：一键初始化

```bash
cd yolo-forge-sp

# 给脚本执行权限
chmod +x init.sh

# 运行初始化
./init.sh
```

这个脚本会自动：
1. ✅ 检查 Node.js 和 Python
2. ✅ 运行 `npm install`（安装约200个Node包，需2-5分钟）
3. ✅ 运行 `pip install -r electron/python/requirements.txt`
4. ✅ 验证 Python Worker
5. ✅ 构建前端
6. ✅ 构建主进程

---

## 第四步：如果一键脚本失败，手动操作

### 4.1 安装 Node.js 依赖
```bash
cd yolo-forge-sp
npm install
```
> 如果网络慢，使用淘宝镜像：
> ```bash
> npm install --registry=https://registry.npmmirror.com
> ```

### 4.2 安装 Python 依赖
```bash
pip3 install -r electron/python/requirements.txt
```
> 如果网络慢：
> ```bash
> pip3 install -r electron/python/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
> ```

### 4.3 验证 Python Worker
```bash
python3 -c "
import sys; sys.path.insert(0,'electron/python')
from worker import HANDLERS
print(f'OK: {len(HANDLERS)} handlers: {list(HANDLERS.keys())}')
"
```
> 应输出: `OK: 6 handlers: ['inspect', 'convert', 'train', 'report', 'stop_train', 'ping']`

### 4.4 构建前端
```bash
npx vite build
```
> 成功标志: 出现 `✓ built in Xms` 和 `dist/renderer/` 目录

### 4.5 构建主进程
```bash
npx tsc -p tsconfig.electron.json
```
> 可能有少量类型警告，不影响运行

---

## 第五步：启动应用

### 开发模式（推荐先用这个）
```bash
npm run electron:dev
```
这会：
1. 启动 Vite 开发服务器 (http://localhost:5173)
2. 启动 Electron 主进程
3. 自动打开应用窗口

### 仅前端开发（不需要 Electron）
```bash
npm run dev
```
然后浏览器打开 http://localhost:5173
> 注意：此模式下 Agent 功能不可用（需要 Electron 的 IPC）

---

## 第六步：首次使用配置

应用启动后：

1. **左侧导航栏** 点击 ⚙️ (Settings)
2. **选择 Provider**: OpenAI 或 Anthropic
3. **输入 API Key**:
   - OpenAI: `sk-...` (从 https://platform.openai.com/api-keys 获取)
   - Anthropic: `sk-ant-...` (从 https://console.anthropic.com/ 获取)
4. **点击 Test Connection** 验证
5. **点击 Save Settings** 保存

### 使用自定义API端点（DeepSeek/通义千问等）
在 Settings 中:
- Provider: 选 **OpenAI** (兼容OpenAI格式)
- Base URL: 填入端点地址
- API Key: 填入对应平台的Key

| 平台 | Base URL |
|------|----------|
| DeepSeek | https://api.deepseek.com/v1 |
| 通义千问 | https://dashscope.aliyuncs.com/compatible-mode/v1 |
| Moonshot | https://api.moonshot.cn/v1 |
| Ollama本地 | http://localhost:11434/v1 |

---

## 第七步：基本操作

### Agent Chat 使用
右侧聊天面板，直接输入自然语言：
- "检测 /path/to/dataset 目录的结构"
- "帮我把VOC格式转成YOLO格式"
- "列出可用的转换模板"
- "用yolov8n训练 /path/to/data.yaml"

### Inspector 使用
1. 左侧点 🔍 Inspector
2. 输入数据集路径
3. 点击 Inspect Dataset
4. 查看检测结果

### Converter 使用
1. 左侧点 🔄 Converter
2. 粘贴 YAML Profile（可让Agent生成）
3. 勾选 Dry Run 先预览
4. 点击 Preview Conversion → 确认无误后取消Dry Run执行

### Trainer 使用
1. 左侧点 🏋️ Trainer
2. 选择 data.yaml 路径
3. 选择模型、设置参数
4. 点击 Start Training

---

## 第八步：生产打包

当你确认开发完成后，打包成安装程序：

### macOS
```bash
npm run electron:build:mac
# 输出: release/YOLO-Forge SP-1.0.0-sp.dmg
```

### Linux
```bash
npm run electron:build:linux
# 输出: release/YOLO-Forge SP-1.0.0-sp.AppImage
```

### Windows
```bash
npm run electron:build:win
# 输出: release/YOLO-Forge SP Setup 1.0.0-sp.exe
```

---

## 常见问题

### Q: npm install 报错
```bash
# 清理缓存重试
npm cache clean --force
rm -rf node_modules package-lock.json
npm install --registry=https://registry.npmmirror.com
```

### Q: Electron下载慢
```bash
# 设置Electron镜像
export ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/
npm install
```

### Q: Python依赖安装失败(Ultralytics)
```bash
# 先安装PyTorch (CPU版)
pip3 install torch torchvision --index-url https://download.pytorch.org/whl/cpu
# 再安装其他
pip3 install ultralytics pyyaml pillow opencv-python
```

### Q: 应用启动白屏
```bash
# 检查Vite是否在运行
curl http://localhost:5173
# 如果无响应，手动启动
npm run dev
# 然后另开终端
npx electron .
```

### Q: Agent聊天报错 "API key not configured"
→ 回到 Settings 面板，确保已保存API Key

### Q: YOLO功能返回 "mock" 数据
→ Python Worker 未启动成功，检查Python安装和依赖
