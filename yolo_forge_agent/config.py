"""Agent 模块配置: 单文件 ~/.yolo-forge/config.yaml.

存储内容:
- LLM API 配置 (api_key, base_url, model)
- 默认数据集路径
- 主题设置等

按用户要求: "配置存储就一个单独配置文件, 不然太麻烦"
所以全部塞一个 YAML, API key 也是明文存, 换取可调试性.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import yaml


# 配置文件位置
CONFIG_DIR = Path.home() / ".yolo-forge"
CONFIG_FILE = CONFIG_DIR / "config.yaml"


@dataclass
class LLMConfig:
    """LLM API 配置."""

    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    temperature: float = 0.3
    max_tokens: int = 4096
    timeout: float = 60.0


@dataclass
class AppConfig:
    """yolo-forge 应用全局配置."""

    llm: LLMConfig = field(default_factory=LLMConfig)
    default_dataset_dir: str = ""
    default_output_dir: str = "./yolo_output"
    theme: str = "dark_ide"
    last_opened_panel: str = "converter"

    # ────────── 序列化 ──────────
    def to_dict(self) -> dict:
        return asdict(self)

    def to_yaml(self) -> str:
        return yaml.safe_dump(self.to_dict(), allow_unicode=True, sort_keys=False, default_flow_style=False)

    # ────────── 持久化 ──────────
    def save(self, path: Optional[Path] = None) -> Path:
        """保存配置到 YAML. 默认存 ~/.yolo-forge/config.yaml."""
        path = path or CONFIG_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_yaml())
        # 限制权限 (仅当前用户可读写), 保护 api_key
        try:
            os.chmod(path, 0o600)
        except Exception:
            pass  # Windows 上 chmod 不完全生效, 忽略
        return path

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "AppConfig":
        """从 YAML 加载配置. 文件不存在则返回默认值."""
        path = path or CONFIG_FILE
        if not path.exists():
            return cls()
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception:
            return cls()

        # 兼容嵌套 llm 字段
        llm_data = data.get("llm", {}) or {}
        llm = LLMConfig(
            api_key=llm_data.get("api_key", ""),
            base_url=llm_data.get("base_url", "https://api.openai.com/v1"),
            model=llm_data.get("model", "gpt-4o-mini"),
            temperature=float(llm_data.get("temperature", 0.3)),
            max_tokens=int(llm_data.get("max_tokens", 4096)),
            timeout=float(llm_data.get("timeout", 60.0)),
        )
        return cls(
            llm=llm,
            default_dataset_dir=data.get("default_dataset_dir", ""),
            default_output_dir=data.get("default_output_dir", "./yolo_output"),
            theme=data.get("theme", "dark_ide"),
            last_opened_panel=data.get("last_opened_panel", "converter"),
        )

    # ────────── 校验 ──────────
    def is_llm_configured(self) -> bool:
        """LLM 是否已配置可用."""
        return bool(self.llm.api_key and self.llm.base_url and self.llm.model)


# ─────────────────────────────────────────────────────────────
#  全局单例 (延迟加载)
# ─────────────────────────────────────────────────────────────
_cached_config: Optional[AppConfig] = None


def get_config(reload: bool = False) -> AppConfig:
    """获取全局配置. 第一次调用时从磁盘加载, 之后缓存."""
    global _cached_config
    if _cached_config is None or reload:
        _cached_config = AppConfig.load()
    return _cached_config


def save_config(config: AppConfig) -> Path:
    """保存配置并刷新缓存."""
    global _cached_config
    _cached_config = config
    return config.save()


def reset_config() -> AppConfig:
    """重置为默认配置."""
    global _cached_config
    _cached_config = AppConfig()
    _cached_config.save()
    return _cached_config
