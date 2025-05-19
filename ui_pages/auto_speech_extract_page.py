"""
AI自動セリフ抽出＆クロスフェード編集ページUI
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit, QFileDialog, QTextEdit, QCheckBox, QComboBox
from PySide6.QtCore import Qt, Signal, QSettings
from core.speech_segment_extractor import SpeechSegmentExtractor
from core.executor import Executor
import os
import threading
import shlex
import tempfile

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

        from PySide6.QtWidgets import QSpacerItem, QSizePolicy

        # ...（中略: 他UI部品の定義）...

        # ログ表示エリア
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(200)  # 最小高さを設定
        layout.addWidget(self.log_text, stretch=1)  # 伸縮可能に

        # Whisperワードレベル解析ON/OFF
        self.chk_word_level = QCheckBox("ワードレベルで解析する（word_timestamps）")
        self.chk_word_level.setChecked(self.settings.value("word_level", False, type=bool))
        layout.addWidget(self.chk_word_level)

        # OpenAI APIキー入力欄
        api_key_layout = QHBoxLayout()
        api_key_label = QLabel("OpenAI APIキー（Whisper API用、省略可）:")
        self.edit_api_key = QLineEdit()
        self.edit_api_key.setPlaceholderText("sk-...（入力した値は保存されます）")
        self.edit_api_key.setEchoMode(QLineEdit.Password)
        api_key = self.settings.value("openai_api_key", "", type=str)
        self.edit_api_key.setText(api_key)
        api_key_layout.addWidget(api_key_label)
        api_key_layout.addWidget(self.edit_api_key)
        layout.addLayout(api_key_layout)

        # 入力ファイル選択UI（横並び）
        file_layout = QHBoxLayout()
        file_label = QLabel("入力動画ファイル:")
        self.edit_file = QLineEdit()
        self.edit_file.setReadOnly(True)
        btn_select_file = QPushButton("動画ファイル選択")
        btn_select_file.clicked.connect(self.select_file)
        file_layout.addWidget(file_label)
        file_layout.addWidget(self.edit_file)
        file_layout.addWidget(btn_select_file)
        layout.addLayout(file_layout)

        # セリフ間隔しきい値入力UI（横並び）
        merge_gap_layout = QHBoxLayout()
        merge_gap_label = QLabel("セリフ間隔しきい値（秒）:")
        self.edit_merge_gap = QLineEdit("0.0")
        self.edit_merge_gap.setPlaceholderText("例: 3.0")
        self.edit_merge_gap.setText(str(self.settings.value("merge_gap_sec", 0.0, type=float)))
        merge_gap_layout.addWidget(merge_gap_label)
        merge_gap_layout.addWidget(self.edit_merge_gap)
        layout.addLayout(merge_gap_layout)

        # 言語選択コンボボックス（Whisper認識言語）
        lang_layout = QHBoxLayout()
        lang_label = QLabel("Whisper認識言語:")
        self.combo_language = QComboBox()
        self.combo_language.addItem("日本語（デフォルト）", "ja")
        self.combo_language.addItem("自動判定", "auto")
        self.combo_language.addItem("英語", "en")
        self.combo_language.setCurrentIndex(0)
        lang_layout.addWidget(lang_label)
        lang_layout.addWidget(self.combo_language)
        layout.addLayout(lang_layout)

        # Whisperモデル選択
        model_layout = QHBoxLayout()
        model_label = QLabel("Whisperモデル:")
        self.combo_model = QComboBox()
        self.combo_model.addItem("base (高速, 低精度)", "base")
        self.combo_model.addItem("small (推奨)", "small")
        self.combo_model.addItem("medium (高精度, 遅い)", "medium")
        self.combo_model.addItem("large-v3 (最高精度, 非常に遅い)", "large-v3")
        # 保存されているモデルを読み込み、デフォルトはsmall
        saved_model = self.settings.value("whisper_model", "small", type=str)
        index = self.combo_model.findData(saved_model)
        if index >= 0:
            self.combo_model.setCurrentIndex(index)
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.combo_model)
        layout.addLayout(model_layout)

        # 出力ファイル選択UI（横並び）
        output_layout = QHBoxLayout()
        output_label = QLabel("出力ファイル:")
        self.edit_output = QLineEdit()
        self.edit_output.setReadOnly(True)
        btn_select_output = QPushButton("出力ファイル選択")
        btn_select_output.clicked.connect(self.select_output)
        output_layout.addWidget(output_label)
        output_layout.addWidget(self.edit_output)
        output_layout.addWidget(btn_select_output)
        layout.addLayout(output_layout)

        # 外部SRTファイル指定UI（横並び）
        srt_layout = QHBoxLayout()
        srt_label = QLabel("外部SRTファイル（指定時は音声認識せずトリム）:")
        self.edit_srt = QLineEdit()
        self.edit_srt.setReadOnly(True)
        btn_select_srt = QPushButton("SRTファイル選択（任意）")
        btn_select_srt.clicked.connect(self.select_srt_file)
        srt_layout.addWidget(srt_label)
        srt_layout.addWidget(self.edit_srt)
        srt_layout.addWidget(btn_select_srt)
        layout.addLayout(srt_layout)

        # 実行ボタン
        self.btn_run = QPushButton("AIジェットカット")
        self.btn_run.clicked.connect(self.run_extract)
        layout.addWidget(self.btn_run, alignment=Qt.AlignBottom)  # 下部に配置

    def select_srt_file(self):
        file, _ = QFileDialog.getOpenFileName(self, "SRTファイル選択", "", "字幕ファイル (*.srt)")
        if file:
            self.srt_path = file
            self.edit_srt.setText(file)
        else:
            self.srt_path = None
            self.edit_srt.setText("")

    def set_input_file(self, file_path):
        """Set the input file programmatically
        
        Args:
            file_path (str): Path to the input file
        """
        self.file_path = file_path
        self.edit_file.setText(file_path)
        # オリジナルファイル名+_trim.mp4 をデフォルト出力ファイル名に設定
        base, ext = os.path.splitext(file_path)
        default_output = base + '_trim.mp4'
        self.output_path = default_output
        self.edit_output.setText(default_output)
        
    def select_file(self):
        file, _ = QFileDialog.getOpenFileName(self, "動画ファイル選択", "", "動画ファイル (*.mp4 *.mov *.mkv *.avi)")
        if file:
            self.set_input_file(file)

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
            merge_gap_sec = 0.0
        self._merge_gap_sec = merge_gap_sec
        
        # 言語設定を取得
        language = self.combo_language.currentData()
        self._language = language
        
        # word_timestampsオプション
        word_level = self.chk_word_level.isChecked()
        self._word_level = word_level
        
        # モデル選択
        model = self.combo_model.currentData()
        self._model = model
        
        # APIキー保存
        api_key = self.edit_api_key.text().strip()
        self.settings.setValue("openai_api_key", api_key)
        self.settings.setValue("word_level", word_level)
        self.settings.setValue("whisper_model", model)
        self._api_key = api_key
        
        # ログをクリアして新しい処理開始を表示
        self.log_text.clear()
        
        # SRTファイルが指定されているかチェック
        srt_path = self.edit_srt.text().strip()
        if srt_path and os.path.exists(srt_path):
            self.srt_path = srt_path
            self.log_text.append(f"=== 外部SRTファイルを使用します ===")
            self.log_text.append(f"SRTファイル: {srt_path}")
            self.log_text.append(f"セリフ間隔しきい値: {merge_gap_sec}秒")
            self.log_text.append("-" * 50)
            
            # SRTファイルから直接セグメントを抽出
            threading.Thread(target=self._process_srt_file, daemon=True).start()
        else:
            # 前回の結果をクリア
            self.srt_path = None
            self.segments = []
            self.log_text.append(f"=== 新しい音声認識を開始します ===")
            self.log_text.append(f"モデル: {model}, 言語: {self.combo_language.currentText()}, ワードレベル: {'ON' if word_level else 'OFF'}")
            self.log_text.append(f"セリフ間隔しきい値: {merge_gap_sec}秒")
            self.log_text.append("-" * 50)
            
            # Whisperで音声認識を実行
            self.log_text.append(f"Whisperで音声認識を開始します...")
            threading.Thread(target=self._run_extract_task, daemon=True).start()
    
    def _process_srt_file(self):
        """外部SRTファイルを処理する"""
        try:
            merge_gap_sec = getattr(self, '_merge_gap_sec', 0.0)
            
            # SRTファイルをパースしてセグメントを取得
            self._append_log(f"SRTファイルを解析中: {self.srt_path}")
            self.segments = self.extractor.parse_srt_segments(
                self.srt_path, 
                merge_gap_sec=merge_gap_sec, 
                reference_media_path=self.file_path
            )
            
            if not self.segments:
                self._append_log("[エラー] 有効なセグメントが見つかりませんでした")
                return
                
            # セグメント情報をログに出力
            self._log_segment_info()
            
            # FFmpegコマンドを実行
            self._execute_ffmpeg_command()
            
        except Exception as e:
            self._append_log(f"[エラー] SRTファイルの処理中にエラーが発生しました: {str(e)}")
    
    def _log_segment_info(self):
        """セグメント情報をログに出力する"""
        # セグメント情報をログに出力
        self._append_log("\n[セリフ区間リスト]")
        for i, (st, ed) in enumerate(self.segments, 1):
            self._append_log(f"  {i:2d}. {st:7.2f}秒 ～ {ed:7.2f}秒  (長さ: {ed-st:6.2f}秒)")
        
        # 元動画の長さを取得
        try:
            import subprocess, re
            cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", 
                  "-of", "default=noprint_wrappers=1:nokey=1", self.file_path]
            out = subprocess.check_output(cmd, encoding="utf-8", errors="ignore").strip()
            original_duration = float(re.findall(r"[\d.]+", out)[0])
            
            # トリム後の合計時間を計算
            total_trimmed = sum(ed - st for st, ed in self.segments)
            
            # トリム情報をログに出力
            self._append_log("\n=== トリム情報 ===")
            self._append_log(f"・元動画の長さ: {original_duration:.2f}秒")
            self._append_log(f"・トリム後の長さ: {total_trimmed:.2f}秒")
            self._append_log(f"・削除された合計時間: {original_duration - total_trimmed:.2f}秒")
            
        except Exception as e:
            self._append_log(f"[警告] 動画情報の取得中にエラーが発生しました: {e}")


    def _run_extract_task(self):
        """Whisperを使用して音声認識を実行する"""
        try:
            language = getattr(self, '_language', 'ja')
            word_level = getattr(self, '_word_level', False)
            model = getattr(self, '_model', 'small')
            api_key = getattr(self, '_api_key', None)
            merge_gap_sec = getattr(self, '_merge_gap_sec', 0.0)
            
            # 毎回新しいextractorインスタンスを作成してモデルを初期化
            self.extractor = SpeechSegmentExtractor(whisper_model=model)
            self._append_log(f"[INFO] Whisperモデル '{model}' を初期化中...")

            # 常に新しい一時ファイルを作成して使用（前回の結果を上書き）
            with tempfile.NamedTemporaryFile(suffix='.srt', delete=False) as temp_srt:
                srt_path = temp_srt.name
            
            # ログ出力用のコールバック関数
            def log_callback(msg):
                # Whisperのログや進捗情報をアプリのログエリアに表示
                if (msg.startswith("  ") or 
                    "Whisper" in msg or 
                    "セリフ区間リスト" in msg or 
                    "再生時間" in msg or 
                    "元動画:" in msg or 
                    "切り取り後" in msg or 
                    "差分" in msg or
                    "認識中" in msg or
                    "モデル" in msg or
                    "完了" in msg or
                    "エラー" in msg.lower() or
                    "warn" in msg.lower() or
                    "info" in msg.lower()):
                    self._append_log(msg)
                # その他の詳細なログはデバッグ情報としてコンソールにのみ出力
                else:
                    print(f"[Whisper] {msg}")
            
            self._append_log(f"Whisperで音声認識を開始します...")
            self._append_log(f"モデル: {model}, 言語: {self.combo_language.currentText()}, ワードレベル: {'ON' if word_level else 'OFF'}")
            self._append_log(f"セリフ間隔しきい値: {merge_gap_sec}秒")
            
            try:
                # Whisperで音声認識を実行
                srt_path = self.extractor.transcribe_to_srt(
                    self.file_path, srt_path,
                    language=language,
                    log_func=log_callback,
                    word_level=word_level,
                    api_key=api_key,
                    model=model,
                    merge_gap_sec=merge_gap_sec
                )
                
                # セグメント情報を取得
                self.segments = self.extractor.parse_srt_segments(
                    srt_path, 
                    merge_gap_sec=merge_gap_sec, 
                    reference_media_path=self.file_path
                )
                
                if not self.segments:
                    self._append_log("[エラー] 有効なセグメントが見つかりませんでした")
                    return
                
                # セグメント情報をログに出力
                self._log_segment_info()
                
                # FFmpegコマンドを実行
                self._execute_ffmpeg_command()
                
            except Exception as e:
                self._append_log(f"[エラー] 音声認識中にエラーが発生しました: {str(e)}")
                raise
                
        except Exception as e:
            self._append_log(f"[エラー] {str(e)}")
    
    def _execute_ffmpeg_command(self):
        """FFmpegコマンドを実行する"""
        try:
            self._append_log(f"\nセグメント抽出完了: {len(self.segments)}区間\nFFmpegコマンド生成中...")
            
            # FFmpegコマンドを生成
            ffmpeg_cmd = self.extractor.build_ffmpeg_commands(
                self.file_path, 
                self.segments, 
                self.output_path
            )
            
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
            self._append_log(f"[エラー] FFmpegコマンドの実行中にエラーが発生しました: {str(e)}")

    def _append_log(self, text):
        # メインスレッドでappend
        from PySide6.QtCore import QMetaObject, Qt, Q_ARG
        QMetaObject.invokeMethod(self.log_text, "append", Qt.QueuedConnection, Q_ARG(str, text))
