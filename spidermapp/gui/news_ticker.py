from __future__ import annotations

import webbrowser

from PySide6.QtCore import QThread, Qt, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from spidermapp.core import seo_news
from spidermapp.gui import theme

CARDS_VISIBLE = 3
FAVICON_FETCH_LIMIT = 9  # only the items that could actually be shown get their icon downloaded
ROTATE_INTERVAL_MS = 15000
REFRESH_INTERVAL_MS = 30 * 60 * 1000  # re-fetch every 30 minutes while the app is open
PANEL_MIN_HEIGHT = 260  # roughly a third of the default window height


class NewsWorker(QThread):
    finished_news = Signal(list)  # list[tuple[seo_news.NewsItem, bytes | None]]
    failed = Signal(str)

    def run(self) -> None:
        try:
            items = seo_news.fetch_seo_llm_news()
            enriched: list[tuple[seo_news.NewsItem, bytes | None]] = []
            for i, item in enumerate(items):
                favicon = seo_news.fetch_favicon(item.source_domain) if i < FAVICON_FETCH_LIMIT else None
                enriched.append((item, favicon))
            self.finished_news.emit(enriched)
        except Exception as exc:  # noqa: BLE001 - surfaced in the panel itself
            self.failed.emit(str(exc))


class NewsCard(QFrame):
    """One headline: source favicon + name, title, relative timestamp.
    The whole card is clickable and opens the article in the browser."""

    def __init__(self, item: seo_news.NewsItem, favicon_bytes: bytes | None, parent=None):
        super().__init__(parent)
        self._link = item.link
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            "NewsCard { background: white; border: 1px solid #E5E7EB; border-radius: 8px; }"
            "NewsCard:hover { border-color: " + theme.PRIMARY + "; }"
        )
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        source_row = QHBoxLayout()
        source_row.setSpacing(6)
        icon_label = QLabel()
        icon_label.setFixedSize(20, 20)
        if favicon_bytes:
            pixmap = QPixmap()
            if pixmap.loadFromData(favicon_bytes):
                icon_label.setPixmap(
                    pixmap.scaled(20, 20, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                )
        source_row.addWidget(icon_label)

        source_label = QLabel(item.source or "Google Noticias")
        source_label.setStyleSheet("font-size: 11px; font-weight: 700; color: #6B7280;")
        source_row.addWidget(source_label, stretch=1)
        layout.addLayout(source_row)

        title_label = QLabel(item.title)
        title_label.setWordWrap(True)
        title_label.setStyleSheet("font-size: 13.5px; font-weight: 600; color: #111827;")
        title_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        layout.addWidget(title_label, stretch=1)

        when = seo_news.relative_time(item.published_at)
        if when:
            time_label = QLabel(when)
            time_label.setStyleSheet("font-size: 10.5px; color: #9CA3AF;")
            layout.addWidget(time_label)

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt override
        if event.button() == Qt.MouseButton.LeftButton:
            webbrowser.open(self._link)
        super().mousePressEvent(event)


class NewsTicker(QWidget):
    """Sits between the progress row and the tabs: a panel of headlines
    about SEO and LLMs pulled from Google News' public RSS feed, sized to
    take up roughly a third of the window so there's something substantial
    to read while a crawl (or nothing) is running. Rotates through more
    stories than fit on screen at once."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[tuple[seo_news.NewsItem, bytes | None]] = []
        self._offset = 0
        self._worker: NewsWorker | None = None

        self.setStyleSheet(f"background: {theme.PRIMARY_SOFT}; border-bottom: 1px solid #E5E7EB;")
        self.setMinimumHeight(PANEL_MIN_HEIGHT)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 10, 14, 12)
        outer.setSpacing(8)

        tag = QLabel("NOTICIAS SEO / IA")
        tag.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {theme.PRIMARY}; letter-spacing: 0.04em;")
        outer.addWidget(tag)

        self.cards_row = QHBoxLayout()
        self.cards_row.setSpacing(12)
        outer.addLayout(self.cards_row, stretch=1)

        self.status_label = QLabel("Cargando noticias…")
        self.status_label.setStyleSheet("font-size: 11.5px; color: #6B7280;")
        outer.addWidget(self.status_label)
        self._render_cards([])  # empty placeholders while the first fetch is in flight

        self._rotate_timer = QTimer(self)
        self._rotate_timer.timeout.connect(self._rotate)
        self._rotate_timer.setInterval(ROTATE_INTERVAL_MS)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.refresh)
        self._refresh_timer.setInterval(REFRESH_INTERVAL_MS)
        self._refresh_timer.start()

        self.refresh()

    def refresh(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        self._worker = NewsWorker(self)
        self._worker.finished_news.connect(self._on_news)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_failed(self, message: str) -> None:
        if not self._items:
            self.status_label.setText("No se pudieron cargar noticias en este momento.")

    def _on_news(self, items: list) -> None:
        self._rotate_timer.stop()
        self._items = items
        self._offset = 0
        if not self._items:
            self.status_label.setText("Sin noticias disponibles en este momento.")
            self._render_cards([])
            return
        self.status_label.setText(f"{len(self._items)} titulares — se actualiza automáticamente.")
        self._render_current()
        if len(self._items) > CARDS_VISIBLE:
            self._rotate_timer.start()

    def _rotate(self) -> None:
        if not self._items:
            return
        self._offset = (self._offset + CARDS_VISIBLE) % len(self._items)
        self._render_current()

    def _render_current(self) -> None:
        n = len(self._items)
        visible = [self._items[(self._offset + i) % n] for i in range(min(CARDS_VISIBLE, n))]
        self._render_cards(visible)

    def _render_cards(self, visible: list[tuple[seo_news.NewsItem, bytes | None]]) -> None:
        while self.cards_row.count():
            item = self.cards_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        slots = visible + [None] * (CARDS_VISIBLE - len(visible))
        for slot in slots:
            if slot is None:
                placeholder = QFrame()
                placeholder.setStyleSheet("background: white; border: 1px dashed #E5E7EB; border-radius: 8px;")
                placeholder.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                self.cards_row.addWidget(placeholder, stretch=1)
            else:
                news_item, favicon_bytes = slot
                self.cards_row.addWidget(NewsCard(news_item, favicon_bytes), stretch=1)
