from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Local task board: the Kanban/checklist layer over audit findings. No
# backend exists for this app (it's a local desktop tool), so "collaborators"
# and "comments" are local records tied to whoever is signed in on this
# machine (see core/auth.py) — not synced across machines. That's an honest
# limitation, not an oversight: real multi-user sync would need a server.

TASKS_PATH = Path.home() / ".spidermapp" / "tasks.json"

STATUSES = ["Por hacer", "En progreso", "Revisión cliente", "Hecho"]
DEFAULT_STATUS = STATUSES[0]
IMPACTS = ["alto", "medio", "bajo"]


def _new_id() -> str:
    return uuid.uuid4().hex[:10]


@dataclass
class ChecklistItem:
    text: str
    done: bool = False


@dataclass
class Comment:
    author: str
    text: str
    created_at: float = field(default_factory=time.time)


@dataclass
class Task:
    id: str = field(default_factory=_new_id)
    title: str = ""
    site: str = ""
    status: str = DEFAULT_STATUS
    impact: str = "medio"
    labels: list[str] = field(default_factory=list)
    assignee: str = ""
    checklist: list[ChecklistItem] = field(default_factory=list)
    comments: list[Comment] = field(default_factory=list)
    source_issue_code: str = ""  # links back to an audit finding, when created from one
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


def new_task(
    title: str,
    site: str = "",
    impact: str = "medio",
    labels: list[str] | None = None,
    source_issue_code: str = "",
) -> Task:
    if impact not in IMPACTS:
        impact = "medio"
    return Task(title=title, site=site, impact=impact, labels=list(labels or []), source_issue_code=source_issue_code)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def _task_to_dict(task: Task) -> dict:
    d = asdict(task)
    return d


def _task_from_dict(data: dict) -> Task:
    checklist = [ChecklistItem(**c) for c in data.get("checklist", [])]
    comments = [Comment(**c) for c in data.get("comments", [])]
    return Task(
        id=data.get("id", _new_id()),
        title=data.get("title", ""),
        site=data.get("site", ""),
        status=data.get("status", DEFAULT_STATUS),
        impact=data.get("impact", "medio"),
        labels=list(data.get("labels", [])),
        assignee=data.get("assignee", ""),
        checklist=checklist,
        comments=comments,
        source_issue_code=data.get("source_issue_code", ""),
        created_at=data.get("created_at", time.time()),
        updated_at=data.get("updated_at", time.time()),
    )


def load_tasks(path: Path = TASKS_PATH) -> list[Task]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    return [_task_from_dict(t) for t in data.get("tasks", [])]


def save_tasks(tasks: list[Task], path: Path = TASKS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"tasks": [_task_to_dict(t) for t in tasks]}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Mutations — pure functions over a list[Task], caller persists the result.
# Mirrors the immutable-list style already used by core/history.py's diffing.
# ---------------------------------------------------------------------------


def find_task(tasks: list[Task], task_id: str) -> Task | None:
    return next((t for t in tasks if t.id == task_id), None)


def add_task(tasks: list[Task], task: Task) -> list[Task]:
    return [*tasks, task]


def delete_task(tasks: list[Task], task_id: str) -> list[Task]:
    return [t for t in tasks if t.id != task_id]


def set_status(tasks: list[Task], task_id: str, status: str) -> list[Task]:
    if status not in STATUSES:
        raise ValueError(f"Estado inválido: {status}")
    task = find_task(tasks, task_id)
    if task is None:
        return tasks
    task.status = status
    task.updated_at = time.time()
    return tasks


def add_comment(tasks: list[Task], task_id: str, author: str, text: str) -> list[Task]:
    task = find_task(tasks, task_id)
    if task is None or not text.strip():
        return tasks
    task.comments.append(Comment(author=author or "Anónimo", text=text.strip()))
    task.updated_at = time.time()
    return tasks


def add_checklist_item(tasks: list[Task], task_id: str, text: str) -> list[Task]:
    task = find_task(tasks, task_id)
    if task is None or not text.strip():
        return tasks
    task.checklist.append(ChecklistItem(text=text.strip()))
    task.updated_at = time.time()
    return tasks


def toggle_checklist_item(tasks: list[Task], task_id: str, index: int) -> list[Task]:
    task = find_task(tasks, task_id)
    if task is None or not (0 <= index < len(task.checklist)):
        return tasks
    task.checklist[index].done = not task.checklist[index].done
    task.updated_at = time.time()
    return tasks


def tasks_by_status(tasks: list[Task]) -> dict[str, list[Task]]:
    buckets: dict[str, list[Task]] = {status: [] for status in STATUSES}
    for task in tasks:
        buckets.setdefault(task.status, []).append(task)
    return buckets
