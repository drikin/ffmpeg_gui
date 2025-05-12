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
        前半・中盤・後半の3点でラウドネス値（LUFS, LRA, TPなど）をサンプリングし平均値を返す
        戻り値: (平均測定値dict, ffmpegのstderr全文)
        """
        import subprocess, json, re
        # --- 動画全体の長さ（秒）を取得 ---
        try:
            ffprobe_cmd = [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", str(input_path)
            ]
            duration_result = subprocess.run(ffprobe_cmd, capture_output=True, text=True, timeout=10)
            total_duration = float(duration_result.stdout.strip())
        except Exception as e:
            return None, f"duration取得失敗: {e}"

        # --- サンプリング位置を決定（前半0s, 中盤, 後半-60s） ---
        sample_length = 60.0
        positions = [0.0, max((total_duration - sample_length) / 2, 0), max(total_duration - sample_length, 0)]
        results = []
        stderrs = []
        for ss in positions:
            # ffmpeg loudnormで各区間を測定
            cmd = [
                "ffmpeg", "-hide_banner", "-nostats", "-ss", str(ss), "-i", str(input_path),
                "-t", str(sample_length),
                "-af", "loudnorm=I=-23:TP=-1.5:LRA=7:print_format=json",
                "-f", "null", "-"
            ]
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
                out = proc.stderr
                stderrs.append(out)
                m = re.search(r'\{[\s\S]+?\}', out)
                if m:
                    loudness_json = json.loads(m.group(0))
                    results.append(loudness_json)
            except Exception as e:
                stderrs.append(str(e))

        if not results:
            return None, '\n'.join(stderrs)

        # --- 各値を平均化 ---
        keys = [
            "input_i", "input_tp", "input_lra", "input_thresh",
            "output_i", "output_tp", "output_lra", "output_thresh", "target_offset"
        ]
        avg = {}
        for k in keys:
            vals = [float(r.get(k, 0)) for r in results if k in r]
            avg[k] = sum(vals) / len(vals) if vals else 0.0
        return avg, '\n'.join(stderrs)

