"""
ラウドネス補正ページUI
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFileDialog, QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView, QCheckBox, QLineEdit, QInputDialog
from PySide6.QtCore import Qt, QEvent, Signal, QObject
from PySide6.QtGui import QColor
from pathlib import Path
from core.file_scanner import scan_video_files
from core.command_builder import CommandBuilder
from core.executor import Executor
import threading
from ui_parts.file_select_widget import FileSelectWidget
from ui_parts.log_console_widget import LogConsoleWidget
from ui_parts.external_storage_file_adder import ExternalStorageFileAdder
import os
import re

class LoudnessPage(QWidget):
    # Signal定義
    update_status = Signal(int, str)
    update_log = Signal(int, str)
    append_logbox = Signal(str)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        layout = QVBoxLayout(self)
        self.file_paths = []  # ファイルリストをインスタンス変数で管理
        # ファイル選択ウィジェット（共通化）
        self.file_select = FileSelectWidget()
        self.file_select.files_changed.connect(self.on_files_changed)
        layout.addWidget(self.file_select)
        # 外部ストレージファイル追加ウィジェット（共通化）
        self.ext_storage_adder = ExternalStorageFileAdder(self)
        self.ext_storage_adder.files_found.connect(self.file_select.add_files)
        layout.addWidget(self.ext_storage_adder)
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
        # 素材用最適化チェックボックス
        self.chk_material = QCheckBox("素材用に最適化（-23LUFS/音質優先/均一化）")
        self.chk_material.setToolTip("編集素材用途向け。音質を最大限維持しつつ全クリップの音量を均一化します。ラウドネス-23LUFS/ピーク-1dBTPで揃えます。")
        self.chk_material.setChecked(False)
        layout.addWidget(self.chk_material)
        # 書き出しフォルダ選択UI
        folder_layout = QHBoxLayout()
        self.edit_outdir = QLineEdit()
        self.edit_outdir.setReadOnly(True)
        self.edit_outdir.setPlaceholderText("未選択（素材と同じフォルダに書き出し）")
        btn_select_dir = QPushButton("書き出しフォルダ選択")
        btn_reset_dir = QPushButton("リセット")
        folder_layout.addWidget(QLabel("書き出し先:"))
        folder_layout.addWidget(self.edit_outdir)
        folder_layout.addWidget(btn_select_dir)
        folder_layout.addWidget(btn_reset_dir)
        layout.addLayout(folder_layout)
        self.output_dir = None
        btn_select_dir.clicked.connect(self.select_output_dir)
        btn_reset_dir.clicked.connect(self.reset_output_dir)
        # 実行ボタン（右下揃えのためのレイアウト調整）
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_run = QPushButton("ラウドネス補正を実行")
        btn_run.clicked.connect(self.run_loudness)
        btn_layout.addWidget(btn_run)
        layout.addLayout(btn_layout)
        # ログ表示欄（共通ウィジェット化）
        self.log_console = LogConsoleWidget()
        layout.addWidget(self.log_console)
        # ファイルリスト管理はfile_selectに一元化
        # Signal接続
        self.update_status.connect(self._update_status)
        self.update_log.connect(self._update_log)
        self.append_logbox.connect(self.log_console.append)

    def _update_status(self, row: int, status: str):
        self.table.setItem(row, 1, QTableWidgetItem(status))
    def _update_log(self, row: int, log: str):
        self.table.setItem(row, 2, QTableWidgetItem(log[-80:]))

    def on_files_changed(self, files):
        self.file_paths = files
        self.status_map = {f: i for i, f in enumerate(self.file_paths)}
        self.table.setRowCount(len(self.file_paths))
        for i, f in enumerate(self.file_paths):
            self.table.setItem(i, 0, QTableWidgetItem(Path(f).name))
            self.table.setItem(i, 1, QTableWidgetItem("未処理"))

    def select_files(self):
        self.file_select.select_files()

    def add_files(self, files):
        self.file_select.add_files(files)

    def select_output_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "書き出しフォルダを選択")
        if dir_path:
            self.output_dir = dir_path
            self.edit_outdir.setText(dir_path)

    def reset_output_dir(self):
        self.output_dir = None
        self.edit_outdir.clear()

    def run_loudness(self):
        use_dynaudnorm = self.chk_dynaudnorm.isChecked() and not self.chk_material.isChecked()
        material_mode = self.chk_material.isChecked()
        def parse_loudnorm_summary(log_lines):
            summary = {}
            for line in log_lines:
                # ピーク値やLUFSなどを抽出
                if m := re.match(r"\s*Input Integrated:\s*([\-\d\.]+)", line):
                    summary['input_lufs'] = float(m.group(1))
                elif m := re.match(r"\s*Input True Peak:\s*([\-\d\.]+)", line):
                    summary['input_tp'] = float(m.group(1))
                elif m := re.match(r"\s*Output Integrated:\s*([\-\d\.]+)", line):
                    summary['output_lufs'] = float(m.group(1))
                elif m := re.match(r"\s*Output True Peak:\s*([\-\d\.]+)", line):
                    summary['output_tp'] = float(m.group(1))
                elif m := re.match(r"\s*Output LRA:\s*([\-\d\.]+)", line):
                    summary['output_lra'] = float(m.group(1))
                elif 'WARNING' in line.upper() or 'clipping' in line.lower():
                    summary['warning'] = line.strip()
            return summary
        def task():
            for idx, file_path in enumerate(self.file_paths):
                row = self.status_map[file_path]
                self.update_status.emit(row, "実行中")
                input_path = Path(file_path)
                out_dir = Path(self.output_dir) if self.output_dir else input_path.parent
                out_name = input_path.stem + ("_mat-23LUFS" if material_mode else "_norm-14LUFS") + input_path.suffix
                output_path = out_dir / out_name
                cmd = CommandBuilder.build_loudness_normalization_cmd(
                    input_path, output_path, use_dynaudnorm=use_dynaudnorm, material_mode=material_mode)
                log_lines = []
                def log_callback(line):
                    log_lines.append(line)
                    self.update_log.emit(row, line)
                    self.append_logbox.emit(line)
                ret = Executor.run_command(cmd, log_callback)
                summary = parse_loudnorm_summary(log_lines)
                # 状態セルの色付き表示
                if 'warning' in summary or ('output_tp' in summary and summary['output_tp'] > -1.0):
                    warn_msg = summary.get('warning', '')
                    if 'output_tp' in summary and summary['output_tp'] > -1.0:
                        warn_msg += f" True Peak超過: {summary['output_tp']} dBTP"
                    status_item = QTableWidgetItem(f"警告: {warn_msg}")
                    status_item.setForeground(QColor("red"))
                    self.table.setItem(row, 1, status_item)
                    self.append_logbox.emit(f"[警告] {input_path.name}: {warn_msg}")
                else:
                    status_item = QTableWidgetItem("OK")
                    status_item.setForeground(QColor("green"))
                    self.table.setItem(row, 1, status_item)
                # 詳細もログ欄に表示
                detail = f"出力LUFS: {summary.get('output_lufs','')} / Peak: {summary.get('output_tp','')}dBTP / LRA: {summary.get('output_lra','')}"
                self.update_log.emit(row, detail)
                if ret == 0:
                    pass
                else:
                    fail_item = QTableWidgetItem("失敗")
                    fail_item.setForeground(QColor("red"))
                    self.table.setItem(row, 1, fail_item)
        threading.Thread(target=task, daemon=True).start()
