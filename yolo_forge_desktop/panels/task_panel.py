"""任务管理 Panel: 集中查看 / 控制 训练 / 转换 / 扫描 / 审查 等后台任务.

设计:
- TaskInfo: 单个任务的状态数据 (id / name / 类型 / 状态 / 进度 / 日志 / 等)
- TaskManager: 单例, 全局维护任务字典 (供其他 panel 注册任务)
- TaskPanel: GUI, 显示 QListWidget + 日志, 2 秒刷新一次
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QGroupBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QSplitter, QTextEdit, QVBoxLayout,
)

from .base import BasePanel


# ────────────────── 数据结构 ──────────────────

@dataclass
class TaskInfo:
    """单个后台任务的运行时信息."""

    task_id: str
    name: str
    task_type: str = "task"            # train | convert | inspect | review | custom
    status: str = "pending"            # pending | running | completed | failed | stopped
    progress: float = 0.0              # 0.0 - 1.0
    start_time: str = ""
    end_time: str = ""
    output_dir: str = ""
    logs: list = field(default_factory=list)
    error: str = ""
    best_pt: str = ""
    trainer: Optional[object] = None   # 持有 Trainer / Worker 实例, 用于 stop


# ────────────────── 单例管理器 ──────────────────

class TaskManager:
    """全局任务管理 (单例).

    使用方式:
        tm = TaskManager()
        task = tm.add_task(name="train-exp1", task_type="train", output_dir="./runs/exp1")
        task.trainer = self._worker          # 后面要能 stop
        task.logs.append("[*] starting...")
        tm.update_task(task.task_id, status="running", progress=0.1)
    """

    _instance: Optional["TaskManager"] = None

    def __new__(cls) -> "TaskManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tasks = {}
        return cls._instance

    # ── CRUD ──
    def add_task(
        self,
        name: str,
        task_type: str = "task",
        output_dir: str = "",
        trainer: Optional[object] = None,
    ) -> TaskInfo:
        """创建并注册一个新任务, 返回 TaskInfo 供调用方继续填充."""
        task = TaskInfo(
            task_id=uuid.uuid4().hex[:8],
            name=name,
            task_type=task_type,
            output_dir=output_dir,
            start_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            trainer=trainer,
        )
        self._tasks[task.task_id] = task
        return task

    def update_task(self, task_id: str, **fields) -> None:
        t = self._tasks.get(task_id)
        if t is None:
            return
        for k, v in fields.items():
            if hasattr(t, k):
                setattr(t, k, v)
        # 终态自动写入 end_time
        if fields.get("status") in ("completed", "failed", "stopped") and not t.end_time:
            t.end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def append_log(self, task_id: str, line: str) -> None:
        t = self._tasks.get(task_id)
        if t is None:
            return
        t.logs.append(line)
        # 防止无限增长 (只保留最近 2000 行)
        if len(t.logs) > 2000:
            t.logs = t.logs[-2000:]

    def remove_task(self, task_id: str) -> None:
        self._tasks.pop(task_id, None)

    def get_task(self, task_id: str) -> Optional[TaskInfo]:
        return self._tasks.get(task_id)

    def list_tasks(self) -> list:
        # 按 start_time 倒序 (最新在前)
        return sorted(
            self._tasks.values(),
            key=lambda t: t.start_time or "",
            reverse=True,
        )

    def clear_finished(self) -> int:
        """删除所有非 running/pending 的任务, 返回删除数."""
        done = [tid for tid, t in self._tasks.items()
                if t.status not in ("pending", "running")]
        for tid in done:
            self._tasks.pop(tid, None)
        return len(done)

    def stop_task(self, task_id: str) -> bool:
        """停止一个运行中的任务. 返回是否成功调用 stop."""
        t = self._tasks.get(task_id)
        if t is None or t.status not in ("pending", "running"):
            return False
        try:
            if t.trainer is not None and hasattr(t.trainer, "stop"):
                t.trainer.stop()
            t.status = "stopped"
            t.end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            t.logs.append("[!] 用户已停止任务")
            return True
        except Exception as e:
            t.error = f"停止失败: {e}"
            return False


# ────────────────── GUI Panel ──────────────────

class TaskPanel(BasePanel):
    """任务管理 Panel."""

    panel_id = "tasks"
    panel_name = "任务管理"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tm = TaskManager()
        self._current_id: Optional[str] = None
        self._build_ui()

        # 每 2 秒刷新一次任务列表 + 当前任务日志
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(2000)

    # ────────── UI ──────────
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(14)

        title = QLabel("任务管理")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        subtitle = QLabel("集中查看与控制所有训练 / 转换 / 扫描 / 审查后台任务的运行状态")
        subtitle.setObjectName("SectionSubtitle")
        layout.addWidget(subtitle)

        hint = QLabel(
            "<b>说明:</b> 各功能面板启动任务时会自动注册到这里, "
            "可在此集中查看进度 / 停止任务 / 浏览日志。"
        )
        hint.setObjectName("PanelHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # ── 工具按钮行 ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.stop_btn = QPushButton("停止选中任务")
        self.stop_btn.setObjectName("DangerButton")
        self.stop_btn.setFixedWidth(130)
        self.stop_btn.setToolTip("强制停止当前选中的运行中任务")
        self.stop_btn.clicked.connect(self._on_stop)
        btn_row.addWidget(self.stop_btn)

        self.clear_btn = QPushButton("清理已完成")
        self.clear_btn.setFixedWidth(130)
        self.clear_btn.setToolTip("从列表中移除所有已完成 / 失败 / 已停止的任务")
        self.clear_btn.clicked.connect(self._on_clear)
        btn_row.addWidget(self.clear_btn)

        btn_row.addStretch()

        self.refresh_btn = QPushButton("立即刷新")
        self.refresh_btn.setFixedWidth(100)
        self.refresh_btn.clicked.connect(self._refresh)
        btn_row.addWidget(self.refresh_btn)

        layout.addLayout(btn_row)

        # ── 任务列表 + 日志 ──
        splitter = QSplitter(Qt.Vertical)
        splitter.setChildrenCollapsible(False)

        list_group = QGroupBox("任务列表")
        ll = QVBoxLayout(list_group)
        self.task_list = QListWidget()
        self.task_list.setMinimumHeight(160)
        self.task_list.itemSelectionChanged.connect(self._on_select)
        ll.addWidget(self.task_list)
        splitter.addWidget(list_group)

        log_group = QGroupBox("任务日志")
        lgl = QVBoxLayout(log_group)
        self.log_view = QTextEdit()
        self.log_view.setObjectName("LogView")
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("选中上方任务后, 这里显示其运行日志 ...")
        lgl.addWidget(self.log_view)
        splitter.addWidget(log_group)

        splitter.setSizes([260, 280])
        layout.addWidget(splitter, 1)

    # ────────── 事件 ──────────
    def _on_select(self) -> None:
        items = self.task_list.selectedItems()
        if not items:
            return
        tid = items[0].data(Qt.UserRole)
        self._current_id = tid
        self._show_log(tid)

    def _on_stop(self) -> None:
        if not self._current_id:
            QMessageBox.information(self, "未选中", "请先在列表中选中一个任务")
            return
        t = self._tm.get_task(self._current_id)
        if t is None:
            return
        if t.status not in ("pending", "running"):
            QMessageBox.information(self, "不可停止", f"任务状态为 {t.status}, 无法停止")
            return
        reply = QMessageBox.question(
            self, "确认停止",
            f"确定要停止任务 [{t.name}] 吗?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        ok = self._tm.stop_task(self._current_id)
        if ok:
            self.status_message.emit(f"已停止任务: {t.name}")
        else:
            QMessageBox.warning(self, "停止失败", f"停止任务失败:\n{t.error}")
        self._refresh()

    def _on_clear(self) -> None:
        n = self._tm.clear_finished()
        if n == 0:
            self.status_message.emit("没有可清理的已完成任务")
        else:
            self.status_message.emit(f"已清理 {n} 个已完成任务")
        self._current_id = None
        self.log_view.clear()
        self._refresh()

    # ────────── 刷新 ──────────
    def _refresh(self) -> None:
        """刷新任务列表 + 当前选中任务的日志."""
        tasks = self._tm.list_tasks()

        # 记录当前选中 id (可能因刷新被清掉, 重新选中)
        prev_selected = self._current_id

        self.task_list.blockSignals(True)
        self.task_list.clear()
        for t in tasks:
            label = self._format_task_label(t)
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, t.task_id)
            # 运行中任务用亮色, 其他用灰色
            item.setForeground(
                Qt.GlobalColor.white if t.status == "running"
                else Qt.GlobalColor.lightGray
            )
            # 用 tooltip 显示详细信息
            item.setToolTip(
                f"ID: {t.task_id}\n"
                f"名称: {t.name}\n"
                f"类型: {t.task_type}\n"
                f"状态: {t.status}\n"
                f"进度: {t.progress*100:.1f}%\n"
                f"开始: {t.start_time}\n"
                f"结束: {t.end_time or '(运行中)'}\n"
                f"输出: {t.output_dir or '(无)'}\n"
                f"best.pt: {t.best_pt or '(无)'}\n"
                f"错误: {t.error or '(无)'}"
            )
            self.task_list.addItem(item)
        self.task_list.blockSignals(False)

        # 重新选中之前选中的 (如果还存在)
        if prev_selected:
            for i in range(self.task_list.count()):
                if self.task_list.item(i).data(Qt.UserRole) == prev_selected:
                    self.task_list.setCurrentRow(i)
                    break
            else:
                # 之前选中的不在列表里了, 清空
                self._current_id = None
                self.log_view.clear()
        else:
            # 没有选中, 清空日志
            self.log_view.clear()

        # 刷新日志 (只在选中任务时)
        if self._current_id:
            self._show_log(self._current_id)

    def _format_task_label(self, t: TaskInfo) -> str:
        status_emoji = {
            "running":   "▶",
            "pending":   "○",
            "completed": "✓",
            "failed":    "✗",
            "stopped":   "■",
        }.get(t.status, "·")
        pct = f"{t.progress*100:.0f}%" if t.progress > 0 else "--"
        return f"[{status_emoji}] {t.name}  ({t.task_type})  {t.status}  {pct}"

    def _show_log(self, task_id: str) -> None:
        t = self._tm.get_task(task_id)
        if t is None:
            self.log_view.clear()
            return
        if not t.logs:
            self.log_view.setPlainText("(暂无日志)")
            return
        # 仅追加最近 500 行, 避免卡顿
        tail = t.logs[-500:]
        self.log_view.setPlainText("\n".join(tail))
        # 滚到底部
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ────────── 生命周期 ──────────
    def on_activated(self) -> None:
        """切到本面板时立即刷新一次, 并确保 timer 在跑."""
        if not self._timer.isActive():
            self._timer.start(2000)
        self._refresh()

    def on_deactivated(self) -> None:
        """切走时不必停 timer (任务仍在后台跑), 但保留状态."""
        # 保留 timer 运行, 这样切回来时数据是最新的
        pass
