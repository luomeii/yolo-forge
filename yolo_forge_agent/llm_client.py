"""LLM 客户端: OpenAI 兼容 API 调用封装, 支持 function calling.

v0.3.0 重大升级:
- 支持 function calling (OpenAI / DeepSeek / 智谱 / Ollama 都兼容)
- chat_with_tools() 实现"LLM 自主决策 → 调工具 → 结果回喂 → LLM 继续"循环
- 工具调用可靠: 严格 schema + 失败回退到 LLM 自行回答
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .config import LLMConfig, get_config


# ─────────────────────────────────────────────────────────────
@dataclass
class ChatMessage:
    """简化的 chat message 结构, 支持工具调用."""

    role: str  # "system" | "user" | "assistant" | "tool"
    content: str = ""
    tool_calls: List[dict] = field(default_factory=list)  # assistant 发起的工具调用
    tool_call_id: Optional[str] = None  # role=tool 时关联的调用 ID
    name: Optional[str] = None  # role=tool 时工具名

    def to_dict(self) -> dict:
        d: dict = {"role": self.role}
        if self.content:
            d["content"] = self.content
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.name:
            d["name"] = self.name
        # OpenAI API 要求: assistant 消息即使有 tool_calls, content 也得是 null 或字符串
        if self.role == "assistant" and self.tool_calls and "content" not in d:
            d["content"] = None
        return d


# ─────────────────────────────────────────────────────────────
@dataclass
class ToolCall:
    """LLM 决定调用的工具."""
    id: str          # OpenAI 返回的 call ID, 用于回填结果
    name: str        # 工具名
    arguments: dict  # 解析后的参数


# ─────────────────────────────────────────────────────────────
@dataclass
class ChatResult:
    """chat_with_tools 的返回."""
    text: str = ""                           # 最终文本回复
    tool_calls_made: List[dict] = field(default_factory=list)  # 执行过的工具调用历史
    error: str = ""


# ─────────────────────────────────────────────────────────────
class LLMClient:
    """OpenAI 兼容 LLM 客户端, 支持工具调用."""

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or get_config().llm
        self._client = None

    def _ensure_client(self):
        if self._client is not None:
            return
        if not self.config.api_key:
            raise RuntimeError(
                "LLM API key 未配置. 请在「设置」面板填入, 或编辑 ~/.yolo-forge/config.yaml"
            )
        try:
            from openai import OpenAI
        except ImportError as e:
            raise RuntimeError(
                "openai 包未安装. 请运行: pip install 'yolo-forge[agent]'"
            ) from e

        self._client = OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            timeout=self.config.timeout,
        )

    # ────────── 简单 chat (无工具) ──────────
    def chat(
        self,
        messages: List[ChatMessage],
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """简单 chat, 返回纯文本."""
        self._ensure_client()
        kwargs = dict(
            model=self.config.model,
            messages=[m.to_dict() for m in messages],
            temperature=temperature if temperature is not None else self.config.temperature,
            max_tokens=max_tokens or self.config.max_tokens,
        )
        resp = self._client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""

    def chat_with_retry(self, messages: List[ChatMessage], retries: int = 2) -> str:
        last_err = None
        for i in range(retries + 1):
            try:
                return self.chat(messages)
            except Exception as e:
                last_err = e
                if i < retries:
                    import time
                    time.sleep(1.5 * (i + 1))
        raise last_err  # type: ignore

    # ────────── chat with tools (function calling) ──────────
    def chat_with_tools(
        self,
        messages: List[ChatMessage],
        tools: List[dict],
        tool_executor: Callable[[str, dict], str],
        *,
        max_iterations: int = 5,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        on_tool_start: Optional[Callable[[str, dict], None]] = None,
        on_tool_end: Optional[Callable[[str, str], None]] = None,
    ) -> ChatResult:
        """带工具调用的 chat, 实现 ReAct 循环.

        流程:
        1. 把 messages + tools 发给 LLM
        2. LLM 返回: 要么是文本回复, 要么是 tool_calls
        3. 如果是 tool_calls → 执行工具 → 把结果作为 tool message 喂回 LLM
        4. 重复直到 LLM 给出最终文本回复, 或达到 max_iterations

        Parameters
        ----------
        messages : List[ChatMessage]
            对话历史
        tools : List[dict]
            工具定义 (OpenAI function calling schema 格式)
        tool_executor : callable(tool_name, arguments) -> str
            工具执行器, 返回工具执行结果文本
        max_iterations : int
            最多循环次数 (防止 LLM 反复调工具)
        on_tool_start / on_tool_end : callable, optional
            回调, 用于 UI 显示工具调用过程
        """
        self._ensure_client()

        result = ChatResult()
        # 复制一份 messages, 避免修改原列表
        msg_dicts = [m.to_dict() for m in messages]

        for iteration in range(max_iterations):
            try:
                resp = self._client.chat.completions.create(
                    model=self.config.model,
                    messages=msg_dicts,
                    tools=tools,
                    tool_choice="auto",
                    temperature=temperature if temperature is not None else self.config.temperature,
                    max_tokens=max_tokens or self.config.max_tokens,
                )
            except Exception as e:
                result.error = f"LLM 调用失败: {e}"
                return result

            choice = resp.choices[0]
            message = choice.message
            msg_dict = message.model_dump()
            msg_dicts.append(msg_dict)

            # 没有 tool_calls → LLM 给出了最终文本回复
            if not message.tool_calls:
                result.text = message.content or ""
                return result

            # 有 tool_calls → 逐个执行
            # 注意: on_tool_start 在这里调用一次即可, 不要在 tool_executor 内部再调
            for tc in message.tool_calls:
                tool_name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                except json.JSONDecodeError as e:
                    args = {}
                    args_error = f"参数解析失败: {e}"
                    if on_tool_end:
                        on_tool_end(tool_name, f"[x] {args_error}")
                    msg_dicts.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tool_name,
                        "content": f"错误: {args_error}",
                    })
                    continue

                if on_tool_start:
                    on_tool_start(tool_name, args)

                try:
                    # tool_executor 只负责执行, 不再做进度回调 (避免重复)
                    tool_result = tool_executor(tool_name, args)
                except Exception as e:
                    tool_result = f"[x] 工具执行失败: {e}"

                if on_tool_end:
                    on_tool_end(tool_name, tool_result[:500])

                result.tool_calls_made.append({
                    "name": tool_name,
                    "arguments": args,
                    "result": tool_result[:1000],
                })

                # 工具结果作为 tool message 喂回
                msg_dicts.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tool_name,
                    "content": tool_result,
                })

        # 超过 max_iterations, 强制让 LLM 总结
        try:
            msg_dicts.append({
                "role": "user",
                "content": "工具调用次数已达上限，请基于已有信息直接回答。",
            })
            resp = self._client.chat.completions.create(
                model=self.config.model,
                messages=msg_dicts,
                temperature=temperature if temperature is not None else self.config.temperature,
                max_tokens=max_tokens or self.config.max_tokens,
            )
            result.text = resp.choices[0].message.content or ""
        except Exception as e:
            result.error = f"最终总结失败: {e}"
            result.text = "工具调用次数过多，请尝试更明确的指令。"

        return result


# ─────────────────────────────────────────────────────────────
def make_client() -> LLMClient:
    return LLMClient()
