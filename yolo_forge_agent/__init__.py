"""yolo_forge_agent — LLM Agent 模块.

依赖 OpenAI 兼容 API. v0.2 先实现:
- 配置管理 (config.yaml 读写)
- LLM 客户端封装
- 结构探查 Agent
- 训练报告 Agent

设计原则:
- Agent 只生成配置和报告, 绝不直接修改数据
- 所有 LLM 调用走 OpenAI 兼容格式 (兼容 DeepSeek / 智谱 / OpenAI / Ollama)
- 失败时优雅降级到确定性 fallback, 不让用户卡死
"""
from __future__ import annotations

__version__ = "0.2.0"
__all__ = ["__version__"]
