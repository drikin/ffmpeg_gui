"""
オープニング動画生成コア処理
"""
import subprocess
import os
from pathlib import Path

def generate_opening(text: str, output_path: str, log_func=None) -> bool:
    """
    指定テキストを右下にフェードイン・フェードアウトで表示したオープニング動画を生成
    :param text: 埋め込みテキスト
    :param output_path: 出力ファイルパス
    :param log_func: ログ出力用関数
    :return: 成功時True
    """
    # テンプレート動画パス
    base_dir = Path(__file__).parent.parent
    template_path = str(base_dir / "assets/clip/opening.mov")
    if not os.path.exists(template_path):
        if log_func:
            log_func(f"[エラー] テンプレート動画が見つかりません: {template_path}")
        return False
    # フォントパス（OS依存。必要に応じて修正）
    font_path = "C:/Windows/Fonts/msgothic.ttc"
    if not os.path.exists(font_path):
        if log_func:
            log_func(f"[エラー] フォントファイルが見つかりません: {font_path}")
        return False
    # ffmpegフィルタ構築
    # 1.5秒からフェードイン、3秒からフェードアウト（例: 1.5s~3.0s表示）
    # drawtextフィルタのfontcolorとalpha式のクオートを修正
    # alpha指定を一旦外し、まずテキストが右下に表示されるか確認
    # fontfileパスをC:/Windows/Fonts/msgothic.ttcに統一
    # fontfile指定なし、デフォルトフォントでdrawtext
    # エピソード表示にふさわしいサイズ・右下30pxオフセット・英語フォント指定
    fontsize = 64  # オープニングにふさわしい大きめサイズ
    offset = 30    # 右下からのオフセット
    # 入力テキストをdrawtext用にエスケープ
    esc_text = text.replace("'", r"\'").replace(':', r'\:')
    drawtext = (
        f"drawtext=text='{esc_text}':x=w-tw-{offset}:y=h-th-{offset}:fontsize={fontsize}:fontcolor=white:font='Arial':shadowcolor=black:shadowx=3:shadowy=3"
    )
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-i", template_path,
        "-vf", drawtext,
        "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
        "-c:a", "aac", "-b:a", "192k",
        output_path
    ]
    # コマンド実行
    try:
        if log_func:
            log_func("ffmpegコマンド実行中...")
            log_func("実行コマンド: " + ' '.join(ffmpeg_cmd))
        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return True
        else:
            if log_func:
                log_func(f"[エラー] ffmpeg失敗: {result.stderr}")
            return False
    except Exception as e:
        if log_func:
            log_func(f"[エラー] ffmpeg実行例外: {e}")
        return False

class OpeningGenerator:
    @staticmethod
    def generate_opening(text, output_path, log_func=None):
        return generate_opening(text, output_path, log_func)
