"""后台 Agent worker 线程."""
from __future__ import annotations
from PySide6.QtCore import QThread, Signal


class _AgentWorker(QThread):
    tool_start_sig = Signal(str, str)
    tool_end_sig = Signal(str, str)
    train_log_sig = Signal(str)
    train_complete_sig = Signal(str, str)
    finished_reply_sig = Signal(str, str)
    failed_sig = Signal(str)
    permission_request_sig = Signal(str, str)

    def __init__(self, user_text: str, agent):
        super().__init__()
        self.user_text = user_text
        self.agent = agent
        self._sig_tool_start = self.tool_start_sig
        self._sig_tool_end = self.tool_end_sig
        self._sig_train_log = self.train_log_sig
        self._sig_train_complete = self.train_complete_sig
        self._sig_permission = self.permission_request_sig
        self._permission_result = None

    def run(self) -> None:
        self.agent.on_tool_start = lambda name, args: self._emit_tool_start(name, args)
        self.agent.on_tool_end = lambda name, result: self._emit_tool_end(name, result)

        from yolo_forge_agent import tools as _tools
        _tools._permission_callback = self._permission_via_signal
        _tools._on_train_log = lambda line: self._sig_train_log.emit(line)
        _tools._on_train_complete = lambda bp, td: self._sig_train_complete.emit(bp, td)

        try:
            reply = self.agent.chat(self.user_text)
            conv_id = getattr(self.agent, 'conv_id', '')
            self.finished_reply_sig.emit(reply, conv_id)
        except Exception as e:
            import traceback
            print(f"[ERROR] Agent worker failed: {e}\n{traceback.format_exc()}")
            self.failed_sig.emit(f"{e}")

    def _emit_tool_start(self, name, args):
        key_params = ["path", "command", "data_yaml", "model", "epochs", "name", "profile_path"]
        display_args = []
        for k, v in args.items():
            if k in key_params:
                v_str = str(v)
                if len(v_str) > 40:
                    v_str = v_str[:40] + "..."
                display_args.append(f"{k}={v_str}")
        args_str = ", ".join(display_args) if display_args else ""
        if len(args_str) > 80:
            args_str = args_str[:80] + "..."
        self._sig_tool_start.emit(name, args_str)

    def _emit_tool_end(self, name, result):
        first_line = result.split("\n")[0] if result else ""
        preview = first_line[:80] + ("..." if len(first_line) > 80 else "")
        self._sig_tool_end.emit(name, preview)

    def _permission_via_signal(self, tool_name, args):
        import json, time
        safe_tools = {"inspect_dataset", "convert_dataset", "train_model",
                      "generate_report", "read_file", "list_dir",
                      "list_builtin_templates", "get_builtin_template", "detect_cuda_env"}
        if tool_name in safe_tools:
            return True
        self._permission_result = None
        args_str = json.dumps(args, ensure_ascii=False, default=str)[:500]
        self._sig_permission.emit(tool_name, args_str)
        for _ in range(600):
            if self._permission_result is not None:
                break
            time.sleep(0.1)
        return self._permission_result if self._permission_result is not None else False

    def set_permission_result(self, approved: bool):
        self._permission_result = approved
