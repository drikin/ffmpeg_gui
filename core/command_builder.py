"""
ffmpegコマンド生成モジュール（ラウドネス補正用）
"""
from pathlib import Path
from typing import Optional

class CommandBuilder:
    """
    ffmpegコマンド生成クラス
    """
    @staticmethod
    def build_loudness_normalization_cmd(input_path: Path, output_path: Path, use_dynaudnorm: bool = True) -> list:
        """
        ffmpeg 7.1.1以降のラウドネス補正コマンドを生成
        -14LUFS/YouTube基準
        use_dynaudnorm: Trueでdynaudnorm併用、Falseでloudnormのみ
        """
        if use_dynaudnorm:
            af = "dynaudnorm=f=250:g=15:p=0.95:m=5:r=0.0:n=1,loudnorm=I=-14:LRA=7:TP=-2"
        else:
            af = "loudnorm=I=-14:LRA=7:TP=-2"
        return [
            "ffmpeg",
            "-y",
            "-i", str(input_path),
            "-af", af,
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            str(output_path)
        ]
