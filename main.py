"""
アプリケーションエントリポイント
PySide6 + Draculaテーマ + サイドバー + QStackedWidget構成
"""
import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QStackedWidget, QLabel
from PySide6.QtCore import Qt
from ui_pages.loudness_page import LoudnessPage
from ui_pages.loudness_measure_page import LoudnessMeasurePage
from ui_pages.video_concat_page import VideoConcatPage
from ui_pages.slideshow_page import SlideshowPage
from ui_pages.auto_speech_extract_page import AutoSpeechExtractPage
from ui_pages.opening_generator_page import OpeningGeneratorPage  # 追加

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FFmpeg MultiTool GUI")
        self.resize(1000, 700)
        # メインレイアウト
        central_widget = QWidget()
        main_layout = QHBoxLayout(central_widget)
        # サイドバー
        sidebar = QVBoxLayout()
        self.btn_loudness = QPushButton("ラウドネス補正")
        self.btn_loudness.setObjectName("btn_loudness")
        sidebar.addWidget(self.btn_loudness)
        self.btn_measure = QPushButton("ラウドネス測定")
        self.btn_measure.setObjectName("btn_measure")
        sidebar.addWidget(self.btn_measure)
        self.btn_slideshow = QPushButton("スライドショー生成")
        self.btn_slideshow.setObjectName("btn_slideshow")
        sidebar.addWidget(self.btn_slideshow)
        # オープニング生成タブ追加（動画結合の上に挿入）
        self.btn_opening = QPushButton("オープニング生成")
        self.btn_opening.setObjectName("btn_opening")
        self.btn_concat = QPushButton("動画結合")
        self.btn_concat.setObjectName("btn_concat")
        sidebar.addWidget(self.btn_opening)
        sidebar.addWidget(self.btn_concat)
        # AI自動セリフ抽出タブ追加（全リセットの直前に移動）
        self.btn_auto_speech = QPushButton("AIトリム")
        self.btn_auto_speech.setObjectName("btn_auto_speech")
        sidebar.insertWidget(sidebar.count(), self.btn_auto_speech)
        # ストレッチを全リセットボタンの直前に追加
        sidebar.addStretch()
        # グローバルリセットボタン
        self.btn_reset = QPushButton("全リセット")
        self.btn_reset.setObjectName("btn_reset")
        self.btn_reset.clicked.connect(self.reset_all_file_lists)
        sidebar.addWidget(self.btn_reset)
        # スタックページ
        self.stack = QStackedWidget()
        self.video_concat_page = VideoConcatPage()
        self.loudness_page = LoudnessPage(concat_page=self.video_concat_page)
        self.stack.addWidget(self.loudness_page)  # ラウドネス補正
        self.loudness_measure_page = LoudnessMeasurePage()
        self.stack.addWidget(self.loudness_measure_page)  # ラウドネス測定
        self.slideshow_page = SlideshowPage()
        self.stack.addWidget(self.slideshow_page)  # スライドショー生成
        self.opening_generator_page = OpeningGeneratorPage()
        self.stack.addWidget(self.opening_generator_page)  # オープニング生成
        self.stack.addWidget(self.video_concat_page)  # 動画結合
        self.auto_speech_extract_page = AutoSpeechExtractPage()
        self.stack.addWidget(self.auto_speech_extract_page)  # AIセリフ抽出編集
        # レイアウト結合
        main_layout.addLayout(sidebar, 1)
        main_layout.addWidget(self.stack, 6)
        self.setCentralWidget(central_widget)
        # イベント接続
        self.btn_loudness.clicked.connect(lambda: self.stack.setCurrentWidget(self.loudness_page))
        self.btn_measure.clicked.connect(lambda: self.stack.setCurrentWidget(self.loudness_measure_page))
        self.btn_slideshow.clicked.connect(lambda: self.stack.setCurrentWidget(self.slideshow_page))
        self.btn_opening.clicked.connect(lambda: self.stack.setCurrentWidget(self.opening_generator_page))
        self.btn_concat.clicked.connect(lambda: self.stack.setCurrentWidget(self.video_concat_page))
        self.btn_auto_speech.clicked.connect(lambda: self.stack.setCurrentWidget(self.auto_speech_extract_page))
        # Draculaテーマ適用（必要ならQSSを読み込み）
        self.apply_dracula_theme()

    def apply_dracula_theme(self):
        # 必要に応じてQSSファイルを読み込む（ここではシンプルなダークテーマ例）
        self.setStyleSheet("""
            QWidget { background: #282a36; color: #f8f8f2; }
            QPushButton { background: #44475a; color: #f8f8f2; border-radius: 6px; padding: 8px; }
            QPushButton:hover { background: #6272a4; }
        """)

    def reset_all_file_lists(self):
        # 各ページのファイルリストをリセット
        if hasattr(self, 'slideshow_page'):
            self.slideshow_page.reset_file_list()
        if hasattr(self, 'loudness_page'):
            self.loudness_page.reset_file_list()
        if hasattr(self, 'video_concat_page'):
            self.video_concat_page.reset_file_list()
        if hasattr(self, 'loudness_measure_page'):
            self.loudness_measure_page.reset_file_list()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
