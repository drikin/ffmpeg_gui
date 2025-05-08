"""
AI自動セリフ抽出＆クロスフェード編集ページUI
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QLineEdit, QFileDialog, QTextEdit
from PySide6.QtCore import Qt, Signal
from core.speech_segment_extractor import SpeechSegmentExtractor
from core.executor import Executor
import os
import threading
import shlex

class AutoSpeechExtractPage(QWidget):
    update_status = Signal(int, str)
    update_log = Signal(int, str)
    append_logbox = Signal(str)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        layout = QVBoxLayout(self)
        self.extractor = SpeechSegmentExtractor()
        self.file_path = None
        self.srt_path = None
        self.segments = []
        self.output_path = None

        # ファイル選択UI
        self.edit_file = QLineEdit()
        self.edit_file.setReadOnly(True)
        btn_select_file = QPushButton("動画ファイル選択")
        btn_select_file.clicked.connect(self.select_file)
        layout.addWidget(QLabel("入力動画ファイル:"))
        layout.addWidget(self.edit_file)
        layout.addWidget(btn_select_file)

        # 出力先選択
        self.edit_output = QLineEdit()
        self.edit_output.setReadOnly(True)
        btn_select_output = QPushButton("出力ファイル選択")
        btn_select_output.clicked.connect(self.select_output)
        layout.addWidget(QLabel("出力ファイル:"))
        layout.addWidget(self.edit_output)
        layout.addWidget(btn_select_output)

        # 実行ボタン
        btn_run = QPushButton("AI自動セリフ抽出＆編集実行")
        btn_run.clicked.connect(self.run_extract)
        layout.addWidget(btn_run)

        # ログ表示
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(120)
        layout.addWidget(self.log_text)

    def select_file(self):
        file, _ = QFileDialog.getOpenFileName(self, "動画ファイル選択", "", "動画ファイル (*.mp4 *.mov *.mkv *.avi)")
        if file:
            self.file_path = file
            self.edit_file.setText(file)

    def select_output(self):
        file, _ = QFileDialog.getSaveFileName(self, "出力ファイル選択", "", "動画ファイル (*.mp4)")
        if file:
            self.output_path = file
            self.edit_output.setText(file)

    def run_extract(self):
        if not self.file_path or not self.output_path:
            self.log_text.append("入力・出力ファイルを選択してください")
            return
        self.log_text.append("Whisperで音声認識中...")
        threading.Thread(target=self._run_extract_task, daemon=True).start()

    def _run_extract_task(self):
        try:
            srt_path = self.extractor.transcribe_to_srt(self.file_path)
            self.srt_path = srt_path
            self._append_log(f"SRT生成完了: {srt_path}\nセグメント抽出中...")
            segments = self.extractor.parse_srt_segments(srt_path)
            self.segments = segments
            self._append_log(f"セグメント抽出完了: {len(segments)}区間\nFFmpegコマンド生成中...")
            ffmpeg_cmd = self.extractor.build_ffmpeg_commands(self.file_path, segments, self.output_path)
            self._append_log(f"コマンド生成完了\n{ffmpeg_cmd}")
            # FFmpegコマンド自動実行
            if ffmpeg_cmd.startswith("#"):
                self._append_log(ffmpeg_cmd)
                return
            self._append_log("FFmpeg実行中...")
            # コマンドをシェル分割してExecutorに渡す
            cmd_list = shlex.split(ffmpeg_cmd)
            ret = Executor.run_command(cmd_list, self._append_log)
            if ret == 0:
                self._append_log("\n[完了] 編集済み動画の出力が完了しました。")
            else:
                self._append_log(f"\n[エラー] FFmpeg実行に失敗しました (return code={ret})")
        except Exception as e:
            self._append_log(f"[エラー] {str(e)}")

    def _append_log(self, text):
        # メインスレッドでappend
        from PySide6.QtCore import QMetaObject, Qt, Q_ARG
        QMetaObject.invokeMethod(self.log_text, "append", Qt.QueuedConnection, Q_ARG(str, text))
