"""
動画結合ページUI
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit, QFileDialog, QListWidget
from ui_parts.file_select_widget import FileSelectWidget
from ui_parts.external_storage_file_adder import ExternalStorageFileAdder
from ui_parts.log_console_widget import LogConsoleWidget
from PySide6.QtCore import Qt
from pathlib import Path

class VideoConcatPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        # ファイル選択
        self.file_select = FileSelectWidget()
        layout.addWidget(self.file_select)
        # 外部ストレージから追加
        self.ext_storage_adder = ExternalStorageFileAdder(self)
        self.ext_storage_adder.files_found.connect(self.file_select.add_files)
        layout.addWidget(self.ext_storage_adder)
        # ファイルリスト表示（ストレージボタンの下）
        self.list_files = QListWidget()
        layout.addWidget(self.list_files)
        self.file_select.files_changed.connect(self.update_file_list)
        self.update_file_list(self.file_select.get_files() if hasattr(self.file_select, "get_files") else [])
        # 出力ファイル名
        out_layout = QHBoxLayout()
        out_layout.addWidget(QLabel("出力ファイル名:"))
        self.edit_outfile = QLineEdit("concat_output.mp4")
        out_layout.addWidget(self.edit_outfile)
        btn_outdir = QPushButton("保存先選択")
        out_layout.addWidget(btn_outdir)
        self.outdir = None
        btn_outdir.clicked.connect(self.select_outdir)
        layout.addLayout(out_layout)
        # 実行ボタン
        self.btn_run = QPushButton("結合実行")
        layout.addWidget(self.btn_run)
        # ログ
        self.log_console = LogConsoleWidget()
        layout.addWidget(self.log_console)
        self.btn_run.clicked.connect(self.run_concat)
    def select_outdir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "保存先フォルダを選択")
        if dir_path:
            self.outdir = dir_path
    def run_concat(self):
        files = [self.list_files.item(i).text() for i in range(self.list_files.count())]
        if not files or len(files) < 2:
            self.log_console.append("2つ以上の動画ファイルを選択してください")
            return
        outdir = Path(self.outdir) if self.outdir else Path(files[0]).parent
        outfile = outdir / self.edit_outfile.text()
        from core.command_builder import CommandBuilder
        cmd, concat_list_path, need_reencode, format_list, force_reason = CommandBuilder.build_video_concat_cmd(files, outfile)
        import threading, os
        def task():
            # フォーマット判定ログ
            if force_reason:
                self.log_console.append(f"[INFO] {force_reason}")
            elif need_reencode:
                self.log_console.append("[INFO] 異なるフォーマットの動画が混在しているため再エンコードして結合します（HWエンコード:h264_videotoolbox）")
            else:
                self.log_console.append("[INFO] 全て同一フォーマットのため再エンコードなしで結合します (-c copy)")
            self.log_console.append(f"結合コマンド実行: {' '.join(cmd)}")
            # 詳細フォーマット情報も表示
            for i, fmt in enumerate(format_list):
                self.log_console.append(f"[{i+1}] {files[i]} → {fmt}")
            from core.executor import Executor
            ret = Executor.run_command(cmd, self.log_console.append)
            if ret == 0:
                self.log_console.append(f"結合完了: {outfile}")
            else:
                self.log_console.append("[エラー] 結合に失敗しました")
            # 一時リストファイル削除
            if concat_list_path and os.path.exists(concat_list_path):
                os.remove(concat_list_path)
        threading.Thread(target=task, daemon=True).start()
    def update_file_list(self, files):
        self.list_files.clear()
        for f in files:
            self.list_files.addItem(str(f))
