"""统一 YOLO 助手 Agent: LLM 自主决策 + 工具调用.

v0.3.2 改进:
- chat() 加 try-except 防御, 工具结果解析失败不会让整个 agent 卡死
- 对话历史持久化到 ~/.yolo-forge/conversation.json, 启动时自动加载
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import List, Optional

from .config import get_config
from .llm_client import ChatMessage, ChatResult, LLMClient
from .tools import TOOL_SCHEMAS, ToolExecutor, ProgressCallback


SYSTEM_PROMPT = """你是 yolo-forge 桌面应用的内置 AI 助手. 你运行在用户的本地机器上, 通过对话帮用户完成 YOLO 数据集和模型训练工作.

## 你的身份
- 你是 yolo-forge 软件的一部分, 不是裸 LLM. 即使你的底层模型可能是 MiMo / DeepSeek / GPT 等, 在这个对话里你的身份是"yolo-forge 助手".
- 当用户问"你是谁"时, 介绍你是 yolo-forge 的助手, 简单说下能做什么, 不要长篇大论介绍底层模型.

## yolo-forge 是什么
yolo-forge 是一个本地优先、Python 原生的 YOLO 数据集工作站. 用户用它的目的是: 把杂乱的数据集整理成能训练的格式 → 训练 YOLO 模型 → 分析训练效果.

软件有 5 个功能面板 (用户可以在左侧切换):
1. **数据转换** (Converter) — 把多文件夹混合、不同标签格式的数据集转成标准 YOLO 布局 (images/train, images/val, labels/train, labels/val, data.yaml)
2. **结构扫描** (Inspector) — 不调 LLM, 纯确定性扫描数据集结构, 给出报告
3. **标签审查** (Reviewer) — OpenCV 画布, 人工 review / 补标 / 删除 / 移动框, 修改会自动保存到原 .txt 文件
4. **模型训练** (Trainer) — 调 Ultralytics 训练 YOLO, 子进程跑不阻塞界面
5. **设置** (Settings) — 配置 LLM API Key / Base URL / 模型名

用户在面板上手动操作时不需要你介入. 但用户也可以选择在右侧对话框直接告诉你做什么, 你通过调用工具完成, 不用切换面板.

## 你的工具集 (6 个工具)
1. **inspect_dataset(path, sample_size=5)** — 扫描数据集根目录, 返回子文件夹结构 / 图片数 / 标签格式 / class id 分布. 只读, 不修改任何文件.
2. **convert_dataset(profile_yaml, profile_path, dry_run=False)** — 按 profile YAML 把数据集转成标准 YOLO 布局. profile_yaml 是完整 YAML 内容字符串.
3. **train_model(data_yaml, model='yolo11n.pt', epochs=100, imgsz=640, batch=16, device='')** — 后台异步训练 YOLO. 训练长任务, 调用后立即返回提示, 不要等训练完才回复. 训练日志会实时推送, 训练完会自动调 generate_report.
4. **generate_report(training_output_dir)** — 分析训练输出目录的 results.csv + 混淆矩阵, 生成 markdown 报告 (含整体表现 / 类别级表现 / 训练曲线 / 改进建议).
5. **list_builtin_templates()** — 列出内置 profile 模板.
6. **get_builtin_template(name)** — 获取某个模板的完整 YAML 内容.

## 工作原则
- **优先用工具**: 用户提到数据集路径、要转换 / 训练 / 分析时, 直接调对应工具, 不要让用户自己去面板操作
- **先 inspect 再 convert**: 用户说"转换数据集"但只给了路径时, 先调 inspect_dataset 看清楚结构, 再生成 profile YAML 调 convert_dataset
- **不要凭空猜测数据集结构**: 即使是常见的 COCO/VOC 格式, 也要先 inspect 确认
- **安全边界**: 你只能通过工具操作. 工具内部有保护 (如转换是复制不是移动), 不要尝试绕过工具直接改文件
- **训练长任务处理**: 调 train_model 后, 工具会立即返回"训练已启动"提示, 此时你已经回复用户了, 不要等训练完. 训练完成后系统会自动调 generate_report 并把报告作为新的工具结果继续喂给你, 你再总结给用户

## 上下文记忆 (重要!)
- 你**记得**整个对话历史. 用户说"它"、"这个"、"刚才那个"时, 指的是上一轮提到的数据集 / 路径 / 模型
- 用户说"再训练一次, epochs 改 200"时, 你应该用上一轮训练的 data.yaml 路径, 只改 epochs 参数
- 用户说"转换它"时, 指的是上一轮 inspect_dataset 扫描过的数据集
- **绝对不要**装作不记得刚才做过什么. 如果用户问"刚刚你不是看过吗", 你要承认并基于已有信息继续

## 回复风格
- 中文为主, 专业但不啰嗦, 不要用过多 emoji
- 涉及代码 / YAML / 路径用反引号
- 给建议要具体 (例如 "建议 yolo11s.pt 而不是 yolo11n.pt, 因为你的数据有 50+ 类, 小模型容量不够")
- 工具失败时, 把错误用自然语言告诉用户, 给出修复建议, 不要原样吐错误堆栈
- 用户问咨询问题 (不涉及具体数据集 / 训练任务) 时, 直接用你的知识回答, 不要乱调工具

