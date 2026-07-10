"""Desktop design tokens and Qt stylesheet."""

COLORS = {
    "canvas": "#F4F6F8",
    "surface": "#FFFFFF",
    "surface_muted": "#F8FAFC",
    "text": "#172033",
    "text_muted": "#667085",
    "border": "#E6EAF0",
    "accent": "#3867E8",
    "accent_soft": "#EEF3FF",
    "success": "#16805C",
    "success_soft": "#EAF7F1",
    "warning": "#A85B00",
    "warning_soft": "#FFF4DF",
    "critical": "#C43D4B",
    "critical_soft": "#FDECEF",
}


APP_STYLESHEET = """
QWidget#appRoot {
    background: #F4F6F8;
    color: #172033;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue";
    font-size: 14px;
}
QLabel#eyebrow {
    color: #3867E8;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
}
QLabel#displayTitle {
    color: #172033;
    font-size: 27px;
    font-weight: 700;
}
QLabel#pageSubtitle, QLabel#mutedText {
    color: #667085;
}
QFrame#card {
    background: #FFFFFF;
    border: 1px solid #E6EAF0;
    border-radius: 16px;
}
QFrame#subtlePanel {
    background: #F8FAFC;
    border: 1px solid #EDF0F4;
    border-radius: 12px;
}
QLabel#cardTitle {
    color: #172033;
    font-size: 16px;
    font-weight: 650;
}
QLabel#sectionTitle {
    color: #172033;
    font-size: 13px;
    font-weight: 650;
}
QLabel#metricValue {
    color: #172033;
    font-size: 22px;
    font-weight: 700;
}
QLabel#metricLabel {
    color: #667085;
    font-size: 11px;
    font-weight: 600;
}
QLabel#badge, QLabel#brandBadge {
    border-radius: 10px;
    padding: 4px 9px;
    font-size: 11px;
    font-weight: 650;
}
QLabel#brandBadge {
    color: #3867E8;
    background: #EEF3FF;
}
QLabel#badge[tone="success"] { color: #16805C; background: #EAF7F1; }
QLabel#badge[tone="warning"] { color: #A85B00; background: #FFF4DF; }
QLabel#badge[tone="critical"] { color: #C43D4B; background: #FDECEF; }
QLabel#badge[tone="neutral"] { color: #526078; background: #EEF1F5; }
QPushButton#primaryButton {
    color: white;
    background: #3867E8;
    border: none;
    border-radius: 11px;
    padding: 11px 14px;
    font-weight: 650;
    text-align: left;
}
QPushButton#primaryButton:hover { background: #2F5CD4; }
QPushButton#primaryButton:pressed { background: #294FB7; }
QPushButton#actionButton {
    color: #263249;
    background: #F8FAFC;
    border: 1px solid #E6EAF0;
    border-radius: 11px;
    padding: 11px 13px;
    text-align: left;
    font-weight: 600;
}
QPushButton#actionButton:hover {
    color: #3867E8;
    background: #F3F6FF;
    border-color: #C9D6FA;
}
QPushButton#actionButton:disabled {
    color: #A3ABB8;
    background: #FAFBFC;
    border-color: #EEF0F3;
}
QPushButton#historyItem {
    color: #263249;
    background: #F8FAFC;
    border: 1px solid #E9EDF2;
    border-radius: 11px;
    padding: 11px 12px;
    text-align: left;
    font-weight: 600;
}
QPushButton#historyItem:hover {
    color: #3867E8;
    background: #F3F6FF;
    border-color: #C9D6FA;
}
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QToolTip {
    color: #FFFFFF;
    background: #172033;
    border: none;
    padding: 5px;
}
"""
