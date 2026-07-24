from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from spidermapp.core import auth, tasks
from spidermapp.gui import theme

_IMPACT_COLOR = {"alto": theme.CRITICAL_HEX, "medio": theme.WARNING_HEX, "bajo": "#7D8590"}
_LABEL_PALETTE = {
    "Técnico": ("#3A2226", theme.CRITICAL_HEX),
    "Contenido": ("#3A331C", theme.WARNING_HEX),
    "Urgente": ("#3A2226", theme.CRITICAL_HEX),
    "Enlaces": ("#262A33", "#9AA1AE"),
    "Mantención": ("#1F3A2E", theme.GOOD_HEX),
}
_DEFAULT_LABEL_COLOR = (theme.PRIMARY_SOFT, theme.PRIMARY_HOVER)


def _label_chip(text: str) -> QLabel:
    bg, fg = _LABEL_PALETTE.get(text, _DEFAULT_LABEL_COLOR)
    chip = QLabel(text)
    chip.setStyleSheet(f"background: {bg}; color: {fg}; font-size: 10px; font-weight: 700; padding: 2px 7px; border-radius: 4px;")
    return chip


def _current_display_name() -> str:
    session = auth.load_session()
    if session:
        profile = session.get("profile", {})
        return profile.get("name") or profile.get("email") or "Yo"
    return "Yo"


