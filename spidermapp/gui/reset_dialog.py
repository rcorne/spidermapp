from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from spidermapp.core import data_reset
from spidermapp.gui import theme

# Typing the word is the last line of defence: it makes the delete something
# you can only do on purpose, not something a stray Enter can trigger.
CONFIRM_WORD = "BORRAR"


class ResetDataDialog(QDialog):
    """Archivo → Empezar de cero. Returns the list of target keys the user
    confirmed, via selected_keys(), or an empty list if they cancelled.

    Deliberately spells out what each item holds and how much of it there is:
    this is irreversible, and "se borrarán tus datos" gives someone no way to
    judge whether that's fine or a disaster."""

    def __init__(self, parent=None, base_dir=data_reset.BASE_DIR):
        super().__init__(parent)
        self.setWindowTitle("Empezar de cero")
        self.resize(560, 560)

        self._checkboxes: dict[str, QCheckBox] = {}
        self._statuses = data_reset.inventory(base_dir)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 14)
        outer.setSpacing(10)

        title = QLabel("Dejar Pidge como recién instalado")
        title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {theme.TEXT_PRIMARY};")
        outer.addWidget(title)

        intro = QLabel(
            "Elige qué borrar. La app queda en blanco de inmediato: se vacían la tabla, "
            "el mapa, «Hoy» y el tablero, sin necesidad de reiniciar."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet(f"font-size: 12.5px; color: {theme.TEXT_SECONDARY};")
        outer.addWidget(intro)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll, stretch=1)

        content = QWidget()
        scroll.setWidget(content)
        items = QVBoxLayout(content)
        items.setContentsMargins(0, 4, 0, 4)
        items.setSpacing(12)

        for status in self._statuses:
            items.addWidget(self._build_item(status))
        items.addStretch(1)

        self.backup_checkbox = QCheckBox("Guardar un respaldo antes de borrar (recomendado)")
        self.backup_checkbox.setChecked(True)
        self.backup_checkbox.setStyleSheet(f"font-size: 12.5px; color: {theme.TEXT_PRIMARY};")
        outer.addWidget(self.backup_checkbox)

        backup_hint = QLabel(
            "El respaldo queda en una carpeta dentro de ~/.spidermapp y puedes borrarla a mano "
            "cuando confirmes que no la necesitas. Sin respaldo, esto no se puede deshacer: no "
            "pasa por la Papelera."
        )
        backup_hint.setWordWrap(True)
        backup_hint.setStyleSheet(f"font-size: 11.5px; color: {theme.TEXT_MUTED};")
        outer.addWidget(backup_hint)

        confirm_label = QLabel(f"Para continuar, escribe <b>{CONFIRM_WORD}</b>:")
        confirm_label.setTextFormat(Qt.TextFormat.RichText)
        confirm_label.setStyleSheet(f"font-size: 12.5px; color: {theme.TEXT_PRIMARY};")
        outer.addWidget(confirm_label)

        self.confirm_input = QLineEdit()
        self.confirm_input.setPlaceholderText(CONFIRM_WORD)
        self.confirm_input.textChanged.connect(self._refresh_confirm_state)
        outer.addWidget(self.confirm_input)

        buttons = QDialogButtonBox()
        self._confirm_button = buttons.addButton("Borrar definitivamente", QDialogButtonBox.ButtonRole.AcceptRole)
        self._confirm_button.setStyleSheet(theme.BUTTON_DANGER_QSS)
        # Qt makes an AcceptRole button respond to Enter by default, which on
        # a destructive dialog means a stray keypress wipes everything that
        # happens to be pre-checked. Take it out of the Enter path entirely
        # and let Cancel be what Enter hits.
        self._confirm_button.setAutoDefault(False)
        self._confirm_button.setDefault(False)

        cancel = buttons.addButton("Cancelar", QDialogButtonBox.ButtonRole.RejectRole)
        cancel.setStyleSheet(theme.BUTTON_SECONDARY_QSS)
        cancel.setAutoDefault(True)
        cancel.setDefault(True)

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

        self._refresh_confirm_state()

    def wants_backup(self) -> bool:
        return self.backup_checkbox.isChecked()

    def _build_item(self, status: data_reset.TargetStatus) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        checkbox = QCheckBox(status.target.label)
        checkbox.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {theme.TEXT_PRIMARY};")
        # Nothing stored means nothing to delete — showing it unchecked and
        # disabled is clearer than hiding it, since it answers "is that
        # already clean?" too.
        checkbox.setEnabled(status.exists)
        checkbox.setChecked(status.exists and status.target.default_selected)
        checkbox.stateChanged.connect(self._refresh_confirm_state)
        layout.addWidget(checkbox)
        self._checkboxes[status.target.key] = checkbox

        description = QLabel(status.target.description)
        description.setWordWrap(True)
        description.setStyleSheet(f"font-size: 11.5px; color: {theme.TEXT_MUTED}; margin-left: 22px;")
        layout.addWidget(description)

        amount = QLabel(self._describe_amount(status))
        amount.setStyleSheet(f"font-size: 11px; color: {theme.TEXT_FAINT}; margin-left: 22px;")
        layout.addWidget(amount)

        return box

    @staticmethod
    def _describe_amount(status: data_reset.TargetStatus) -> str:
        if not status.exists:
            return "Vacío — no hay nada que borrar."
        size = data_reset.format_size(status.size_bytes)
        if status.target.key == "history":
            sites = "sitio" if status.item_count == 1 else "sitios"
            return f"{status.item_count} {sites} · {size}"
        archivos = "archivo" if status.item_count == 1 else "archivos"
        return f"{status.item_count} {archivos} · {size}"

    def _refresh_confirm_state(self) -> None:
        typed_ok = self.confirm_input.text().strip().upper() == CONFIRM_WORD
        self._confirm_button.setEnabled(bool(self.selected_keys()) and typed_ok)

    def selected_keys(self) -> list[str]:
        return [key for key, box in self._checkboxes.items() if box.isChecked() and box.isEnabled()]
