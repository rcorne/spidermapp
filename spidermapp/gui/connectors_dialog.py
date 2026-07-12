from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from spidermapp.core import connectors


class ConnectorsDialog(QDialog):
    """Paste-your-key configuration for every external API Spidermapp can use.
    Keys live in ~/.spidermapp/connectors.json (chmod 600), never in the repo."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Conectores — claves API")
        self.resize(640, 560)

        outer = QVBoxLayout(self)

        intro = QLabel(
            "Pega aquí tus claves API. Cada análisis funciona solo con los servicios que configures; "
            "los demás quedan desactivados. Las claves se guardan únicamente en tu Mac "
            "(~/.spidermapp/connectors.json)."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #4B5563; font-size: 12px;")
        outer.addWidget(intro)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll, stretch=1)

        form_host = QWidget()
        form = QFormLayout(form_host)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        scroll.setWidget(form_host)

        config = connectors.load_config()
        self._fields: dict[str, QLineEdit] = {}
        for spec in connectors.CONNECTORS:
            field = QLineEdit(config.get(spec.key, ""))
            field.setEchoMode(QLineEdit.EchoMode.Password)
            field.setPlaceholderText(spec.field_label)
            self._fields[spec.key] = field

            label = QLabel(f'{spec.label}<br><a href="{spec.help_url}" style="font-size:10px;">Cómo obtener la clave</a>')
            label.setTextFormat(Qt.TextFormat.RichText)
            label.setOpenExternalLinks(True)
            if spec.needs_oauth:
                label.setToolTip("Este servicio requiere configuración OAuth adicional; la clave se guarda para la integración futura.")
            form.addRow(label, field)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def _save(self) -> None:
        config = {key: field.text().strip() for key, field in self._fields.items() if field.text().strip()}
        connectors.save_config(config)
        self.accept()
