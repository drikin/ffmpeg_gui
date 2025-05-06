"""
ffprobeによるラウドネス測定ユーティリティ
"""
import subprocess
import json
from pathlib import Path
from typing import Dict, Optional

class FFprobeLoudness:
    @staticmethod
    def measure_loudness(input_path: Path) -> Optional[Dict[str, float]]:
        """
        ffmpegのloudnormフィルタを使い、ラウドネス値（LUFS, LRA, TPなど）を抽出
        Returns: dict or None
        """
        cmd = [
            "ffmpeg", "-hide_banner", "-i", str(input_path),
            "-af", "loudnorm=I=-14:TP=-2:LRA=7:print_format=json",
            "-f", "null", "-"
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            out = proc.stderr
            # loudnormのjson出力部分を抽出
            start = out.find('{')
            end = out.rfind('}') + 1
            if start != -1 and end != -1:
                data = json.loads(out[start:end])
                return {
                    "input_i": float(data.get("input_i", 0)),
                    "input_tp": float(data.get("input_tp", 0)),
                    "input_lra": float(data.get("input_lra", 0)),
                    "input_thresh": float(data.get("input_thresh", 0)),
                    "output_i": float(data.get("output_i", 0)),
                    "output_tp": float(data.get("output_tp", 0)),
                    "output_lra": float(data.get("output_lra", 0)),
                    "output_thresh": float(data.get("output_thresh", 0)),
                    "target_offset": float(data.get("target_offset", 0)),
                }
        except Exception as e:
            return None
        return None
