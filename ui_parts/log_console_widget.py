"""
全タブ共通のログコンソールウィジェット
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QHBoxLayout, QTextEdit
from PySide6.QtCore import Signal, Qt, QThread

class LogConsoleWidget(QWidget):
    append_log = Signal(str)
    clear_log = Signal()
    append_signal = Signal(str)

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
        self.append_signal.connect(self._append_slot)

    def append(self, text):
        # スレッドセーフなappend
        if self.thread() != QThread.currentThread():
            self.append_signal.emit(text)
        else:
            self._append_slot(text)

    def _append_slot(self, text):
        self.log_box.append(text)

    def clear(self):
        self.log_box.clear()
