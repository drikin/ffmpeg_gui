"""
Loudness Measureページ（ffprobe/ffmpegによるラウドネス測定）
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QFileDialog, QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView
from PySide6.QtCore import Qt, QEvent
from pathlib import Path
from core.ffprobe_loudness import FFprobeLoudness
import threading
from ui_parts.file_select_widget import FileSelectWidget
from ui_parts.log_console_widget import LogConsoleWidget
from ui_parts.external_storage_file_adder import ExternalStorageFileAdder

from PySide6.QtCore import Signal

class LoudnessMeasurePage(QWidget):
    add_files_signal = Signal(object)  # 型をobjectにしてPySide6の型不一致を回避
    def __init__(self):
        super().__init__()
        print(f"[DEBUG][stdout] LoudnessMeasurePage __init__ id={id(self)}")
        if hasattr(self, 'log_console'):
            self.log_console.append(f"[DEBUG] LoudnessMeasurePage __init__ id={id(self)}")
        self.add_files_signal.connect(self.add_files)
        layout = QVBoxLayout(self)
        # ファイル選択ウィジェット（共通化）
        self.file_select = FileSelectWidget()
        self.file_select.files_changed.connect(self.on_files_changed)
        layout.addWidget(self.file_select)
        # add_files_signalをfile_select.add_filesに接続
        self.add_files_signal.connect(self.add_files)
        # 外部ストレージファイル追加ウィジェット（共通化）
        self.ext_storage_adder = ExternalStorageFileAdder(self)
        self.ext_storage_adder.files_found.connect(self.file_select.add_files)
        layout.addWidget(self.ext_storage_adder)
        # ファイルリスト
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ファイル名", "Integrated (LUFS)", "True Peak (dB)", "LRA", "ログ"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setDefaultSectionSize(26)
        layout.addWidget(self.table)
        # 実行ボタン
        btn_run = QPushButton("ラウドネス測定を実行")
        btn_run.clicked.connect(self.run_measure)
        layout.addWidget(btn_run)
        # ログ表示欄（共通ウィジェット化）
        self.log_console = LogConsoleWidget()
        layout.addWidget(self.log_console)
        # ファイルリスト管理はfile_selectに一元化
        self.status_map = {}
        # ドラッグ&ドロップ有効化
        # self.setAcceptDrops(True)

    def add_files(self, files):
        print(f"[DEBUG][stdout] add_files called: {files} id={id(self)}")
        if hasattr(self, 'log_console'):
            self.log_console.append(f"[DEBUG] add_files called: {files} id={id(self)}")
        """
        VideoConcatPageと同じくSignal経由でファイル追加
        """
        self.file_select.add_files(files)
        # デバッグ: 追加直後のファイルリストをログ出力
        if hasattr(self, 'log_console'):
            self.log_console.append(f"[DEBUG] add_files呼び出し: {files}")
            self.log_console.append(f"[DEBUG] file_select.file_paths: {self.file_select.file_paths}")

    def on_files_changed(self, file_paths):
        print(f"[DEBUG][stdout] on_files_changed: {file_paths} id={id(self)}")
        if hasattr(self, 'log_console'):
            self.log_console.append(f"[DEBUG] on_files_changed: {file_paths} id={id(self)}")
        self.file_paths = file_paths
        # デバッグ: on_files_changedで受け取ったファイルリストをログ出力
        if hasattr(self, 'log_console'):
            self.log_console.append(f"[DEBUG] on_files_changed: {file_paths}")
        self.status_map = {f: i for i, f in enumerate(self.file_paths)}
        self.table.setRowCount(len(self.file_paths))
        for i, f in enumerate(self.file_paths):
            self.table.setItem(i, 0, QTableWidgetItem(Path(f).name))
            self.table.setItem(i, 1, QTableWidgetItem("-"))
            self.table.setItem(i, 2, QTableWidgetItem("-"))
            self.table.setItem(i, 3, QTableWidgetItem("-"))
            self.table.setItem(i, 4, QTableWidgetItem("未処理"))

    def select_files(self):
        self.file_select.select_files()

    def add_files(self, files):
        self.file_select.add_files(files)

    def reset_file_list(self):
        if hasattr(self, 'file_select'):
            self.file_select.clear()
        if hasattr(self, 'table'):
            self.table.setRowCount(0)
        self.file_paths = []
        self.status_map = {}

    def run_measure(self):
        def task():
            for file_path in self.file_paths:
                row = self.status_map[file_path]
                self.table.setItem(row, 4, QTableWidgetItem("実行中"))
                self.log_console.append(f"[実行開始] {file_path}")
                result, log = FFprobeLoudness.measure_loudness(Path(file_path))
                if result:
                    # ラウドネス測定値をテーブルに反映
                    self.table.setItem(row, 1, QTableWidgetItem(str(result.get("input_i", "-"))))
                    self.table.setItem(row, 2, QTableWidgetItem(str(result.get("input_tp", "-"))))
                    self.table.setItem(row, 3, QTableWidgetItem(str(result.get("input_lra", "-"))))
                    self.table.setItem(row, 4, QTableWidgetItem("成功"))
                    self.log_console.append(f"[成功] {file_path}")
                else:
                    self.table.setItem(row, 4, QTableWidgetItem("失敗"))
                    self.log_console.append(f"[失敗] {file_path}\n{log}")
        threading.Thread(target=task, daemon=True).start()
