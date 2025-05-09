"""
ffprobeによるラウドネス測定ユーティリティ
"""
import subprocess
import json
from pathlib import Path
from typing import Dict, Optional, Tuple

class FFprobeLoudness:
    @staticmethod
    def is_silent(input_path: Path, threshold_db: float = -90.0) -> bool:
        """
        音声が完全無音か判定（max_volumeがthreshold_db未満なら無音とみなす）
        """
        import subprocess, re
        cmd = [
            "ffmpeg", "-y", "-i", str(input_path),
            "-af", "volumedetect", "-f", "null", "-"
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            out = proc.stderr
            m = re.search(r"max_volume: ([\-\d\.]+) dB", out)
            if m:
                max_vol = float(m.group(1))
                return max_vol < threshold_db
        except Exception:
            pass
        return False

    @staticmethod
    def has_audio_stream(input_path: Path) -> bool:
        """
        指定ファイルに音声ストリームが存在するか判定
        """
        import subprocess, json
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=index",
            "-of", "json", str(input_path)
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            info = json.loads(result.stdout)
            return bool(info.get('streams'))
        except Exception:
            return False

    @staticmethod
    def measure_loudness(input_path: Path) -> Optional[Tuple[Dict[str, float], str]]:
        """
        ffmpegのloudnormフィルタを使い、ラウドネス値（LUFS, LRA, TPなど）を抽出
        戻り値: (測定値dict, ffmpegのstderr全文)
        """
        import subprocess, json, re
        cmd = [
            "ffmpeg", "-hide_banner", "-nostats", "-i", str(input_path),
            "-af", "loudnorm=I=-23:TP=-1.5:LRA=7:print_format=json",
            "-f", "null", "-"
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            out = proc.stderr
            m = re.search(r'\{[\s\S]+?\}', out)
            if m:
                loudness_json = json.loads(m.group(0))
                return {
                    "input_i": float(loudness_json.get("input_i", 0)),
                    "input_tp": float(loudness_json.get("input_tp", 0)),
                    "input_lra": float(loudness_json.get("input_lra", 0)),
                    "input_thresh": float(loudness_json.get("input_thresh", 0)),
                    "output_i": float(loudness_json.get("output_i", 0)),
                    "output_tp": float(loudness_json.get("output_tp", 0)),
                    "output_lra": float(loudness_json.get("output_lra", 0)),
                    "output_thresh": float(loudness_json.get("output_thresh", 0)),
                    "target_offset": float(loudness_json.get("target_offset", 0)),
                }, out
            else:
                return None, out
        except Exception as e:
            return None, str(e)
        return None