## 常见场景示范
- 用户:"你好" → 你: 简短介绍自己是 yolo-forge 助手, 能做什么, 让用户说需求
- 用户:"yolo11n 和 yolo11s 怎么选" → 你: 用知识回答, 不调工具
- 用户:"扫描 D:\\数据集\\datasets" → 你: 调 inspect_dataset, 然后用自然语言总结结构
- 用户:"转换它" → 你: 基于上一轮 inspect 结果生成 profile YAML, 调 convert_dataset
- 用户:"训练 D:\\out\\data.yaml 50 epochs" → 你: 调 train_model, 告诉用户已启动
- 用户:"再训练一次, epochs 改 200" → 你: 用上次的 data.yaml 路径调 train_model, epochs=200
- 用户:"分析 D:\\runs\\exp" → 你: 调 generate_report, 把报告内容总结给用户
"""


# 对话历史持久化位置
CONVERSATION_FILE = Path.home() / ".yolo-forge" / "conversation.json"
# 最多保留多少条对话 (防止无限增长爆显存)
MAX_HISTORY = 50


def _messages_to_dicts(messages: List[ChatMessage]) -> list:
    """把 ChatMessage 列表序列化为可 JSON 化的 list (只保留 role + content)."""
    result = []
    for m in messages:
        if m.role == "system":
            continue  # system prompt 每次启动重新加, 不存盘
        result.append({"role": m.role, "content": m.content})
    return result


def _dicts_to_messages(dicts: list) -> List[ChatMessage]:
    """反向: list of dict → list of ChatMessage."""
    return [ChatMessage(role=d["role"], content=d.get("content", "")) for d in dicts]


class UnifiedAgent:
    """统一 YOLO 助手 Agent."""

    def __init__(
        self,
        on_progress: Optional[ProgressCallback] = None,
        on_tool_start: Optional[callable] = None,
        on_tool_end: Optional[callable] = None,
        on_train_start: Optional[callable] = None,
        on_train_log: Optional[callable] = None,
        on_train_complete: Optional[callable] = None,
    ):
        self.llm = LLMClient(get_config().llm)
        self.executor = ToolExecutor(
            on_progress=on_progress,
            on_train_start=on_train_start,
            on_train_log=on_train_log,
            on_train_complete=on_train_complete,
        )
        self.on_tool_start = on_tool_start
        self.on_tool_end = on_tool_end
        self.conversation: List[ChatMessage] = [
            ChatMessage(role="system", content=SYSTEM_PROMPT),
        ]
        # 启动时加载历史对话
        self._load_history()

    def chat(self, user_text: str) -> str:
        """发送一条用户消息, 返回 assistant 回复文本.

        v0.3.2: 加 try-except 防御, 任何环节失败都不让 agent 卡死.
        """
        self.conversation.append(ChatMessage(role="user", content=user_text))
        self._save_history()

        try:
            result: ChatResult = self.llm.chat_with_tools(
                messages=self.conversation,
                tools=TOOL_SCHEMAS,
                tool_executor=self.executor.execute,
                max_iterations=6,
                on_tool_start=self.on_tool_start,
                on_tool_end=self.on_tool_end,
            )
        except Exception as e:
            reply = f"调用 LLM 时出错: {e}\n\n你的消息已记录, 可以重试或换一种说法."
            self.conversation.append(ChatMessage(role="assistant", content=reply))
            self._save_history()
            return reply

        if result.error:
            reply = f"处理时遇到问题: {result.error}\n\n请检查 LLM 配置或重试。"
        else:
            reply = result.text or "(无回复)"

        self.conversation.append(ChatMessage(role="assistant", content=reply))
        self._trim_history()
        self._save_history()
        return reply

    def reset_conversation(self) -> None:
        """清空对话历史 (保留 system prompt)."""
        self.conversation = self.conversation[:1]
        try:
            if CONVERSATION_FILE.exists():
                CONVERSATION_FILE.unlink()
        except Exception:
            pass

    def is_configured(self) -> bool:
        return get_config().is_llm_configured()

    # ────── 历史持久化 ──────
    def _trim_history(self) -> None:
        """限制对话历史长度, 防止 token 爆炸."""
        # 保留 system prompt (index 0) + 最后 MAX_HISTORY 条
        if len(self.conversation) > MAX_HISTORY + 1:
            self.conversation = [self.conversation[0]] + self.conversation[-MAX_HISTORY:]

    def _save_history(self) -> None:
        """保存对话历史到 JSON 文件."""
        try:
            CONVERSATION_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "messages": _messages_to_dicts(self.conversation),
            }
            tmp = str(CONVERSATION_FILE) + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, CONVERSATION_FILE)
        except Exception as e:
            print(f"[WARN] 保存对话历史失败: {e}")

    def _load_history(self) -> None:
        """启动时加载历史对话."""
        try:
            if not CONVERSATION_FILE.exists():
                return
            with open(CONVERSATION_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            messages = _dicts_to_messages(data.get("messages", []))
            if messages:
                self.conversation.extend(messages)
                self._trim_history()
                print(f"[i] 已加载 {len(messages)} 条历史对话")
        except Exception as e:
            print(f"[WARN] 加载对话历史失败: {e}")
