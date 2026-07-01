"""In-memory background task registry for progress tracking."""
from datetime import datetime
from typing import Optional

_tasks: dict[str, dict] = {}


def start_task(task_id: str, name: str, total: int = 0) -> dict:
    _tasks[task_id] = {
        "id": task_id,
        "name": name,
        "status": "running",
        "total": total,
        "done": 0,
        "message": "",
        "started_at": datetime.utcnow().isoformat(),
        "finished_at": None,
    }
    return _tasks[task_id]


def update_task(task_id: str, done: Optional[int] = None, message: Optional[str] = None, total: Optional[int] = None):
    t = _tasks.get(task_id)
    if not t:
        return
    if done is not None:
        t["done"] = done
    if message is not None:
        t["message"] = message
    if total is not None:
        t["total"] = total


def finish_task(task_id: str, status: str = "success", message: str = ""):
    t = _tasks.get(task_id)
    if not t:
        return
    t["status"] = status
    t["message"] = message
    t["finished_at"] = datetime.utcnow().isoformat()


def get_tasks() -> list[dict]:
    return list(reversed(list(_tasks.values())))


def clear_old_tasks():
    now = datetime.utcnow()
    to_remove = [
        k for k, v in _tasks.items()
        if v["finished_at"] and (now - datetime.fromisoformat(v["finished_at"])).total_seconds() > 3600
    ]
    for k in to_remove:
        del _tasks[k]
