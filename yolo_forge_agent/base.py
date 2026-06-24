"""Agent 基类: 所有 agent 共享的通用逻辑.

设计:
- 每个具体 agent 子类化 BaseAgent, 实现 run() 方法
- BaseAgent 提供: 配置读取、LLM 客户端、日志回调
- agent 输出统一是 AgentResult (status + content + data)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from .config import AppConfig, get_config
from .llm_client import LLMClient


class AgentStatus(str, Enum):
    SUCCESS = "success"
    NEEDS_CONFIRMATION = "needs_confirmation"   # 需要用户确认 (比如 profile 草稿)
    FAILED = "failed"
    FALLBACK = "fallback"                       # LLM 失败但用确定性 fallback 完成了


@dataclass
class AgentResult:
    """Agent 执行结果."""
    status: AgentStatus
    content: str = ""                            # 自然语言总结 (给用户看的)
    data: dict = field(default_factory=dict)    # 结构化输出 (给程序用的)
    error: str = ""                              # 失败时的错误信息

    @property
    def ok(self) -> bool:
        return self.status in (AgentStatus.SUCCESS, AgentStatus.NEEDS_CONFIRMATION, AgentStatus.FALLBACK)


# 类型: 进度回调, 接收 (step_name, detail) 二元组
ProgressCallback = Callable[[str, str], None]


class BaseAgent:
    """所有 agent 的基."""

    name: str = "base"
    description: str = ""

    def __init__(
        self,
        config: Optional[AppConfig] = None,
        llm_client: Optional[LLMClient] = None,
        on_progress: Optional[ProgressCallback] = None,
    ):
        self.config = config or get_config()
        self.llm = llm_client or LLMClient(self.config.llm)
        self.on_progress = on_progress or (lambda step, detail: None)

    def _progress(self, step: str, detail: str = "") -> None:
        self.on_progress(step, detail)

    def run(self, *args, **kwargs) -> AgentResult:
        """子类实现具体逻辑."""
        raise NotImplementedError
