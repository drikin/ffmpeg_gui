"""
ラウドネス補正ページUI
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFileDialog, QTableWidget, QTableWidgetItem, QTextEdit, QAbstractItemView, QHeaderView, QCheckBox
from PySide6.QtCore import Qt, QEvent, Signal, QObject
from pathlib import Path
from core.file_scanner import scan_video_files
from core.command_builder import CommandBuilder
from core.executor import Executor
import threading

class LoudnessPage(QWidget):
    # Signal定義
    update_status = Signal(int, str)
    update_log = Signal(int, str)
    append_logbox = Signal(str)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        layout = QVBoxLayout(self)
        # ファイル追加ボタン
        btn_select = QPushButton("ファイル追加")
        btn_select.clicked.connect(self.select_files)
        layout.addWidget(btn_select)
        # ドラッグ&ドロップ領域
        self.drop_label = QLabel("ここに動画ファイルまたはフォルダーをドロップ")
        self.drop_label.setStyleSheet("border: 2px dashed #6272a4; padding: 24px; margin: 8px;")
        self.drop_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.drop_label)
        # ファイルリスト
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["ファイル名", "状態", "ログ"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # ファイル名列は伸縮
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # 状態
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # ログ
        self.table.verticalHeader().setDefaultSectionSize(26)  # 行高さ詰める
        self.table.setStyleSheet("""
            QTableWidget { padding: 0; margin: 0; gridline-color: #44475a; }
            QHeaderView::section { background: #282a36; color: #f8f8f2; padding: 2px; border: none; }
            QTableWidget::item { padding-left: 4px; padding-right: 4px; }
        """)
        layout.addWidget(self.table)
        # dynaudnorm有効チェックボックス
        self.chk_dynaudnorm = QCheckBox("dynaudnorm（自動音量均一化）を有効にする")
        self.chk_dynaudnorm.setChecked(False)
        layout.addWidget(self.chk_dynaudnorm)
        # 実行ボタン
        btn_run = QPushButton("ラウドネス補正を実行")
        btn_run.clicked.connect(self.run_loudness)
        layout.addWidget(btn_run)
        # ログ表示欄
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        layout.addWidget(self.log_box)
        # ファイルリスト管理
        self.file_paths = []
        self.status_map = {}
        # Signal接続
        self.update_status.connect(self._update_status)
        self.update_log.connect(self._update_log)
        self.append_logbox.connect(self.log_box.append)

    def _update_status(self, row: int, status: str):
        self.table.setItem(row, 1, QTableWidgetItem(status))
    def _update_log(self, row: int, log: str):
        self.table.setItem(row, 2, QTableWidgetItem(log[-80:]))

    def select_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "動画ファイルを選択", "", "動画ファイル (*.mp4 *.mov *.mkv)")
        self.add_files([Path(f) for f in files])

    def add_files_from_folder(self, folder):
        files = scan_video_files(Path(folder))
        self.add_files(files)

    def add_files(self, files):
        for f in files:
            if str(f) not in self.file_paths:
                row = self.table.rowCount()
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(str(f.name)))
                self.table.setItem(row, 1, QTableWidgetItem("未処理"))
                self.table.setItem(row, 2, QTableWidgetItem(""))
                self.file_paths.append(str(f))
                self.status_map[str(f)] = row

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        files = []
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.is_dir():
                files.extend(scan_video_files(path))
            elif path.is_file():
                if path.suffix.lower() in {'.mp4', '.mov', '.mkv'}:
                    files.append(path)
        self.add_files(files)

    def run_loudness(self):
        use_dynaudnorm = self.chk_dynaudnorm.isChecked()
        def task():
            for idx, file_path in enumerate(self.file_paths):
                row = self.status_map[file_path]
                self.update_status.emit(row, "実行中")
                input_path = Path(file_path)
                output_path = input_path.with_name(input_path.stem + "_norm-14LUFS" + input_path.suffix)
                cmd = CommandBuilder.build_loudness_normalization_cmd(input_path, output_path, use_dynaudnorm=use_dynaudnorm)
                def log_callback(line):
                    self.update_log.emit(row, line)
                    self.append_logbox.emit(line)
                ret = Executor.run_command(cmd, log_callback)
                if ret == 0:
                    self.update_status.emit(row, "成功")
                else:
                    self.update_status.emit(row, "失敗")
        threading.Thread(target=task, daemon=True).start()