class TaskDetailDialog(QDialog):
    changed = Signal()

    def __init__(self, task: tasks.Task, parent=None):
        super().__init__(parent)
        self._task = task
        self.setWindowTitle(task.title or "Tarea")
        self.resize(440, 560)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 14)
        outer.setSpacing(10)

        site_row = QHBoxLayout()
        site_label = QLabel(task.site or "Sin sitio")
        site_label.setStyleSheet("font-size: 11px; font-weight: 700; color: #9AA1AE;")
        site_row.addWidget(site_label)
        site_row.addStretch(1)
        labels_row = QHBoxLayout()
        for label in task.labels:
            labels_row.addWidget(_label_chip(label))
        labels_row.addStretch(1)
        outer.addLayout(site_row)
        outer.addLayout(labels_row)

        title = QLabel(task.title)
        title.setWordWrap(True)
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #E7E9EE;")
        outer.addWidget(title)

        status_row = QHBoxLayout()
        status_row.addWidget(QLabel("Estado:"))
        self.status_combo = QComboBox()
        self.status_combo.addItems(tasks.STATUSES)
        self.status_combo.setCurrentText(task.status)
        self.status_combo.currentTextChanged.connect(self._on_status_changed)
        status_row.addWidget(self.status_combo, stretch=1)
        outer.addLayout(status_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll, stretch=1)
        content = QWidget()
        scroll.setWidget(content)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 8, 0, 0)
        content_layout.setSpacing(6)

        checklist_header = QLabel("SUB-TAREAS")
        checklist_header.setStyleSheet("font-size: 10.5px; font-weight: 700; color: #7D8590; letter-spacing: 0.04em;")
        content_layout.addWidget(checklist_header)
        self.checklist_layout = QVBoxLayout()
        self.checklist_layout.setSpacing(4)
        content_layout.addLayout(self.checklist_layout)
        self._render_checklist()

        add_check_row = QHBoxLayout()
        self.new_check_input = QLineEdit()
        self.new_check_input.setPlaceholderText("Agregar sub-tarea…")
        self.new_check_input.returnPressed.connect(self._add_checklist_item)
        add_check_row.addWidget(self.new_check_input, stretch=1)
        add_check_btn = QPushButton("+")
        add_check_btn.clicked.connect(self._add_checklist_item)
        add_check_row.addWidget(add_check_btn)
        content_layout.addLayout(add_check_row)

        comments_header = QLabel("COMENTARIOS")
        comments_header.setStyleSheet("font-size: 10.5px; font-weight: 700; color: #7D8590; letter-spacing: 0.04em; margin-top: 10px;")
        content_layout.addWidget(comments_header)
        self.comments_layout = QVBoxLayout()
        self.comments_layout.setSpacing(8)
        content_layout.addLayout(self.comments_layout)
        self._render_comments()
        content_layout.addStretch(1)

        comment_row = QHBoxLayout()
        self.new_comment_input = QLineEdit()
        self.new_comment_input.setPlaceholderText("Escribe un comentario…")
        self.new_comment_input.returnPressed.connect(self._add_comment)
        comment_row.addWidget(self.new_comment_input, stretch=1)
        send_btn = QPushButton("Enviar")
        send_btn.setStyleSheet(theme.BUTTON_PRIMARY_QSS)
        send_btn.clicked.connect(self._add_comment)
        comment_row.addWidget(send_btn)
        outer.addLayout(comment_row)

    def _persist(self) -> None:
        task_list = tasks.load_tasks()
        # Replace the stored copy of this task with our in-memory edits —
        # load_tasks() returns fresh Task objects, not the same instance.
        task_list = [self._task if t.id == self._task.id else t for t in task_list]
        if not any(t.id == self._task.id for t in task_list):
            task_list.append(self._task)
        tasks.save_tasks(task_list)
        self.changed.emit()

    def _on_status_changed(self, status: str) -> None:
        self._task.status = status
        self._persist()

    def _render_checklist(self) -> None:
        while self.checklist_layout.count():
            item = self.checklist_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for index, entry in enumerate(self._task.checklist):
            checkbox = QCheckBox(entry.text)
            checkbox.setChecked(entry.done)
            checkbox.setStyleSheet("font-size: 12.5px;")
            checkbox.stateChanged.connect(lambda _state, i=index: self._toggle_checklist(i))
            self.checklist_layout.addWidget(checkbox)

    def _toggle_checklist(self, index: int) -> None:
        tasks.toggle_checklist_item([self._task], self._task.id, index)
        self._persist()
        self._render_checklist()

    def _add_checklist_item(self) -> None:
        text = self.new_check_input.text().strip()
        if not text:
            return
        tasks.add_checklist_item([self._task], self._task.id, text)
        self.new_check_input.clear()
        self._persist()
        self._render_checklist()

    def _render_comments(self) -> None:
        while self.comments_layout.count():
            item = self.comments_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not self._task.comments:
            empty = QLabel("Sin comentarios todavía.")
            empty.setStyleSheet("font-size: 11.5px; color: #7D8590; font-style: italic;")
            self.comments_layout.addWidget(empty)
            return
        for comment in self._task.comments:
            when = datetime.fromtimestamp(comment.created_at).strftime("%d/%m %H:%M")
            box = QLabel(f"<b>{comment.author}</b> <span style='color:#7D8590;font-size:10px;'>{when}</span><br>{comment.text}")
            box.setTextFormat(Qt.TextFormat.RichText)
            box.setWordWrap(True)
            box.setStyleSheet("font-size: 12px; color: #C3C7D1;")
            self.comments_layout.addWidget(box)

    def _add_comment(self) -> None:
        text = self.new_comment_input.text().strip()
        if not text:
            return
        tasks.add_comment([self._task], self._task.id, _current_display_name(), text)
        self.new_comment_input.clear()
        self._persist()
        self._render_comments()


