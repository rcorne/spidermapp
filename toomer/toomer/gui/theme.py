"""Tema visual de Toomer (claro, sobrio)."""

PRIMARIO = "#1F6FEB"
PRIMARIO_HOVER = "#3B82F6"
FONDO = "#F6F7F9"
PANEL = "#FFFFFF"
BORDE = "#E3E6EA"
TEXTO = "#1B1F24"
TEXTO_SUAVE = "#6B7280"
RAIL = "#101828"
RAIL_TEXTO = "#B8C0CC"
RAIL_ACTIVO = "#1D2939"

HOJA_ESTILO = f"""
QMainWindow, QWidget {{ background: {FONDO}; color: {TEXTO}; font-size: 13px; }}
QFrame#panel {{ background: {PANEL}; border: 1px solid {BORDE}; border-radius: 10px; }}
QLabel#titulo {{ font-size: 22px; font-weight: 700; }}
QLabel#subtitulo {{ color: {TEXTO_SUAVE}; font-size: 13px; }}
QLabel#seccion {{ font-size: 14px; font-weight: 600; margin-top: 4px; }}
QLabel#nota {{ color: {TEXTO_SUAVE}; font-size: 12px; }}
QLabel#error {{ color: #B42318; }}
QPushButton {{ background: {PANEL}; border: 1px solid {BORDE}; border-radius: 6px; padding: 6px 14px; }}
QPushButton:hover {{ border-color: {PRIMARIO}; }}
QPushButton:disabled {{ color: #9CA3AF; }}
QPushButton#primario {{ background: {PRIMARIO}; color: white; border: none; font-weight: 600; }}
QPushButton#primario:hover {{ background: {PRIMARIO_HOVER}; }}
QPushButton#primario:disabled {{ background: #9DB9F0; }}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit, QPlainTextEdit, QTextEdit {{
    background: {PANEL}; border: 1px solid {BORDE}; border-radius: 6px; padding: 5px 8px; }}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{ border-color: {PRIMARIO}; }}
QTableView {{ background: {PANEL}; border: 1px solid {BORDE}; border-radius: 6px; gridline-color: #EEF0F3;
    selection-background-color: #DBEAFE; selection-color: {TEXTO}; alternate-background-color: #FAFBFC; }}
QHeaderView::section {{ background: #F1F3F6; border: none; border-bottom: 1px solid {BORDE}; padding: 6px; font-weight: 600; }}
QListWidget#rail {{ background: {RAIL}; border: none; color: {RAIL_TEXTO}; font-size: 13px; outline: 0; }}
QListWidget#rail::item {{ padding: 10px 16px; border-left: 3px solid transparent; }}
QListWidget#rail::item:selected {{ background: {RAIL_ACTIVO}; color: white; border-left: 3px solid {PRIMARIO}; }}
QListWidget#rail::item:hover {{ background: {RAIL_ACTIVO}; }}
QLabel#marca {{ background: {RAIL}; color: white; font-size: 20px; font-weight: 800; padding: 18px 16px 8px 16px; }}
QLabel#marca_sub {{ background: {RAIL}; color: {RAIL_TEXTO}; font-size: 11px; padding: 0 16px 14px 16px; }}
QProgressBar {{ border: 1px solid {BORDE}; border-radius: 6px; background: {PANEL}; text-align: center; height: 14px; }}
QProgressBar::chunk {{ background: {PRIMARIO}; border-radius: 5px; }}
QStatusBar {{ background: {PANEL}; border-top: 1px solid {BORDE}; color: {TEXTO_SUAVE}; }}
QTabWidget::pane {{ border: 1px solid {BORDE}; border-radius: 6px; background: {PANEL}; }}
QTabBar::tab {{ padding: 7px 14px; border: 1px solid transparent; border-bottom: none; }}
QTabBar::tab:selected {{ background: {PANEL}; border-color: {BORDE}; border-top-left-radius: 6px; border-top-right-radius: 6px; }}
QGroupBox {{ border: 1px solid {BORDE}; border-radius: 8px; margin-top: 10px; padding-top: 6px; background: {PANEL}; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: {TEXTO_SUAVE}; }}
QScrollArea {{ border: none; }}
"""
