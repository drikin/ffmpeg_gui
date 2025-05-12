"""
AI自動セリフ抽出＆クロスフェード編集ページUI
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QLineEdit, QFileDialog, QTextEdit, QCheckBox
from PySide6.QtCore import Qt, Signal, QSettings
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
        self.settings = QSettings("drikin", "ffmpeg_gui")

        # Whisperワードレベル解析ON/OFF
        self.chk_word_level = QCheckBox("ワードレベルで解析する（word_timestamps）")
        self.chk_word_level.setChecked(self.settings.value("word_level", False, type=bool))
        layout.addWidget(self.chk_word_level)

        # OpenAI APIキー入力欄
        layout.addWidget(QLabel("OpenAI APIキー（Whisper API用、省略可）:"))
        self.edit_api_key = QLineEdit()
        self.edit_api_key.setPlaceholderText("sk-...（入力した値は保存されます）")
        self.edit_api_key.setEchoMode(QLineEdit.Password)
        api_key = self.settings.value("openai_api_key", "", type=str)
        self.edit_api_key.setText(api_key)
        layout.addWidget(self.edit_api_key)

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

        # セリフ間隔しきい値入力欄（秒）を追加
        self.edit_merge_gap = QLineEdit()
        self.edit_merge_gap.setPlaceholderText("0")
        self.edit_merge_gap.setText("0")  # デフォルト値
        layout.addWidget(QLabel("セリフ間隔しきい値（秒、デフォルト3.0）:"))
        layout.addWidget(self.edit_merge_gap)

        # 言語選択コンボボックスを追加
        from PySide6.QtWidgets import QComboBox
        self.combo_language = QComboBox()
        self.combo_language.addItem("日本語（デフォルト）", "ja")
        self.combo_language.addItem("自動判定", "auto")
        self.combo_language.addItem("英語", "en")
        self.combo_language.setCurrentIndex(0)
        layout.addWidget(QLabel("Whisper認識言語:"))
        layout.addWidget(self.combo_language)

        # 実行ボタン
        btn_run = QPushButton("AIジェットカット")
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
            # オリジナルファイル名+_trim.mp4 をデフォルト出力ファイル名に設定
            base, ext = os.path.splitext(file)
            default_output = base + '_trim.mp4'
            self.output_path = default_output
            self.edit_output.setText(default_output)

    def select_output(self):
        file, _ = QFileDialog.getSaveFileName(self, "出力ファイル選択", self.output_path if self.output_path else "", "動画ファイル (*.mp4)")
        if file:
            self.output_path = file
            self.edit_output.setText(file)

    def run_extract(self):
        if not self.file_path or not self.output_path:
            self.log_text.append("入力・出力ファイルを選択してください")
            return
        # セリフ間隔しきい値（秒）を取得
        try:
            merge_gap_sec = float(self.edit_merge_gap.text())
        except Exception:
            merge_gap_sec = 3.0
        self._merge_gap_sec = merge_gap_sec
        # 言語設定を取得
        language = self.combo_language.currentData()
        self._language = language
        # word_timestampsオプション
        word_level = self.chk_word_level.isChecked()
        self._word_level = word_level
        # APIキー保存
        api_key = self.edit_api_key.text().strip()
        self.settings.setValue("openai_api_key", api_key)
        self.settings.setValue("word_level", word_level)
        self._api_key = api_key
        self.log_text.append(f"Whisperで音声認識中...（セリフ間隔しきい値: {merge_gap_sec}秒, 言語: {self.combo_language.currentText()}、ワードレベル: {'ON' if word_level else 'OFF'}）")
        threading.Thread(target=self._run_extract_task, daemon=True).start()


    def _run_extract_task(self):
        try:
            language = getattr(self, '_language', 'ja')
            word_level = getattr(self, '_word_level', False)
            api_key = getattr(self, '_api_key', None)
            srt_path = self.extractor.transcribe_to_srt(self.file_path, language=language, word_timestamps=word_level, api_key=api_key)
            self.srt_path = srt_path
            # SRTファイルの内容をログ出力
            try:
                with open(srt_path, "r", encoding="utf-8") as f:
                    srt_content = f.read()
                self._append_log(f"SRT生成完了: {srt_path}\n--- SRT内容 ---\n{srt_content}\n--- END ---\nセグメント抽出中...")
            except Exception as e:
                self._append_log(f"SRT生成完了: {srt_path}\n[SRT内容の読込失敗: {e}]\nセグメント抽出中...")
            # セリフ間隔しきい値をparse_srt_segmentsに渡す
            merge_gap_sec = getattr(self, '_merge_gap_sec', 3.0)
            segments = self.extractor.parse_srt_segments(srt_path, merge_gap_sec=merge_gap_sec)
            self.segments = segments
            self._append_log(f"セグメント抽出完了: {len(segments)}区間\nFFmpegコマンド生成中...")

            ffmpeg_cmd = self.extractor.build_ffmpeg_commands(self.file_path, segments, self.output_path)
            # build_ffmpeg_commandsが複数コマンドリストを返す場合に対応
            cmds = ffmpeg_cmd
            if isinstance(cmds, (list, tuple)) and len(cmds) > 0 and isinstance(cmds[0], list):
                # コマンドリストのリスト（複数候補）
                success = False
                for idx, cmd in enumerate(cmds):
                    self._append_log(f"コマンド候補{idx+1}: {' '.join(cmd)}")
                    self._append_log("FFmpeg実行中...")
                    ret = Executor.run_command(cmd, self._append_log)
                    if ret == 0:
                        self._append_log("\n[完了] 編集済み動画の出力が完了しました。")
                        success = True
                        break
                    else:
                        self._append_log(f"\n[エラー] FFmpeg実行に失敗しました (return code={ret})")
                if not success:
                    self._append_log("[エラー] すべてのエンコーダでFFmpeg実行に失敗しました")
            else:
                # 1コマンドのみ（従来通り）
                if isinstance(cmds, list):
                    self._append_log(f"コマンド生成完了\n{' '.join(cmds)}")
                    cmd_list = cmds
                else:
                    self._append_log(f"コマンド生成完了\n{cmds}")
                    cmd_list = shlex.split(cmds)
                self._append_log("FFmpeg実行中...")
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
