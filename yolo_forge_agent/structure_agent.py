"""结构探查 Agent: 把任意目录结构 → YOLO 可训练的 profile YAML.

工作流:
1. 用 core.inspector 确定性扫描目录, 得到结构化报告
2. 把报告喂给 LLM, 让它推断 class_mappings / background 策略等
3. LLM 输出一个 profile YAML 草稿
4. 返回 NEEDS_CONFIRMATION, 等用户在 GUI 里确认/修改
5. 用户确认后, 调 core.converter 引擎执行转换

安全边界: Agent 只生成配置, 不直接修改数据.
"""
from __future__ import annotations

import re
from typing import Optional

import yaml

from yolo_forge_core.inspector import InspectionReport, inspect_dataset
from yolo_forge_core.converter.profiles import DatasetProfile

from .base import AgentResult, AgentStatus, BaseAgent


SYSTEM_PROMPT = """You are a YOLO dataset structure expert. You analyze dataset folder structures
and produce a YAML "profile" that the yolo-forge converter engine can execute.

You ALWAYS output a single YAML document inside a ```yaml fenced block. No prose outside the block.
The YAML MUST follow this schema:

name: <string>            # dataset name
description: <string>
output_dir: ./yolo_output
classes: [<class_name_0>, <class_name_1>, ...]   # target class names, order = class_id
train_split: 0.8
val_split: 0.2
test_split: 0.0
seed: 42
copy_strategy: copy
flatten: true
sources:
  - name: <string>
    path: <absolute_path>
    images_subdir: images        # or "" if images are directly under path
    labels_subdir: labels        # or "" if no labels
    label_format: yolo           # yolo | voc | coco | raw_px | none
    label_ext: .txt
    class_mappings:
      - {source_id: 0, target_id: 0}
    background: include          # include | skip | copy_no_label | dedicated_folder

Rules:
- For folders with NO labels (background-only), set label_format: none and background: include.
- For folders that look like noise/irrelevant, set background: skip.
- target_id in class_mappings MUST be a valid index into the classes list.
- source_id is the class id used in the source labels (0-based).
- If a source has no class_mappings info, use [] (engine defaults to source_id == target_id).
- Preserve the user's intended class semantics. If folder A's id=0 is "pit" and folder B's id=0
  is also "pit", both should map to target_id of "pit".
"""


class StructureAgent(BaseAgent):
    """结构探查 Agent."""

    name = "structure_agent"
    description = "Scan a dataset folder and generate a YOLO converter profile YAML."

    def run(self, dataset_path: str, *, user_hint: str = "") -> AgentResult:
        """执行探查.

        Parameters
        ----------
        dataset_path : str
            数据集根目录路径
        user_hint : str
            用户的额外说明, 例如 "id=0 是 pit, id=1 是 scratch"

        Returns
        -------
        AgentResult
            status=NEEDS_CONFIRMATION, data={"profile_yaml": str, "profile_dict": dict}
        """
        self._progress("scan", f"扫描目录: {dataset_path}")
        try:
            report = inspect_dataset(dataset_path)
        except Exception as e:
            return AgentResult(
                status=AgentStatus.FAILED,
                error=f"扫描失败: {e}",
            )

        if not report.folders:
            return AgentResult(
                status=AgentStatus.FAILED,
                error="目录下没有任何子文件夹, 也无图片",
            )

        self._progress("llm", f"调用 LLM 推断 profile (model={self.llm.config.model})...")

        # 构造 LLM 输入
        user_msg = self._build_user_message(report, user_hint)
        try:
            from .llm_client import ChatMessage
            reply = self.llm.chat_with_retry([
                ChatMessage("system", SYSTEM_PROMPT),
                ChatMessage("user", user_msg),
            ], retries=1)
        except Exception as e:
            # LLM 失败时降级到确定性 fallback
            self._progress("fallback", f"LLM 调用失败 ({e}), 用确定性 fallback 生成 profile")
            return self._fallback_profile(report, str(e))

        self._progress("parse", "解析 LLM 输出的 YAML...")
        yaml_text = self._extract_yaml(reply)
        if not yaml_text:
            return AgentResult(
                status=AgentStatus.FAILED,
                error=f"LLM 回复中未找到 YAML 块. 原文: {reply[:500]}",
            )

        try:
            profile_dict = yaml.safe_load(yaml_text)
        except yaml.YAMLError as e:
            return AgentResult(
                status=AgentStatus.FAILED,
                error=f"LLM 生成的 YAML 解析失败: {e}\n原文:\n{yaml_text[:500]}",
            )

        return AgentResult(
            status=AgentStatus.NEEDS_CONFIRMATION,
            content=f"已扫描 {len(report.folders)} 个子文件夹, 生成 profile 草稿. 请检查后确认执行.",
            data={
                "profile_yaml": yaml_text,
                "profile_dict": profile_dict,
                "inspection_report": report.to_llm_prompt(),
            },
        )

    # ────────── 内部 ──────────
    def _build_user_message(self, report: InspectionReport, user_hint: str) -> str:
        parts = [report.to_llm_prompt()]
        if user_hint:
            parts.append("")
            parts.append("User hint:")
            parts.append(user_hint)
        parts.append("")
        parts.append("Now produce the profile YAML. Output ONLY the yaml fenced block.")
        return "\n".join(parts)

    def _extract_yaml(self, text: str) -> str:
        """从 LLM 回复中提取 ```yaml ... ``` 块."""
        m = re.search(r"```(?:yaml|yml)?\s*\n(.*?)```", text, re.DOTALL)
        if m:
            return m.group(1).strip()
        # 没找到代码块, 看看整段是不是合法 yaml
        if text.strip().startswith("name:"):
            return text.strip()
        return ""

    def _fallback_profile(self, report: InspectionReport, error: str) -> AgentResult:
        """LLM 失败时的确定性 fallback: 生成一个最朴素的 profile."""
        sources = []
        for f in report.folders:
            sources.append({
                "name": f.name,
                "path": f.path,
                "images_subdir": "images" if f.has_images_subdir else "",
                "labels_subdir": "labels" if f.has_labels_subdir else "",
                "label_format": f.sample_label_format if f.sample_label_format != "unknown" else "none",
                "label_ext": ".txt",
                "class_mappings": [],   # 默认 source_id == target_id
                "background": "include",
            })

        # 推断类别数: 取所有源 class_id 最大值 + 1
        max_id = 0
        for f in report.folders:
            for cid in f.sample_label_classes.keys():
                max_id = max(max_id, cid)
        classes = [f"class_{i}" for i in range(max_id + 1)]

        profile_dict = {
            "name": "fallback_profile",
            "description": f"Auto-generated fallback profile (LLM failed: {error[:80]})",
            "output_dir": "./yolo_output",
            "classes": classes,
            "train_split": 0.8,
            "val_split": 0.2,
            "test_split": 0.0,
            "seed": 42,
            "copy_strategy": "copy",
            "flatten": True,
            "sources": sources,
        }
        yaml_text = yaml.safe_dump(profile_dict, allow_unicode=True, sort_keys=False, default_flow_style=False)

        return AgentResult(
            status=AgentStatus.FALLBACK,
            content=(
                f"LLM 调用失败, 已用确定性 fallback 生成 profile. 建议人工检查 class_mappings 是否正确.\n"
                f"错误: {error}"
            ),
            data={
                "profile_yaml": yaml_text,
                "profile_dict": profile_dict,
                "inspection_report": report.to_llm_prompt(),
            },
        )
