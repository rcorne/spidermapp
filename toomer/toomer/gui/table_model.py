from __future__ import annotations

import numpy as np
import pandas as pd
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt


class ModeloDataFrame(QAbstractTableModel):
    """Modelo Qt de solo lectura sobre un DataFrame de pandas."""

    def __init__(self, df: pd.DataFrame | None = None, parent=None):
        super().__init__(parent)
        self._df = df if df is not None else pd.DataFrame()

    def set_df(self, df: pd.DataFrame):
        self.beginResetModel()
        self._df = df.reset_index(drop=True) if df is not None else pd.DataFrame()
        self.endResetModel()

    @property
    def df(self) -> pd.DataFrame:
        return self._df

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._df)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._df.columns)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        v = self._df.iat[index.row(), index.column()]
        if role == Qt.DisplayRole:
            return formatear(v)
        if role == Qt.TextAlignmentRole and isinstance(v, (int, float, np.integer, np.floating)):
            return int(Qt.AlignRight | Qt.AlignVCenter)
        if role == Qt.UserRole:
            return v
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return str(self._df.columns[section]).replace("_", " ")
        return str(section + 1)

    def sort(self, column, order=Qt.AscendingOrder):
        if self._df.empty:
            return
        self.layoutAboutToBeChanged.emit()
        col = self._df.columns[column]
        self._df = self._df.sort_values(col, ascending=order == Qt.AscendingOrder, kind="mergesort",
                                        na_position="last").reset_index(drop=True)
        self.layoutChanged.emit()


def formatear(v) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return ""
    if isinstance(v, (pd.Timestamp,)):
        return v.strftime("%Y-%m-%d") if v.hour == 0 and v.minute == 0 else v.strftime("%Y-%m-%d %H:%M")
    if isinstance(v, (float, np.floating)):
        return f"{v:,.2f}"
    if isinstance(v, (int, np.integer)):
        return f"{v:,}"
    return str(v)
