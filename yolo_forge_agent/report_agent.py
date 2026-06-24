"""训练报告 Agent: 读 Ultralytics 训练产物 → 生成 markdown 分析报告.

输入: 训练输出目录 (含 results.csv / confusion_matrix.png 等)
输出: 自然语言报告 (markdown), 包含:
- 整体表现 (mAP / precision / recall)
- 类别级表现 (哪类召回低)
- 训练曲线观察 (loss 是否收敛 / 过拟合)
- 改进建议 (补数据 / 调超参 / 换模型规模)
"""
from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Optional

from .base import AgentResult, AgentStatus, BaseAgent


SYSTEM_PROMPT = """You are a YOLO training analyst. Given training metrics (CSV rows)
and dataset info, write a concise Chinese markdown report.

The report MUST include:
1. **总体表现** — overall mAP50, mAP50-95, precision, recall
2. **类别级表现** — per-class performance (if available), highlight weak classes
3. **训练曲线观察** — whether loss converged, signs of overfitting
4. **改进建议** — 3-5 concrete actionable suggestions (collect more data, augment, adjust hyperparams, etc.)

Style: 直接给结论, 不要客套话. 用中文. Markdown 格式.
"""


class ReportAgent(BaseAgent):
    """训练报告 Agent."""

    name = "report_agent"
    description = "Analyze YOLO training results and write a markdown report."

    def run(self, training_output_dir: str) -> AgentResult:
        """生成训练报告.

        Parameters
        ----------
        training_output_dir : str
            Ultralytics 训练输出目录 (含 results.csv 等)

        Returns
        -------
        AgentResult
            status=SUCCESS, data={"report": str, "metrics": dict}
        """
        self._progress("scan", f"扫描训练目录: {training_output_dir}")
        out_dir = Path(training_output_dir)
        if not out_dir.is_dir():
            return AgentResult(
                status=AgentStatus.FAILED,
                error=f"训练目录不存在: {training_output_dir}",
            )

        # 读 results.csv
        results_csv = out_dir / "results.csv"
        if not results_csv.exists():
            return AgentResult(
                status=AgentStatus.FAILED,
                error=f"未找到 results.csv (期望位置: {results_csv})",
            )

        self._progress("parse", "解析 results.csv...")
        metrics = self._parse_results_csv(results_csv)
        if not metrics:
            return AgentResult(
                status=AgentStatus.FAILED,
                error="results.csv 解析失败或为空",
            )

        # 检查可用产物
        artifacts = self._list_artifacts(out_dir)
        metrics["artifacts"] = artifacts

        # 调 LLM
        self._progress("llm", f"调用 LLM 生成报告 (model={self.llm.config.model})...")
        user_msg = self._build_user_message(metrics, out_dir)
        try:
            from .llm_client import ChatMessage
            report = self.llm.chat_with_retry([
                ChatMessage("system", SYSTEM_PROMPT),
                ChatMessage("user", user_msg),
            ], retries=1)
        except Exception as e:
            # fallback: 直接给原始指标, 不写分析
            self._progress("fallback", f"LLM 失败 ({e}), 用确定性 fallback 生成简报")
            report = self._fallback_report(metrics, str(e))
            status = AgentStatus.FALLBACK
        else:
            status = AgentStatus.SUCCESS

        return AgentResult(
            status=status,
            content=report,
            data={"report": report, "metrics": metrics},
        )

    # ────────── 内部 ──────────
    def _parse_results_csv(self, csv_path: Path) -> dict:
        """解析 Ultralytics results.csv."""
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        if not rows:
            return {}

        # 字段名 ultralytics 通常带空格, strip 一下
        rows = [{k.strip(): v for k, v in row.items()} for row in rows]
        last = rows[-1]
        first = rows[0]
        n = len(rows)

        # 提取关键指标 (字段名兼容多种 ultralytics 版本)
        def _get(row, *keys):
            for k in keys:
                if k in row and row[k] not in (None, ""):
                    try:
                        return float(row[k])
                    except ValueError:
                        continue
            return None

        metrics = {
            "epochs_completed": n,
            "first_epoch": _get(first, "epoch"),
            "last_epoch": _get(last, "epoch"),
            "final_box_loss": _get(last, "train/box_loss", "box_loss"),
            "final_cls_loss": _get(last, "train/cls_loss", "cls_loss"),
            "final_dfl_loss": _get(last, "train/dfl_loss", "dfl_loss"),
            "final_precision": _get(last, "metrics/precision(B)", "precision"),
            "final_recall": _get(last, "metrics/recall(B)", "recall"),
            "final_map50": _get(last, "metrics/mAP50(B)", "mAP50"),
            "final_map50_95": _get(last, "metrics/mAP50-95(B)", "mAP50-95"),
            "val_box_loss": _get(last, "val/box_loss"),
            "val_cls_loss": _get(last, "val/cls_loss"),
        }

        # 抓 loss 曲线趋势 (前 5 / 后 5 平均)
        def _avg(rows_subset, *keys):
            vals = []
            for r in rows_subset:
                v = _get(r, *keys)
                if v is not None:
                    vals.append(v)
            return sum(vals) / len(vals) if vals else None

        early = rows[:min(5, n)]
        late = rows[-min(5, n):]
        metrics["box_loss_early_avg"] = _avg(early, "train/box_loss", "box_loss")
        metrics["box_loss_late_avg"] = _avg(late, "train/box_loss", "box_loss")
        return metrics

    def _list_artifacts(self, out_dir: Path) -> dict:
        """检查训练目录里有哪些产物文件."""
        result = {}
        for name in ["results.csv", "confusion_matrix.png", "confusion_matrix_normalized.png",
                     "PR_curve.png", "F1_curve.png", "labels.jpg", "labels_correlogram.jpg"]:
            p = out_dir / name
            result[name] = str(p) if p.exists() else ""
        # 权重
        weights_dir = out_dir / "weights"
        result["best_pt"] = str(weights_dir / "best.pt") if (weights_dir / "best.pt").exists() else ""
        result["last_pt"] = str(weights_dir / "last.pt") if (weights_dir / "last.pt").exists() else ""
        return result

    def _build_user_message(self, metrics: dict, out_dir: Path) -> str:
        parts = [
            f"训练目录: {out_dir}",
            f"完成的 epoch 数: {metrics.get('epochs_completed', '?')}",
            "",
            "关键指标 (最后一个 epoch):",
        ]
        for k in ["final_box_loss", "final_cls_loss", "final_dfl_loss",
                  "final_precision", "final_recall", "final_map50", "final_map50_95",
                  "val_box_loss", "val_cls_loss"]:
            v = metrics.get(k)
            if v is not None:
                parts.append(f"  {k}: {v:.4f}")

        if metrics.get("box_loss_early_avg") is not None and metrics.get("box_loss_late_avg") is not None:
            parts.append("")
            parts.append(f"box_loss 早期均值: {metrics['box_loss_early_avg']:.4f}")
            parts.append(f"box_loss 末期均值: {metrics['box_loss_late_avg']:.4f}")

        parts.append("")
        parts.append("产物文件:")
        arts = metrics.get("artifacts", {})
        for name, path in arts.items():
            parts.append(f"  {name}: {'存在' if path else '缺失'}")

        parts.append("")
        parts.append("请基于以上信息写中文 markdown 报告.")
        return "\n".join(parts)

    def _fallback_report(self, metrics: dict, error: str) -> str:
        """LLM 失败时生成简报."""
        lines = ["# YOLO 训练报告 (自动生成 - LLM 不可用)", ""]
        lines.append(f"> LLM 调用失败: {error}")
        lines.append(f"> 以下为原始指标, 请人工分析.")
        lines.append("")
        lines.append("## 关键指标")
        lines.append("")
        lines.append(f"- 完成 epoch 数: {metrics.get('epochs_completed', '?')}")
        for k in ["final_precision", "final_recall", "final_map50", "final_map50_95"]:
            v = metrics.get(k)
            if v is not None:
                lines.append(f"- {k}: {v:.4f}")
        lines.append("")
        lines.append("## Loss 趋势")
        lines.append("")
        for k in ["final_box_loss", "final_cls_loss", "final_dfl_loss",
                  "val_box_loss", "val_cls_loss"]:
            v = metrics.get(k)
            if v is not None:
                lines.append(f"- {k}: {v:.4f}")
        return "\n".join(lines)
