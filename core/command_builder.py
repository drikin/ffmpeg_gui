"""
ffmpegコマンド生成モジュール（ラウドネス補正用）
"""
from pathlib import Path
from typing import Optional
import subprocess
import json

class CommandBuilder:
    """
    ffmpegコマンド生成クラス
    """
    @staticmethod
    def build_loudness_normalization_cmd(input_path: Path, output_path: Path, use_dynaudnorm: bool = True, material_mode: bool = False) -> list:
        """
        ffmpeg 7.1.1以降のラウドネス補正コマンドを生成
        -14LUFS/YouTube基準
        use_dynaudnorm: Trueでdynaudnorm併用、Falseでloudnormのみ
        material_mode: Trueで素材用（-23LUFS/TP-1/LRA=11/linear）
        """
        if material_mode:
            af = "loudnorm=I=-23:LRA=11:TP=-1:linear=true:print_format=summary"
        elif use_dynaudnorm:
            af = "dynaudnorm=f=250:g=15:p=0.95:m=5:r=0.0:n=1,loudnorm=I=-14:LRA=7:TP=-2:print_format=summary"
        else:
            af = "loudnorm=I=-14:LRA=7:TP=-2:print_format=summary"
        return [
            "ffmpeg",
            "-y",
            "-i", str(input_path),
            "-af", af,
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-map_metadata", "0",
            str(output_path)
        ]

    @staticmethod
    def get_video_format_info(file_path: str) -> dict:
        """
        ffprobeで主要な動画プロパティ（コーデック・解像度・フレームレート等）を取得
        """
        cmd = [
            "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
            "stream=codec_name,width,height,r_frame_rate,pix_fmt", "-of", "json", file_path
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            info = json.loads(result.stdout)
            stream = info['streams'][0] if 'streams' in info and info['streams'] else {}
            return {
                'codec_name': stream.get('codec_name'),
                'width': stream.get('width'),
                'height': stream.get('height'),
                'r_frame_rate': stream.get('r_frame_rate'),
                'pix_fmt': stream.get('pix_fmt'),
            }
        except Exception as e:
            return {'error': str(e)}

    @staticmethod
    def build_video_concat_cmd(input_files: list, output_path: Path) -> tuple:
        """
        ffmpeg concat demuxer用のコマンド生成
        - input_files: 結合対象ファイルのパスリスト
        - output_path: 出力ファイルパス
        戻り値: (コマンドリスト, 一時リストファイルパス, 再エンコード有無[bool], フォーマット判定情報, 強制再エンコード理由)
        """
        # 各ファイルのフォーマット取得
        format_list = [CommandBuilder.get_video_format_info(f) for f in input_files]
        ref = format_list[0]
        need_reencode = False
        force_reason = None
        reencode_reasons = []
        for idx, fmt in enumerate(format_list[1:], 1):
            # 主要プロパティが全て一致しているか
            for k in ['codec_name', 'width', 'height', 'r_frame_rate', 'pix_fmt']:
                if fmt.get(k) != ref.get(k):
                    need_reencode = True
                    reencode_reasons.append(f"{k}不一致: {input_files[0]}={ref.get(k)}, {input_files[idx]}={fmt.get(k)}")
            if need_reencode:
                break
        # 出力ファイル拡張子によるmux可否チェック
        ext = output_path.suffix.lower()
        # proresはmovでのみ-mux可能
        if not need_reencode and ref.get('codec_name') == 'prores' and ext != '.mov':
            need_reencode = True
            force_reason = 'proresコーデックはmp4コンテナにコピー不可のため再エンコードを強制します'
        elif need_reencode and not force_reason:
            force_reason = ' / '.join(reencode_reasons) if reencode_reasons else '動画プロパティ不一致のため再エンコードを強制します'

        import tempfile
        concat_list = tempfile.NamedTemporaryFile(delete=False, mode='w', encoding='utf-8', suffix='.txt')
        for f in input_files:
            concat_list.write(f"file '{str(Path(f).absolute())}'\n")
        concat_list.close()

        if not need_reencode:
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_list.name,
                "-c", "copy",
                str(output_path)
            ]
        else:
            # filter_complex方式でコマンド生成
            # 入力ファイルをすべて -i で指定
            cmd = ["ffmpeg", "-y"]
            for f in input_files:
                cmd += ["-i", str(f)]
            n = len(input_files)
            # 映像・音声両方concatする
            filter_complex = f"concat=n={n}:v=1:a=1 [outv][outa]"
            cmd += [
                "-filter_complex", filter_complex,
                "-map", "[outv]",
                "-map", "[outa]",
                "-c:v", "h264_videotoolbox",
                "-c:a", "aac",
                str(output_path)
            ]
        return cmd, concat_list.name, need_reencode, format_list, force_reason
