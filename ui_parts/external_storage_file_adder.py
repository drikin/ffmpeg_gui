"""
外部ストレージからファイル一覧生成ボタン（全タブ共通部品）
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QInputDialog
from PySide6.QtCore import Signal
from pathlib import Path
import os
from core.file_scanner import scan_video_files

class ExternalStorageFileAdder(QWidget):
    files_found = Signal(list)  # List[Path]

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.btn_ext_storage = QPushButton("外部ストレージからファイル一覧生成")
        self.btn_ext_storage.clicked.connect(self.scan_external_storage)
        layout.addWidget(self.btn_ext_storage)

    def scan_external_storage(self):
        volumes_dir = "/Volumes"
        try:
            candidates = [d for d in os.listdir(volumes_dir)
                          if os.path.isdir(os.path.join(volumes_dir, d)) and d not in ("Macintosh HD", ".DS_Store")]
        except Exception as e:
            self._emit_log(f"[エラー] 外部ストレージ検知失敗: {e}")
            return
        if not candidates:
            self._emit_log("外部ストレージが見つかりませんでした")
            return
        if len(candidates) == 1:
            target = candidates[0]
        else:
            target, ok = QInputDialog.getItem(self, "外部ストレージ選択", "マウント先を選択", candidates, 0, False)
            if not ok:
                return
        storage_path = os.path.join(volumes_dir, target)
        files = scan_video_files(Path(storage_path))
        if not files:
            self._emit_log(f"{storage_path} に動画/音声ファイルが見つかりませんでした")
            return
        self.files_found.emit(files)
        self._emit_log(f"{storage_path} から {len(files)} 件のファイルを追加しました")

    def _emit_log(self, msg):
        # 親に log_console があればappendする
        parent = self.parent()
        if hasattr(parent, "log_console"):
            parent.log_console.append(msg)
