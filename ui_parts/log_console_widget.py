"""
全タブ共通のログコンソールウィジェット
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout
from PySide6.QtCore import Signal

class LogConsoleWidget(QWidget):
    append_log = Signal(str)
    clear_log = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        layout.addWidget(self.log_box)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_clear = QPushButton("ログクリア")
        self.btn_clear.clicked.connect(self.clear)
        btn_layout.addWidget(self.btn_clear)
        layout.addLayout(btn_layout)
        self.append_log.connect(self.log_box.append)
        self.clear_log.connect(self.log_box.clear)

    def append(self, text):
        self.log_box.append(text)

    def clear(self):
        self.log_box.clear()
