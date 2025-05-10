"""
オープニング生成ページUI
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QLineEdit, QFileDialog
from PySide6.QtCore import Qt
from core.opening_generator import OpeningGenerator
import os
import threading

class OpeningGeneratorPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        # 埋め込みテキスト入力欄
        import datetime
        # デフォルトエピソード番号生成
        base_number = 2753
        JST = datetime.timezone(datetime.timedelta(hours=9))
        now = datetime.datetime.now(JST)
        # 基準日を2025-05-09 06:00 JSTに設定
        dt_base = datetime.datetime(2025, 5, 10, 6, 0, 0, tzinfo=JST)
        # JSTでの経過日数
        days = (now.date() - dt_base.date()).days
        # JSTで6時未満なら前日分をカウント
        if now.hour < 6:
            days -= 1
        episode_number = base_number + days
        self.text_input = QLineEdit(str(episode_number))
        self.text_input.setPlaceholderText("エピソード番号などを入力")
        layout.addWidget(QLabel("埋め込みテキスト:"))
        layout.addWidget(self.text_input)
        # 出力ファイルパス
        self.edit_output = QLineEdit()
        self.edit_output.setPlaceholderText("出力ファイルパスを指定")
        layout.addWidget(QLabel("出力ファイル:"))
        layout.addWidget(self.edit_output)
        btn_select_output = QPushButton("出力ファイル選択")
        btn_select_output.clicked.connect(self.select_output)
        layout.addWidget(btn_select_output)
        # 生成ボタン
        self.btn_generate = QPushButton("オープニング生成")
        self.btn_generate.clicked.connect(self.run_generate)
        layout.addWidget(self.btn_generate)
        # ログ表示
        self.log_label = QLabel()
        self.log_label.setWordWrap(True)
        layout.addWidget(self.log_label)
        self.setLayout(layout)

    def select_output(self):
        file, _ = QFileDialog.getSaveFileName(self, "出力ファイル選択", "", "動画ファイル (*.mp4 *.mov)")
        if file:
            self.edit_output.setText(file)

    def run_generate(self):
        text = self.text_input.text().strip()
        output = self.edit_output.text().strip()
        if not text:
            self.log_label.setText("[エラー] 埋め込みテキストを入力してください")
            return
        if not output:
            self.log_label.setText("[エラー] 出力ファイルを指定してください")
            return
        self.btn_generate.setEnabled(False)
        self.log_label.setText("生成中...")
        def task():
            try:
                result = OpeningGenerator.generate_opening(text, output, self.log_label.setText)
                if result:
                    self.log_label.setText(f"[完了] {output}")
                else:
                    self.log_label.setText("[エラー] 生成に失敗しました")
            except Exception as e:
                self.log_label.setText(f"[エラー] {e}")
            finally:
                self.btn_generate.setEnabled(True)
        threading.Thread(target=task, daemon=True).start()
