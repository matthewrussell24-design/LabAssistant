"""Reusable PySide6 components for the desktop research workspace."""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


def add_soft_shadow(widget: QWidget) -> None:
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(28)
    shadow.setOffset(0, 7)
    shadow.setColor(QColor(26, 39, 64, 22))
    widget.setGraphicsEffect(shadow)


class Card(QFrame):
    def __init__(self, title: str = "", subtitle: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("card")
        self.content = QVBoxLayout(self)
        self.content.setContentsMargins(20, 19, 20, 20)
        self.content.setSpacing(12)
        if title:
            title_label = QLabel(title)
            title_label.setObjectName("cardTitle")
            self.content.addWidget(title_label)
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName("mutedText")
            subtitle_label.setWordWrap(True)
            self.content.addWidget(subtitle_label)
        add_soft_shadow(self)


class StatusBadge(QLabel):
    def __init__(self, text: str, tone: str = "neutral", parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setObjectName("badge")
        self.setProperty("tone", tone)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def set_status(self, text: str, tone: str) -> None:
        self.setText(text)
        self.setProperty("tone", tone)
        self.style().unpolish(self)
        self.style().polish(self)


class MetricTile(QFrame):
    def __init__(self, label: str, value: str = "—", parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("subtlePanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(3)
        self.value_label = QLabel(value)
        self.value_label.setObjectName("metricValue")
        label_widget = QLabel(label.upper())
        label_widget.setObjectName("metricLabel")
        layout.addWidget(self.value_label)
        layout.addWidget(label_widget)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)


class WorkspaceAction(QPushButton):
    def __init__(
        self,
        title: str,
        detail: str,
        *,
        primary: bool = False,
        enabled: bool = True,
        parent: QWidget | None = None,
    ):
        super().__init__(f"{title}\n{detail}", parent)
        self.setObjectName("primaryButton" if primary else "actionButton")
        self.setEnabled(enabled)
        self.setMinimumHeight(58)
        if not enabled:
            self.setToolTip("Planned for a future application capability")


class HistoryItem(QPushButton):
    activated = Signal(object)

    def __init__(self, title: str, detail: str, payload: object, parent: QWidget | None = None):
        super().__init__(f"{title}\n{detail}", parent)
        self.setObjectName("historyItem")
        self.payload = payload
        self.setMinimumHeight(58)
        self.clicked.connect(lambda: self.activated.emit(self.payload))


class AnalysisSection(QFrame):
    def __init__(self, title: str, items: Iterable[str] = (), parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("subtlePanel")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(15, 14, 15, 14)
        self.layout.setSpacing(7)
        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")
        self.layout.addWidget(title_label)
        self.set_items(items)

    def set_items(self, items: Iterable[str]) -> None:
        while self.layout.count() > 1:
            item = self.layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()
        values = list(items) or ["No analysis available yet."]
        for value in values:
            label = QLabel(f"•  {value}")
            label.setObjectName("mutedText")
            label.setWordWrap(True)
            label.setAlignment(Qt.AlignmentFlag.AlignTop)
            self.layout.addWidget(label)
