"""
共通ファイル選択＋ドラッグ＆ドロップ用ウィジェット
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QFileDialog, QAbstractItemView
from PySide6.QtCore import Qt, QEvent, Signal
from pathlib import Path
from core.file_scanner import scan_video_files

class FileSelectWidget(QWidget):
    files_changed = Signal(list)  # ファイルリストが変わったとき通知

    def __init__(self, file_types=("*.mp4", "*.mov", "*.mkv", "*.wav", "*.aac", "*.mp3")):
        super().__init__()
        self.file_types = file_types
        self.file_paths = []
        layout = QVBoxLayout(self)
        # ファイル追加ボタン
        self.btn_select = QPushButton("ファイルを追加 or ここにドラッグ&ドロップ")
        self.btn_select.clicked.connect(self.select_files)
        layout.addWidget(self.btn_select)
        # ドラッグ＆ドロップ有効化のみ（ファイルリストテーブルは表示しない）
        self.setAcceptDrops(True)

    def select_files(self):
        filter_str = "動画/音声ファイル ({});;すべてのファイル (*)".format(" ".join(self.file_types))
        files, _ = QFileDialog.getOpenFileNames(self, "ファイルを選択", "", filter_str)
        self.add_files([Path(f) for f in files])

    def add_files(self, files):
        added = False
        for f in files:
            if str(f) not in self.file_paths and self._is_valid_file(f):
                self.file_paths.append(str(f))
                added = True
        if added:
            self.files_changed.emit(self.file_paths)

    def clear_files(self):
        self.file_paths = []
        self.files_changed.emit(self.file_paths)

    def dragEnterEvent(self, event):
        # ファイル追加ボタン上でのドラッグ時は無視
        if self.btn_select.underMouse():
            event.ignore()
            return
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        # ファイル追加ボタン上でのドロップ時は無視
        if self.btn_select.underMouse():
            event.ignore()
            return
        files = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            p = Path(path)
            if p.is_dir():
                files.extend(scan_video_files(p))
            elif self._is_valid_file(path):
                files.append(Path(path))
        if files:
            self.add_files(files)

    def _is_valid_file(self, path):
        if isinstance(path, Path):
            path = str(path)
        ext = path.lower().split(".")[-1]
        for ft in self.file_types:
            if ft.replace("*.", "") == ext:
                return True
        return False
