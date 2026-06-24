"""多会话存储: 支持多个独立对话, 像 ChatGPT 一样可切换."""
from __future__ import annotations
import json, os, time, uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional

CONVERSATIONS_DIR = Path.home() / ".yolo-forge" / "conversations"
INDEX_FILE = CONVERSATIONS_DIR / "index.json"
MAX_MESSAGES = 100

@dataclass
class ConversationMeta:
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0

@dataclass
class Message:
    role: str
    content: str
    timestamp: str = ""
    tool_name: str = ""

def _now(): return time.strftime("%Y-%m-%d %H:%M:%S")
def _new_id(): return uuid.uuid4().hex[:8] + "_" + time.strftime("%m%d%H%M")

class ConversationStore:
    def __init__(self):
        self.conversations: List[ConversationMeta] = []
        CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)
        self._load_index()

    def _load_index(self):
        if not INDEX_FILE.exists(): return
        try:
            with open(INDEX_FILE, "r", encoding="utf-8") as f:
                self.conversations = [ConversationMeta(**d) for d in json.load(f)]
        except: self.conversations = []

    def _save_index(self):
        try:
            tmp = str(INDEX_FILE) + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump([asdict(c) for c in self.conversations], f, ensure_ascii=False, indent=2)
            os.replace(tmp, INDEX_FILE)
        except: pass

    def list_conversations(self):
        return sorted(self.conversations, key=lambda c: c.updated_at, reverse=True)

    def create_conversation(self, title="新对话"):
        meta = ConversationMeta(id=_new_id(), title=title, created_at=_now(), updated_at=_now())
        self.conversations.append(meta)
        self._save_index()
        self._save_messages(meta.id, [])
        return meta

    def delete_conversation(self, conv_id):
        self.conversations = [c for c in self.conversations if c.id != conv_id]
        fp = CONVERSATIONS_DIR / f"{conv_id}.json"
        if fp.exists():
            try: fp.unlink()
            except: pass
        self._save_index()

    def rename_conversation(self, conv_id, title):
        for c in self.conversations:
            if c.id == conv_id:
                c.title = title; c.updated_at = _now(); break
        self._save_index()

    def _msg_file(self, conv_id): return CONVERSATIONS_DIR / f"{conv_id}.json"

    def _save_messages(self, conv_id, messages):
        try:
            tmp = str(self._msg_file(conv_id)) + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"conv_id": conv_id, "messages": [asdict(m) for m in messages]}, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self._msg_file(conv_id))
        except: pass

    def load_messages(self, conv_id):
        fp = self._msg_file(conv_id)
        if not fp.exists(): return []
        try:
            with open(fp, "r", encoding="utf-8") as f:
                return [Message(**m) for m in json.load(f).get("messages", [])]
        except: return []

    def append_message(self, conv_id, role, content, tool_name=""):
        msg = Message(role=role, content=content, timestamp=_now(), tool_name=tool_name)
        messages = self.load_messages(conv_id)
        messages.append(msg)
        if len(messages) > MAX_MESSAGES:
            messages = messages[-MAX_MESSAGES:]
        self._save_messages(conv_id, messages)
        for c in self.conversations:
            if c.id == conv_id:
                c.message_count = len(messages)
                c.updated_at = _now()
                if c.title == "新对话":
                    for m in messages:
                        if m.role == "user":
                            c.title = m.content[:30] + ("..." if len(m.content) > 30 else "")
                            break
                break
        self._save_index()
        return msg

    def get_meta(self, conv_id):
        for c in self.conversations:
            if c.id == conv_id: return c
        return None

_store = None

def get_store():
    global _store
    if _store is None:
        _store = ConversationStore()
    return _store

def reset_store():
    global _store
    _store = ConversationStore()
    return _store