class TaskCard(QFrame):
    clicked = Signal(object)  # tasks.Task

    def __init__(self, task: tasks.Task, parent=None):
        super().__init__(parent)
        self._task = task
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            "TaskCard { background: #1C1F26; border: 1px solid #2D313B; border-radius: 8px; } "
            "TaskCard:hover { border-color: " + theme.PRIMARY + "; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(11, 10, 11, 10)
        layout.setSpacing(7)

        if task.labels:
            labels_row = QHBoxLayout()
            labels_row.setSpacing(4)
            for label in task.labels:
                labels_row.addWidget(_label_chip(label))
            labels_row.addStretch(1)
            layout.addLayout(labels_row)

        title = QLabel(task.title)
        title.setWordWrap(True)
        title.setStyleSheet("font-size: 12.5px; font-weight: 600; color: #E7E9EE;")
        layout.addWidget(title)

        foot = QHBoxLayout()
        site_label = QLabel(task.site or "—")
        site_label.setStyleSheet(f"font-size: 10px; font-weight: 700; color: {_IMPACT_COLOR.get(task.impact, '#7D8590')};")
        foot.addWidget(site_label)
        foot.addStretch(1)
        if task.comments:
            comment_label = QLabel(f"💬 {len(task.comments)}")
            comment_label.setStyleSheet("font-size: 10.5px; color: #7D8590;")
            foot.addWidget(comment_label)
        if task.assignee:
            av = QLabel(task.assignee[:2].upper())
            av.setFixedSize(18, 18)
            av.setAlignment(Qt.AlignmentFlag.AlignCenter)
            av.setStyleSheet(f"background: {theme.PRIMARY}; color: white; font-size: 8.5px; font-weight: 700; border-radius: 9px;")
            foot.addWidget(av)
        layout.addLayout(foot)

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt override
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._task)
        super().mousePressEvent(event)


class BoardColumn(QWidget):
    def __init__(self, status: str, parent=None):
        super().__init__(parent)
        self.status = status
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.header = QLabel(status)
        self.header.setStyleSheet("font-size: 12.5px; font-weight: 700; color: #C3C7D1;")
        layout.addWidget(self.header)

        self.cards_layout = QVBoxLayout()
        self.cards_layout.setSpacing(8)
        layout.addLayout(self.cards_layout)
        layout.addStretch(1)

    def set_tasks(self, task_list: list[tasks.Task], on_click) -> None:
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.header.setText(f"{self.status}  ({len(task_list)})")
        for task in task_list:
            card = TaskCard(task)
            card.clicked.connect(on_click)
            self.cards_layout.addWidget(card)


class BoardView(QWidget):
    """Tablero estilo Trello: cada tarea puede venir de un hallazgo de
    auditoría (creada desde "Hoy") o agregarse manualmente, con checklist y
    comentarios locales para coordinación interna."""

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        header = QWidget()
        header.setStyleSheet("background: #1C1F26; border-bottom: 1px solid #2D313B;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 14, 20, 14)
        title = QLabel("Tablero")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #E7E9EE;")
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        add_btn = QPushButton("+ Tarea")
        add_btn.setStyleSheet(theme.BUTTON_PRIMARY_QSS)
        add_btn.clicked.connect(self._add_blank_task)
        header_layout.addWidget(add_btn)
        outer.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll, stretch=1)

        content = QWidget()
        scroll.setWidget(content)
        columns_layout = QHBoxLayout(content)
        columns_layout.setContentsMargins(20, 16, 20, 20)
        columns_layout.setSpacing(16)

        self.columns: dict[str, BoardColumn] = {}
        for status in tasks.STATUSES:
            column = BoardColumn(status)
            column.setMinimumWidth(240)
            column.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            columns_layout.addWidget(column)
            self.columns[status] = column

        self.refresh()

    def refresh(self) -> None:
        buckets = tasks.tasks_by_status(tasks.load_tasks())
        for status, column in self.columns.items():
            column.set_tasks(buckets.get(status, []), self._open_task)

    def _open_task(self, task: tasks.Task) -> None:
        dialog = TaskDetailDialog(task, self)
        dialog.changed.connect(self.refresh)
        dialog.exec()
        self.refresh()

    def _add_blank_task(self) -> None:
        task_list = tasks.load_tasks()
        new_task = tasks.new_task(title="Nueva tarea")
        task_list = tasks.add_task(task_list, new_task)
        tasks.save_tasks(task_list)
        self.refresh()
        self._open_task(new_task)
