import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Optional
import tempfile
import shutil
from PIL import Image, ImageDraw, ImageFont, ExifTags

class SlideshowBuilder:
    @staticmethod
    def build_ffmpeg_command(image_files: List[str], output_file: str, duration_per_image: int = 5, se_path: Optional[str] = None) -> (List[str], str, Optional[List[str]], Optional[str]):
        """
        スライドショー動画生成用ffmpegコマンドと、SE合成用コマンドも返す
        """
        list_path = Path(output_file).with_suffix('.txt')
        with open(list_path, 'w', encoding='utf-8') as f:
            # すべての画像にdurationとfileを指定
            for img in image_files:
                f.write(f"file '{img}'\n")
                f.write(f"duration {duration_per_image}\n")
            # 最後の画像はduration無しでfileだけ追加（公式推奨）
            f.write(f"file '{image_files[-1]}'\n")
        import sys, platform
        is_macos = sys.platform == "darwin"
        is_apple_silicon = is_macos and (platform.machine() == "arm64" or platform.processor() == "arm")
        # スライドショー動画生成コマンド（HWエンコーダ優先・高画質）
        if is_macos:
            # macOS: QuickTime/Final Cut Pro互換最優先（h264_videotoolbox）
            video_cmd = [
                'ffmpeg', '-y',
                '-f', 'concat', '-safe', '0',
                '-i', str(list_path),
                '-c:v', 'h264_videotoolbox',
                '-r', '30',
                '-pix_fmt', 'yuv420p',
                '-vf', 'format=yuv420p',
                '-movflags', '+faststart',
                '-an',  # 音声なしで一旦生成
                output_file
            ]
        else:
            # それ以外: libx264高画質
            video_cmd = [
                'ffmpeg', '-y',
                '-f', 'concat', '-safe', '0',
                '-i', str(list_path),
                '-vsync', 'vfr',
                '-c:v', 'libx264',
                '-crf', '18',
                '-preset', 'slow',
                '-profile:v', 'high',
                '-level', '4.2',
                '-pix_fmt', 'yuv420p',
                '-movflags', '+faststart',
                '-an',
                output_file
            ]
        # SE合成コマンド生成
        audio_cmd, audio_out = None, None
        if se_path:
            n = len(image_files)  # 各画像の頭でSEを鳴らす（画像枚数分）
            audio_out = str(Path(output_file).with_suffix('.wav'))
            inputs = []
            for _ in range(n):
                inputs += ['-i', se_path]
            adelay_filters = []
            amix_inputs = []
            for i in range(n):
                delay = i * duration_per_image * 1000
                adelay_filters.append(f"[{i}]adelay={delay}|{delay}[a{i}]")
                amix_inputs.append(f"[a{i}]")
            # 動画の長さ（秒）を先に定義
            total_duration = len(image_files) * duration_per_image
            # amixのあとにapadで無音パディングを追加（動画長まで音声を伸ばす）
            filter_complex = ";".join(adelay_filters) + ";" + "".join(amix_inputs) + f"amix=inputs={n},apad=pad_dur={total_duration}"
            audio_cmd = [
                'ffmpeg', '-y',
                *inputs,
                '-filter_complex', filter_complex,
                '-t', str(total_duration),  # 念のため音声長も明示
                audio_out
            ]
        return video_cmd, str(list_path), audio_cmd, audio_out

    @staticmethod
    def run_slideshow(image_files: List[str], output_dir: str, log_func=print, duration_per_image: int = 5, se_path: Optional[str] = None, exif_enable: bool = False) -> Optional[str]:
        """
        画像リストからスライドショー動画を4K出力・縦横比維持・最大化・黒背景で生成（Exif/SE対応）
        """
        if not image_files:
            log_func('[エラー] 画像ファイルが選択されていません')
            return None
        dt_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = str(Path(output_dir) / f'slideshow_{dt_str}.mov')  # Final Cut Pro互換性のためmov拡張子
        tmp_dir = None
        target_w, target_h = 3840, 2160  # 4K解像度
        try:
            # 4Kリサイズ＋Exif情報合成
            tmp_dir = tempfile.mkdtemp(prefix="slideshow_4k_")
            processed_images = []
            for img_path in image_files:
                try:
                    img = Image.open(img_path)
                    # 縦横比維持でリサイズ
                    iw, ih = img.size
                    scale = min(target_w / iw, target_h / ih)
                    new_w = int(iw * scale)
                    new_h = int(ih * scale)
                    resized = img.resize((new_w, new_h), Image.LANCZOS)
                    # 黒背景キャンバス
                    canvas = Image.new('RGB', (target_w, target_h), (0,0,0))
                    offset = ((target_w - new_w)//2, (target_h - new_h)//2)
                    canvas.paste(resized, offset)
                    # Exifテキスト描画
                    if exif_enable:
                        exif = img._getexif()
                        exif_dict = {}
                        if exif:
                            for tag, value in exif.items():
                                decoded = ExifTags.TAGS.get(tag, tag)
                                exif_dict[decoded] = value
                        # --- 1段目: カメラ名 / レンズ名 ---
                        camera = exif_dict.get('Model', '')
                        lens = exif_dict.get('LensModel', '') or exif_dict.get('Lens', '')
                        line1 = f"{camera} / {lens}".strip(' /')
                        # --- 2段目: 撮影パラメータ ---
                        # 焦点距離
                        focal = exif_dict.get('FocalLength')
                        if isinstance(focal, tuple):
                            focal_val = round(focal[0] / focal[1]) if focal[1] else ''
                        elif focal:
                            focal_val = round(float(focal))
                        else:
                            focal_val = ''
                        focal_str = f"{focal_val}mm" if focal_val else ''
                        # F値
                        fnum = exif_dict.get('FNumber')
                        if isinstance(fnum, tuple):
                            fnum_val = round(fnum[0] / fnum[1], 1) if fnum[1] else ''
                        elif fnum:
                            fnum_val = round(float(fnum), 1)
                        else:
                            fnum_val = ''
                        fnum_str = f"F{fnum_val}" if fnum_val else ''
                        # ISO
                        iso = exif_dict.get('ISOSpeedRatings') or exif_dict.get('PhotographicSensitivity')
                        iso_str = f"ISO{iso}" if iso else ''
                        # シャッタースピード
                        exp = exif_dict.get('ExposureTime')
                        exp_str = ''
                        if exp:
                            # tuple(分子, 分母) or float
                            if isinstance(exp, tuple):
                                num, denom = exp
                                if denom and num:
                                    val = num / denom
                                    if val < 1:
                                        exp_str = f"1/{int(round(1/val))}s"
                                    else:
                                        exp_str = f"{round(val, 3)}s"
                            else:
                                try:
                                    val = float(exp)
                                    if val < 1:
                                        exp_str = f"1/{int(round(1/val))}s"
                                    else:
                                        exp_str = f"{round(val, 3)}s"
                                except:
                                    exp_str = f"{exp}s"
                        # 2段目まとめ
                        params = [focal_str, fnum_str, iso_str, exp_str]
                        line2 = '  '.join([p for p in params if p])
                        # --- 描画（背景なし、写真の左端基準）---
                        draw = ImageDraw.Draw(canvas)
                        try:
                            font1 = ImageFont.truetype("/Library/Fonts/Arial Unicode.ttf", 28)
                            font2 = ImageFont.truetype("/Library/Fonts/Arial Unicode.ttf", 26)
                        except:
                            font1 = font2 = ImageFont.load_default()
                        bbox1 = draw.textbbox((0, 0), line1, font=font1)
                        w1, h1 = bbox1[2] - bbox1[0], bbox1[3] - bbox1[1]
                        bbox2 = draw.textbbox((0, 0), line2, font=font2)
                        w2, h2 = bbox2[2] - bbox2[0], bbox2[3] - bbox2[1]
                        margin = 80
                        spacing = 6
                        # offset: 画像が4Kキャンバス内で左上に貼られている座標
                        text_x = offset[0] + margin
                        text_y1 = target_h - margin - h2 - spacing - h1
                        text_y2 = target_h - margin - h2
                        draw.text((text_x, text_y1), line1, font=font1, fill=(255,255,255,220))
                        draw.text((text_x, text_y2), line2, font=font2, fill=(255,255,255,220))
                        out_img_path = str(Path(tmp_dir) / Path(img_path).name)
                        canvas.save(out_img_path)
                        processed_images.append(out_img_path)
                    else:
                        out_img_path = str(Path(tmp_dir) / Path(img_path).name)
                        canvas.save(out_img_path)
                        processed_images.append(out_img_path)
                except Exception as e:
                    log_func(f"[WARN] 4K変換/Exif埋め込み失敗: {img_path} ({e})")
                    processed_images.append(img_path)
            image_files_for_video = processed_images
            video_cmd, list_path, audio_cmd, audio_out = SlideshowBuilder.build_ffmpeg_command(
                image_files_for_video, output_file, duration_per_image, se_path)
            log_func('[INFO] スライドショー動画生成コマンド: ' + ' '.join(video_cmd))
            proc_v = subprocess.run(video_cmd, capture_output=True, text=True)
            if proc_v.returncode != 0:
                log_func('[エラー] 動画生成失敗: ' + proc_v.stderr)
                return None
            if se_path and audio_cmd:
                log_func('[INFO] SE合成コマンド: ' + ' '.join(audio_cmd))
                proc_a = subprocess.run(audio_cmd, capture_output=True, text=True)
                if proc_a.returncode != 0:
                    log_func('[エラー] SE合成失敗: ' + proc_a.stderr)
                    return None
                final_out = str(Path(output_file).with_suffix('.mux.mov'))
                mux_cmd = [
                    'ffmpeg', '-y',
                    '-i', output_file,
                    '-i', audio_out,
                    '-c:v', 'copy',
                    '-c:a', 'aac',
                    '-shortest',
                    '-movflags', '+faststart',
                    final_out
                ]
                log_func('[INFO] 動画+SE muxコマンド: ' + ' '.join(mux_cmd))
                proc_m = subprocess.run(mux_cmd, capture_output=True, text=True)
                if proc_m.returncode == 0:
                    log_func(f'[完了] スライドショー動画生成成功: {final_out}')
                    return final_out
                else:
                    log_func('[エラー] mux失敗: ' + proc_m.stderr)
                    return None
            else:
                # --- 無音AAC音声ストリームを自動生成しmux（Final Cut Pro互換性向上） ---
                silent_audio = str(Path(output_file).with_suffix('.silent.m4a'))
                duration_sec = len(image_files_for_video) * duration_per_image
                gen_silence_cmd = [
                    'ffmpeg', '-y', '-f', 'lavfi', '-i', f'anullsrc=channel_layout=stereo:sample_rate=44100',
                    '-t', str(duration_sec), '-c:a', 'aac', '-b:a', '192k', silent_audio
                ]
                log_func('[INFO] 無音AAC音声生成コマンド: ' + ' '.join(gen_silence_cmd))
                proc_silence = subprocess.run(gen_silence_cmd, capture_output=True, text=True)
                if proc_silence.returncode != 0:
                    log_func('[エラー] 無音音声生成失敗: ' + proc_silence.stderr)
                    return None
                # 動画と無音音声をmux
                final_out = str(Path(output_file).with_suffix('.mux.mov'))
                mux_cmd = [
                    'ffmpeg', '-y',
                    '-i', output_file,
                    '-i', silent_audio,
                    '-c:v', 'copy',
                    '-c:a', 'aac',
                    '-shortest',
                    '-movflags', '+faststart',
                    final_out
                ]
                log_func('[INFO] 動画+無音音声muxコマンド: ' + ' '.join(mux_cmd))
                proc_m = subprocess.run(mux_cmd, capture_output=True, text=True)
                if proc_m.returncode == 0:
                    log_func(f'[完了] スライドショー動画生成成功: {final_out}')
                    return final_out
                log_func('[エラー] mux失敗: ' + proc_m.stderr)
                return None
        finally:
            # 中間生成ファイルのクリーンアップ
            if tmp_dir and Path(tmp_dir).exists():
                shutil.rmtree(tmp_dir)
            if 'list_path' in locals() and Path(list_path).exists():
                Path(list_path).unlink()
            # 無音音声
            silent_audio_path = Path(output_file).with_suffix('.silent.m4a')
            if silent_audio_path.exists():
                silent_audio_path.unlink()
            # SE合成音声
            if 'audio_out' in locals() and audio_out and Path(audio_out).exists():
                Path(audio_out).unlink()
            # SE合成時のmux前動画
            mux_mov = Path(output_file)
            if mux_mov.exists():
                mux_mov.unlink()
            # .txtファイルも念のため削除
            txt_path = Path(output_file).with_suffix('.txt')
            if txt_path.exists():
                txt_path.unlink()

# TODO: Exif情報埋め込みやSE追加など拡張ポイントはここに実装予定
