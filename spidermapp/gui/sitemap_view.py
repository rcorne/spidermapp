from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from spidermapp.core.models import IssueSeverity, PageResult
from spidermapp.gui import theme
from spidermapp.gui.table_model import _max_severity

MAX_RENDERED_NODES = 400
RING_GAP = 58
ORPHAN_RING_EXTRA = 70
NODE_MIN_R = 5.0
NODE_MAX_R = 13.0

_SEVERITY_COLOR = {
    IssueSeverity.CRITICAL: QColor(theme.CRITICAL_HEX),
    IssueSeverity.WARNING: QColor(theme.WARNING_HEX),
    IssueSeverity.INFO: QColor(theme.INFO_HEX),
}
_GOOD_COLOR = theme.GOOD_COLOR
_EDGE_COLOR = QColor(180, 184, 196, 140)


@dataclass
class _NodePos:
    page: PageResult
    x: float = 0.0
    y: float = 0.0
    radius: float = NODE_MIN_R
    parent_url: str | None = None
    orphan: bool = False


def _node_color(page: PageResult) -> QColor:
    severity = _max_severity(page)
    if severity is None:
        return _GOOD_COLOR
    return _SEVERITY_COLOR[severity]


def _node_radius(page: PageResult) -> float:
    inlink_count = len(page.inlinks)
    return min(NODE_MAX_R, NODE_MIN_R + inlink_count * 1.1)


