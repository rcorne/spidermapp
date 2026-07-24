from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from spidermapp.core import priorities, tasks
from spidermapp.gui import theme

_SEVERITY_COLOR = {"critical": theme.CRITICAL_HEX, "warning": theme.WARNING_HEX, "info": "#7D8590"}
_SEVERITY_IMPACT_LABEL = {"critical": "Impacto alto", "warning": "Impacto medio", "info": "Impacto bajo"}


class PriorityRow(QFrame):
    create_task_requested = Signal(object)  # priorities.Priority

    def __init__(self, priority: "priorities.Priority", parent=None):
        super().__init__(parent)
        self._priority = priority
        color = _SEVERITY_COLOR.get(priority.severity, "#7D8590")
        self.setStyleSheet(
            f"PriorityRow {{ background: #1C1F26; border: 1px solid #2D313B; border-left: 4px solid {color}; "
            f"border-radius: 6px; }}"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(10)

        site_label = QLabel(priority.site)
        site_label.setStyleSheet("font-size: 10.5px; font-weight: 700; color: #9AA1AE;")
        site_label.setFixedWidth(150)
        layout.addWidget(site_label)

        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        title = QLabel(priority.title)
        title.setTextFormat(Qt.TextFormat.PlainText)
        title.setWordWrap(True)
        title.setStyleSheet("font-size: 13px; font-weight: 700; color: #E7E9EE;")
        text_box.addWidget(title)
        if priority.fix_step:
            sub = QLabel(priority.fix_step)
            sub.setTextFormat(Qt.TextFormat.PlainText)
            sub.setWordWrap(True)
            sub.setStyleSheet("font-size: 11px; color: #9AA1AE;")
            text_box.addWidget(sub)
        layout.addLayout(text_box, stretch=1)

        impact_label = QLabel(_SEVERITY_IMPACT_LABEL.get(priority.severity, ""))
        impact_label.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {color};")
        layout.addWidget(impact_label)

        pages_word = "página" if priority.affected_pages == 1 else "páginas"
        pages_label = QLabel(f"{priority.affected_pages} {pages_word}")
        pages_label.setStyleSheet("font-size: 11px; color: #7D8590;")
        pages_label.setFixedWidth(70)
        layout.addWidget(pages_label)

        create_btn = QPushButton("+ Tarea")
        create_btn.setStyleSheet(theme.BUTTON_SECONDARY_QSS)
        create_btn.clicked.connect(lambda: self.create_task_requested.emit(self._priority))
        layout.addWidget(create_btn)


class TodayView(QWidget):
    """The entry point of the redesign: one ranked list spanning every
    audited site, instead of drilling into a site first. Reuses saved crawl
    history — no separate "sites" registry needed."""

    task_created = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        header = QWidget()
        header.setStyleSheet("background: #1C1F26; border-bottom: 1px solid #2D313B;")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(20, 16, 20, 14)
        title = QLabel("Hoy")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #E7E9EE;")
        header_layout.addWidget(title)
        self.subtitle = QLabel("Lo más urgente en todos los sitios auditados, en un solo lugar.")
        self.subtitle.setStyleSheet("font-size: 12px; color: #9AA1AE;")
        header_layout.addWidget(self.subtitle)
        outer.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll, stretch=1)

        content = QWidget()
        scroll.setWidget(content)
        self.rows_layout = QVBoxLayout(content)
        self.rows_layout.setContentsMargins(20, 16, 20, 20)
        self.rows_layout.setSpacing(8)

        self.refresh()

    def refresh(self) -> None:
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        priority_list = priorities.gather_today_priorities()
        if not priority_list:
            self.subtitle.setText("Todavía no hay auditorías guardadas. Corre un crawl para empezar a ver prioridades aquí.")
            empty = QLabel("Sin prioridades por ahora.")
            empty.setStyleSheet("color: #7D8590; font-size: 12.5px; font-style: italic;")
            self.rows_layout.addWidget(empty)
            return

        sites = sorted({p.site for p in priority_list})
        self.subtitle.setText(
            f"{len(priority_list)} hallazgos priorizados en {len(sites)} sitio{'s' if len(sites) != 1 else ''}."
        )
        for priority in priority_list:
            row = PriorityRow(priority)
            row.create_task_requested.connect(self._create_task_from_priority)
            self.rows_layout.addWidget(row)
        self.rows_layout.addStretch(1)

    def _create_task_from_priority(self, priority: "priorities.Priority") -> None:
        task_list = tasks.load_tasks()
        new_task = tasks.new_task(
            title=priority.title,
            site=priority.site,
            impact={"critical": "alto", "warning": "medio", "info": "bajo"}.get(priority.severity, "medio"),
            source_issue_code=priority.code,
        )
        if priority.why:
            tasks.add_comment([new_task], new_task.id, "Spidermapp", priority.why)
        task_list = tasks.add_task(task_list, new_task)
        tasks.save_tasks(task_list)
        self.task_created.emit()