class SiteMapCanvas(QWidget):
    node_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._nodes: dict[str, _NodePos] = {}
        self._truncated = False
        self.setMinimumSize(600, 600)

    def set_pages(self, pages: list[PageResult], seed_url: str) -> None:
        self._nodes = {}
        self._truncated = len(pages) > MAX_RENDERED_NODES
        subset = pages[:MAX_RENDERED_NODES]

        by_url = {p.url: p for p in subset}
        non_orphans = [p for p in subset if not p.is_orphan]
        orphans = [p for p in subset if p.is_orphan]

        children: dict[str, list[PageResult]] = defaultdict(list)
        roots: list[PageResult] = []
        for page in non_orphans:
            if page.depth == 0:
                roots.append(page)
                continue
            parent_url = None
            for inlink in page.inlinks:
                candidate = by_url.get(inlink)
                if candidate is not None and candidate.depth == page.depth - 1:
                    parent_url = inlink
                    break
            if parent_url is None and page.inlinks:
                parent_url = page.inlinks[0]
            if parent_url is None or parent_url not in by_url:
                roots.append(page)
            else:
                children[parent_url].append(page)

        max_depth = max((p.depth for p in non_orphans), default=0)

        def place(node: PageResult, angle_start: float, angle_end: float) -> None:
            radius = RING_GAP * node.depth
            mid_angle = (angle_start + angle_end) / 2
            rad = math.radians(mid_angle)
            self._nodes[node.url] = _NodePos(
                page=node,
                x=radius * math.cos(rad),
                y=radius * math.sin(rad),
                radius=_node_radius(node),
                parent_url=None,
            )
            kids = children.get(node.url, [])
            if not kids:
                return
            span = angle_end - angle_start
            step = span / len(kids)
            for i, kid in enumerate(kids):
                place(kid, angle_start + i * step, angle_start + (i + 1) * step)
                self._nodes[kid.url].parent_url = node.url

        if roots:
            span = 360.0 / len(roots)
            for i, root in enumerate(roots):
                place(root, i * span, (i + 1) * span)

        if orphans:
            orphan_radius = RING_GAP * max_depth + ORPHAN_RING_EXTRA
            step = 360.0 / len(orphans)
            for i, orphan in enumerate(orphans):
                rad = math.radians(i * step)
                self._nodes[orphan.url] = _NodePos(
                    page=orphan,
                    x=orphan_radius * math.cos(rad),
                    y=orphan_radius * math.sin(rad),
                    radius=_node_radius(orphan),
                    orphan=True,
                )

        self._recompute_bounds(max_depth, bool(orphans))
        self.update()

    def _recompute_bounds(self, max_depth: int, has_orphans: bool) -> None:
        max_radius = RING_GAP * max_depth + (ORPHAN_RING_EXTRA + 30 if has_orphans else 30)
        side = max(600, int(max_radius * 2 + 80))
        self.setMinimumSize(side, side)
        self.resize(side, side)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = QPointF(self.width() / 2, self.height() / 2)

        if not self._nodes:
            painter.setPen(QColor("#9CA3AF"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Sin datos para mostrar todavía.")
            return

        # background web guides
        max_r = max((math.hypot(n.x, n.y) for n in self._nodes.values()), default=0)
        guide_pen = QPen(QColor(230, 232, 238), 1)
        painter.setPen(guide_pen)
        ring = RING_GAP
        while ring <= max_r + RING_GAP:
            painter.drawEllipse(center, ring, ring)
            ring += RING_GAP

        # edges
        edge_pen = QPen(_EDGE_COLOR, 1.2)
        painter.setPen(edge_pen)
        for node in self._nodes.values():
            if node.orphan or node.parent_url is None:
                continue
            parent = self._nodes.get(node.parent_url)
            if parent is None:
                continue
            painter.drawLine(center + QPointF(parent.x, parent.y), center + QPointF(node.x, node.y))

        # nodes
        font = QFont(self.font())
        font.setPointSize(9)
        painter.setFont(font)
        for node in self._nodes.values():
            pos = center + QPointF(node.x, node.y)
            color = _node_color(node.page)
            if node.orphan:
                painter.setBrush(QColor(255, 255, 255))
                pen = QPen(color, 1.6, Qt.PenStyle.DashLine)
                painter.setPen(pen)
            else:
                painter.setBrush(color)
                painter.setPen(QPen(QColor("white"), 1.4))
            painter.drawEllipse(pos, node.radius, node.radius)

        seed_node = next((n for n in self._nodes.values() if n.page.depth == 0 and not n.orphan), None)
        if seed_node is not None:
            painter.setPen(QColor("#111827"))
            label_pos = center + QPointF(seed_node.x, seed_node.y - seed_node.radius - 8)
            painter.drawText(QRectF(label_pos.x() - 60, label_pos.y() - 14, 120, 14), Qt.AlignmentFlag.AlignCenter, "Inicio")

        if self._truncated:
            painter.setPen(QColor("#9CA3AF"))
            painter.drawText(10, self.height() - 10, f"Mostrando los primeros {MAX_RENDERED_NODES} nodos.")

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        center = QPointF(self.width() / 2, self.height() / 2)
        click = event.position() if hasattr(event, "position") else event.localPos()
        for node in self._nodes.values():
            pos = center + QPointF(node.x, node.y)
            if (pos - click).manhattanLength() <= node.radius * 2.2:
                dist = math.hypot(pos.x() - click.x(), pos.y() - click.y())
                if dist <= node.radius + 4:
                    self.node_clicked.emit(node.page.url)
                    return
        super().mouseReleaseEvent(event)


class SiteMapTab(QWidget):
    node_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        legend = QLabel(
            "● Sin issues &nbsp;&nbsp; ● Info &nbsp;&nbsp; ● Advertencia &nbsp;&nbsp; ● Crítico"
            " &nbsp;&nbsp; ○ (borde punteado) Página huérfana — tamaño del nodo ∝ enlaces entrantes"
        )
        legend.setTextFormat(Qt.TextFormat.RichText)
        legend.setStyleSheet(
            f"padding: 8px 14px; font-size: 11.5px; color: #4B5563; background: #F9FAFB; "
            f"border-bottom: 1px solid #E5E7EB;"
        )
        layout.addWidget(legend)

        scroll = QScrollArea()
        scroll.setWidgetResizable(False)
        scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.canvas = SiteMapCanvas()
        self.canvas.node_clicked.connect(self.node_clicked)
        scroll.setWidget(self.canvas)
        layout.addWidget(scroll, stretch=1)

    def set_pages(self, pages: list[PageResult], seed_url: str) -> None:
        self.canvas.set_pages(pages, seed_url)
