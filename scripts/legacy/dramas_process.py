
# run_all_in_one_end_at_episode_A.py  (方案A：计时日志 + 提速选项)
# 变更要点：
# 1) 全链路计时：片段规范化/拼接/封面/尾部缓存/整条素材/整部剧/探测 都有耗时日志；>=60s 自动转“分钟”。
# 2) 关键日志：
#    - "✅ 素材完成 | 剧：{name} | 第 {i} 条 | 用时 ... | 该剧剩余素材：{remain} 条"
#    - 片段级完成 + 本素材剩余片段数；剧级统计；全局统计；错误打印。
# 3) 提速选项：
#    - --smart-fps: 自适应帧率（默认开）: 源<40fps 用源帧率；否则封顶45fps（比 60 更省时）。
#    - --fast-mode: 关闭 eq/hue 随机色彩扰动滤镜，仅保留缩放/裁切/填充与文字（更快）。
#    - fast_bilinear 缩放：通过 -sws_flags fast_bilinear。
#    - 并行滤镜：-filter_threads/-filter_complex_threads（默认=CPU核数的一半，>=2）。
#    - 硬编补充：-profile:v high -level 4.2 -tag:v avc1；软编同样指定 -profile/level。
#
# 原始功能（交互、多选、尾部缓存、封面等）全部保留；CLI 兼容且新增参数向后兼容。

import os, sys, glob, argparse, subprocess, shlex, math, tempfile, random, json, shutil, hashlib, time
import yaml
from datetime import datetime
from collections import Counter
from typing import List, Tuple, Optional, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

def find_font(name_hint: str) -> str:
    """自动查找包含指定关键字的字体文件路径"""
    try:
        out = subprocess.check_output(["fc-list"], text=True)
        for line in out.splitlines():
            if name_hint.lower() in line.lower():
                return line.split(":")[0]
    except Exception as e:
        print("⚠️ 字体查找失败：", e)
    return ""

# ============== 可调参数（默认值） ==============
TARGET_FPS_DEFAULT = 60
VIDEO_CODEC_HW = "h264_vaapi"  # WSL Linux 硬件编码器
VIDEO_CODEC_SW = "libx264"
BITRATE = "9000k"
AUDIO_BR = "128k"
AUDIO_SR = 48000
SOFT_CRF = "22"

DEFAULT_FONT = find_font("Kaiti") or "/Users/wuchao/Library/Application Support/com.electron.lark.font_workaround/PingFang.ttc"
DEFAULT_FOOTER = "热门短剧 休闲必看"
DEFAULT_SIDE = "剧情纯属虚构 请勿模仿"

TITLE_FONT_SIZE = 36
BOTTOM_FONT_SIZE = 28
SIDE_FONT_SIZE = 28

TITLE_COLORS = [
    "#FFA500", "#FFB347", "#FF8C00", "#FFD580", "#E69500", "#FFAE42",
]

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
DEFAULT_CONFIG_PATH = os.path.join(PROJECT_ROOT, "configs", "default.yaml")

def load_material_code_from_config(default: str = "xh") -> str:
    """Load material code from config file or environment."""
    env_value = os.environ.get("DRAMA_PROCESSOR_MATERIAL_CODE")
    if env_value:
        env_value = env_value.strip()
        if env_value:
            return env_value
    try:
        if os.path.exists(DEFAULT_CONFIG_PATH):
            with open(DEFAULT_CONFIG_PATH, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f) or {}
                code = config_data.get("material_code")
                if code:
                    code = str(code).strip()
                    if code:
                        return code
    except Exception as exc:
        print(f"⚠️ 无法从配置读取 material_code：{exc}")
    return default

MATERIAL_CODE = load_material_code_from_config()

# ============== 基础工具 ==============

def human_duration(sec: float) -> str:
    try:
        sec = float(sec)
    except Exception:
        return str(sec)
    if sec >= 60:
        return f"{sec/60:.2f} 分钟"
    return f"{sec:.2f} 秒"

def run(cmd: List[str], label: Optional[str] = None):
    cmd_str = " ".join(shlex.quote(c) for c in cmd)
    print(">>", cmd_str)
    t0 = time.time()
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    dt = time.time() - t0
    if label:
        print(f"⏱️ 命令[{label}]耗时：{human_duration(dt)}")
    if r.returncode != 0:
        print(r.stdout)
        raise RuntimeError("Command failed")
    return r

def parse_rate(rate_str: Optional[str]) -> float:
    if not rate_str or rate_str == "0/0":
        return 0.0
    if "/" in rate_str:
        a,b = rate_str.split("/",1)
        try:
            a = float(a); b = float(b); 
            return 0.0 if b==0 else a/b
        except Exception:
            return 0.0
    try:
        return float(rate_str)
    except Exception:
        return 0.0

def probe_video_stream(path: str) -> dict:
    out = run(["ffprobe","-v","error","-select_streams","v:0","-show_streams","-show_format","-of","json", path], label=f"probe:{os.path.basename(path)}").stdout
    info = json.loads(out)
    st = (info.get("streams") or [{}])[0]
    fmt = info.get("format") or {}
    width = int(st.get("width") or 0)
    height = int(st.get("height") or 0)
    duration = float(fmt.get("duration") or st.get("duration") or 0.0)
    fps = parse_rate(st.get("avg_frame_rate")) or parse_rate(st.get("r_frame_rate"))
    return {"w": width, "h": height, "duration": duration, "fps": fps}

def probe_duration(path: str) -> float:
    return probe_video_stream(path)["duration"]

def list_episode_files(ep_dir: str) -> List[str]:
    files = glob.glob(os.path.join(ep_dir, "*.mp4"))
    def keyfn(p):
        base = os.path.splitext(os.path.basename(p))[0]
        try:
            return int(base)
        except:
            return math.inf
    return sorted(files, key=keyfn)

def even(x: int) -> int:
    return x if x % 2 == 0 else x - 1

def write_text_file(path: str, text: str):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

def to_vertical(text: str) -> str:
    if "\n" in text:
        return text
    return "\n".join(list(text))

def ensure_dir(p: str) -> str:
    os.makedirs(p, exist_ok=True)
    return p

def md5_of_text(s: str) -> str:
    import hashlib
    return hashlib.md5(s.encode("utf-8")).hexdigest()

def md5_of_file(path: str, chunk: int = 1024 * 1024) -> str:
    import hashlib
    h = hashlib.md5()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b: break
            h.update(b)
    return h.hexdigest()

# ============== 画面与叠字 ==============

def build_overlay_filters(ref_w: int, ref_h: int, fps: int, fontfile: str,
                          drama_name: str, footer_text: str, side_text: str,
                          workdir: str, fast_mode: bool) -> str:
    # 轻量随机扰动（非 fast 模式）
    base_filters = [f"scale={ref_w}:{ref_h}:force_original_aspect_ratio=decrease"]
    crop_pad = random.randint(0, 3)  # 轻微裁边，降低同质化
    if crop_pad > 0:
        base_filters.append(f"crop=iw-2*{crop_pad}:ih-2*{crop_pad}:{crop_pad}:{crop_pad}")
    base_filters.append(f"pad={ref_w}:{ref_h}:(ow-iw)/2:(oh-ih)/2")
    base_filters.append(f"fps={fps}")

    if not fast_mode:
        brightness = round(random.uniform(-0.02, 0.02), 3)
        contrast   = round(random.uniform(0.98, 1.02), 3)
        saturation = round(random.uniform(0.98, 1.02), 3)
        hue        = round(random.uniform(-5, 5), 2)
        base_filters.append(f"eq=brightness={brightness}:contrast={contrast}:saturation={saturation}")
        base_filters.append(f"hue=h={hue}")

    base = ",".join(base_filters)

    # 文本
    title_fs, bottom_fs, side_fs = TITLE_FONT_SIZE, BOTTOM_FONT_SIZE, SIDE_FONT_SIZE
    margin = max(12, int(ref_h * 0.037))

    title_txt = os.path.join(workdir, "title.txt")
    bottom_txt = os.path.join(workdir, "bottom.txt")
    side_txtf = os.path.join(workdir, "side.txt")

    write_text_file(title_txt, f"《{drama_name}》")
    write_text_file(bottom_txt, footer_text)
    write_text_file(side_txtf, to_vertical(side_text))

    title_color = random.choice(TITLE_COLORS)

    dt_top = (
        f"drawtext=fontfile='{fontfile}':textfile='{title_txt}':fontsize={title_fs}:"
        f"fontcolor={title_color}@0.9:shadowx=1:shadowy=1:box=0:"
        f"x=(w-text_w)/2:y={margin + 20}"
    )
    dt_bottom = (
        f"drawtext=fontfile='{fontfile}':textfile='{bottom_txt}':fontsize={bottom_fs}:"
        f"fontcolor=white@0.85:box=0:"
        f"x=(w-text_w)/2:y=h-text_h-{margin + 120}"
    )
    dt_side = (
        f"drawtext=fontfile='{fontfile}':textfile='{side_txtf}':fontsize={side_fs}:"
        f"fontcolor=white@0.85:box=0:"
        f"x=w-text_w-{margin}:y={margin + 200}"
    )

    return ",".join([base, dt_top, dt_bottom, dt_side])

def build_base_vf(ref_w: int, ref_h: int, fps: int) -> str:
    return (
        f"scale={ref_w}:{ref_h}:force_original_aspect_ratio=decrease,"
        f"pad={ref_w}:{ref_h}:(ow-iw)/2:(oh-ih)/2,fps={fps}"
    )

# ============== 编码处理 ==============

def norm_and_trim(src: str, start_s: float, end_s: float, out_path: str,
                  ref_w: int, ref_h: int, fps: int, fontfile: str, drama_name: str,
                  footer_text: str, side_text: str, workdir: str, use_hw: bool,
                  seg_idx:int, seg_total:int, fast_mode: bool, filter_threads:int):
    dur = max(0.01, end_s - start_s)
    vf = build_overlay_filters(ref_w, ref_h, fps, fontfile, drama_name, footer_text, side_text, workdir, fast_mode=fast_mode)
    def build_cmd(vcodec: str, hw: bool):
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(max(0, start_s)), "-t", str(dur),
            "-i", src,
            "-vf", vf,
            "-analyzeduration", "20M", "-probesize", "20M",
            "-sws_flags", "fast_bilinear",
            "-filter_threads", str(filter_threads),
            "-filter_complex_threads", str(filter_threads),
            "-c:v", vcodec,
            "-profile:v", "high",
        ]
        if hw:
            cmd += ["-level", "4.2", "-tag:v", "avc1", "-b:v", BITRATE, "-maxrate", "9000k", "-bufsize", "14000k"]
        else:
            cmd += ["-level", "4.1", "-preset", "veryfast", "-crf", SOFT_CRF, "-pix_fmt", "yuv420p"]
        cmd += ["-c:a", "aac", "-b:a", AUDIO_BR, "-ar", str(AUDIO_SR), "-movflags", "+faststart", out_path]
        return cmd
    label = f"规范化片段#{seg_idx}/{seg_total} -> {os.path.basename(out_path)}"
    t0 = time.time()
    try:
        run(build_cmd(VIDEO_CODEC_HW, True) if use_hw else build_cmd(VIDEO_CODEC_SW, False), label=label)
    except Exception:
        if use_hw:
            print("⚠️ 硬编失败，回退到 x264 软编…")
            run(build_cmd(VIDEO_CODEC_SW, False), label=label+"(fallback-x264)")
        else:
            raise
    dt = time.time() - t0
    print(f"✅ 片段完成 | 源：{os.path.basename(src)} | 起止：{start_s:.3f}~{end_s:.3f}s | 用时 {human_duration(dt)} | 本素材剩余片段：{seg_total - seg_idx} 个")

def norm_tail(src: str, out_path: str, ref_w: int, ref_h: int, fps: int, use_hw: bool, filter_threads:int):
    vf = build_base_vf(ref_w, ref_h, fps)
    def build_cmd(vcodec: str, hw: bool):
        cmd = [
            "ffmpeg", "-y",
            "-i", src,
            "-vf", vf,
            "-analyzeduration", "20M", "-probesize", "20M",
            "-sws_flags", "fast_bilinear",
            "-filter_threads", str(filter_threads),
            "-filter_complex_threads", str(filter_threads),
            "-c:v", vcodec,
            "-profile:v", "high",
        ]
        if hw:
            cmd += ["-level", "4.2", "-tag:v", "avc1", "-b:v", BITRATE, "-maxrate", "9000k", "-bufsize", "14000k"]
        else:
            cmd += ["-level", "4.1", "-preset", "veryfast", "-crf", SOFT_CRF, "-pix_fmt", "yuv420p"]
        cmd += ["-c:a", "aac", "-b:a", AUDIO_BR, "-ar", str(AUDIO_SR), "-movflags", "+faststart", out_path]
        return cmd
    run(build_cmd(VIDEO_CODEC_HW, True) if use_hw else build_cmd(VIDEO_CODEC_SW, False), label="尾部规范化")

def get_or_build_tail_norm(tail_src: str, ref_w: int, ref_h: int, fps: int,
                           use_hw: bool, cache_dir: str, refresh: bool, filter_threads:int) -> Optional[str]:
    if not tail_src or not os.path.isfile(tail_src):
        return None
    ensure_dir(cache_dir)
    try:
        file_sig = md5_of_file(tail_src)[:8]
    except Exception:
        file_sig = "nosig"
    key_str = f"{os.path.abspath(tail_src)}|{file_sig}|{ref_w}x{ref_h}@{fps}|{'hw' if use_hw else 'sw'}"
    fp = md5_of_text(key_str)[:16]
    cache_path = os.path.join(cache_dir, f"tail_{fp}.mp4")
    if os.path.isfile(cache_path) and not refresh:
        print(f"🧩 复用尾部缓存：{cache_path}")
        return cache_path
    tmp_out = cache_path + ".tmp.mp4"
    try:
        print("⚙️ 正在规范化尾部（构建/刷新缓存）…")
        t0 = time.time()
        norm_tail(tail_src, tmp_out, ref_w, ref_h, fps, use_hw=use_hw, filter_threads=filter_threads)
        os.replace(tmp_out, cache_path)
        print(f"✅ 尾部缓存就绪：{cache_path} | 用时 {human_duration(time.time()-t0)}")
        return cache_path
    except Exception as e:
        print("⚠️ 规范化尾部失败：", e)
        try:
            if os.path.exists(tmp_out): os.remove(tmp_out)
        except: pass
        return None

def concat_videos(list_file: str, out_path: str, filter_threads:int):
    run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", list_file,
        "-c", "copy", "-movflags", "+faststart",
        out_path
    ], label=f"concat->{os.path.basename(out_path)}")

def write_ffconcat_list(paths: List[str], list_path: str):
    with open(list_path, "w", encoding="utf-8") as f:
        for p in paths:
            esc = p.replace("'", r"\'")
            f.write(f"file '{esc}'\n")

# ============== 封面处理 ==============

def ensure_jpeg_cover(src_path: str, workdir: str):
    ext = os.path.splitext(src_path)[1].lower()
    if ext in (".jpg", ".jpeg") and os.path.isfile(src_path):
        return src_path
    out_jpg = os.path.join(workdir, "cover_jpeg.jpg")
    run(["ffmpeg", "-y", "-i", src_path, "-frames:v", "1", "-q:v", "2", out_jpg], label="封面转jpg")
    return out_jpg

def is_black_frame_at(video_path: str, t: float, amount_pct: int = 98, pix_th: int = 32) -> bool:
    cmd = [
        "ffmpeg", "-v", "error",
        "-i", video_path,
        "-ss", f"{t}",
        "-frames:v", "1",
        "-vf", f"blackframe=amount={amount_pct}:th={pix_th}",
        "-f", "null", "-"
    ]
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        out = r.stdout or ""
        return ("pblack:" in out) and (float(out.split("pblack:")[-1].split()[0]) >= amount_pct)
    except Exception:
        return False

def extract_first_frame(video_path: str, out_img: str):
    probe_points = [0.05, 0.5, 1.0, 1.5, 2.5, 3.5, 5.0]
    for t in probe_points:
        if not is_black_frame_at(video_path, t):
            run(["ffmpeg", "-y", "-i", video_path, "-ss", f"{t}", "-frames:v", "1", out_img], label="抓首帧")
            return
    run(["ffmpeg", "-y", "-i", video_path, "-ss", "1.0", "-frames:v", "1", out_img], label="抓首帧(兜底)")

def attach_cover(in_mp4: str, cover_src: str, out_mp4: str, workdir: str):
    if not os.path.isfile(cover_src):
        raise FileNotFoundError(cover_src)
    cover_jpg = ensure_jpeg_cover(cover_src, workdir)
    run([
        "ffmpeg", "-y",
        "-i", in_mp4,
        "-i", cover_jpg,
        "-map", "0",
        "-map", "1:v:0",
        "-c", "copy",
        "-c:v:1", "mjpeg",
        "-disposition:v:1", "attached_pic",
        "-movflags", "+faststart",
        out_mp4,
    ], label="追加封面")

# ============== 片段选择（集尾对齐） ==============

def build_segments_at_episode_boundaries(episodes: List[str], start_ep_idx: int, start_offset: float,
                                         min_sec: float, max_sec: float) -> List[Tuple[str, float, float]]:
    choices = []
    total = 0.0
    for i in range(start_ep_idx, len(episodes)):
        path = episodes[i]
        try:
            dur = probe_duration(path)
        except Exception:
            continue
        seg_start = start_offset if i == start_ep_idx else 0.0
        take = max(0.0, dur - seg_start)
        if take <= 0:
            continue
        total += take
        choices.append((i, seg_start, dur, total))
        if total >= max_sec:
            break
    if not choices:
        return []

    target_mid = (min_sec + max_sec) / 2.0
    candidate_idxs = [j for j, (_, _, _, cum) in enumerate(choices) if min_sec <= cum <= max_sec]
    if candidate_idxs:
        cut_upto = min(candidate_idxs, key=lambda j: abs(choices[j][3] - target_mid))
    else:
        cut_upto = min(range(len(choices)), key=lambda j: abs(choices[j][3] - target_mid))

    segs: List[Tuple[str, float, float]] = []
    for j, (i, s, e, _) in enumerate(choices[: cut_upto + 1]):
        segs.append((episodes[i], s, e))
    return segs

# ============== 临时目录工具 ==============

def ensure_temp_root(temp_root_opt: Optional[str]) -> str:
    root = (temp_root_opt.strip() if temp_root_opt else "/tmp")
    try:
        os.makedirs(root, exist_ok=True)
    except Exception as e:
        print(f"⚠️ 创建临时目录失败（{root}），回退到 /tmp：{e}")
        root = "/tmp"
        os.makedirs(root, exist_ok=True)
    return root

# ============== 交互式多选（InquirerPy 模糊搜索 + 多选） ==============

def interactive_pick_dramas(all_drama_dirs: List[str], excludes: Optional[set] = None) -> List[str]:
    names = [os.path.basename(d.rstrip("/")) for d in all_drama_dirs]
    if excludes:
        names = [n for n in names if n not in excludes]
    if not names:
        return []
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return []

    try:
        from InquirerPy import inquirer
        from InquirerPy.base.control import Choice

        keybindings = {
            "toggle": [{"key": " "}],
            "down":   [{"key": "down"}, {"key": "c-n"}],
            "up":     [{"key": "up"},   {"key": "c-p"}],
        }

        result = inquirer.fuzzy(
            message=(
                "选择要处理的短剧：\n"
                "  - 直接输入=模糊搜索（插入模式）\n"
                "  - ESC 进入普通模式，用 j/k 或 ↑/↓ 移动；i 返回输入\n"
                "  - 空格多选，回车确认"
            ),
            choices=[Choice(name, name) for name in names],
            multiselect=True,
            keybindings=keybindings,
            vi_mode=True,
            instruction="提示：ESC 切换到普通模式用 j/k；i 返回输入；空格选中；回车确认",
        ).execute()

        if not result:
            return []
        if isinstance(result, str):
            result = [result]
        picked_names = [str(x) for x in result]
        name_to_dir = {os.path.basename(d.rstrip("/")): d for d in all_drama_dirs}
        return [name_to_dir[n] for n in picked_names if n in name_to_dir]

    except Exception as e:
        import traceback
        print("⚠️ InquirerPy 交互 UI 启动失败，降级数字多选：", repr(e))
        traceback.print_exc()
        for i, n in enumerate(names, 1):
            print(f"{i:2d}. {n}")
        raw = input("输入要处理的序号（逗号分隔），留空=全选：").strip()
        picked = names if not raw else [names[int(tok)-1] for tok in raw.split(",") if tok.strip().isdigit() and 1<=int(tok)<=len(names)]
        name_to_dir = {os.path.basename(d.rstrip("/")): d for d in all_drama_dirs}
        return [name_to_dir[n] for n in picked if n in name_to_dir]

# ============== 构建单条素材（计时+日志增强） ==============

def build_one_material(episodes: List[str], drama_name: str, start_ep_idx: int, start_offset: float,
                       min_sec: float, max_sec: float, out_path: str, ref_w: int, ref_h: int,
                       fps: int, fontfile: str, footer_text: str, side_text: str, use_hw: bool,
                       tail_file: Optional[str], cover_img: Optional[str],
                       temp_root: str, keep_temp: bool,
                       tail_cache_dir: str, refresh_tail_cache: bool,
                       material_idx:int, material_total:int,
                       fast_mode: bool, filter_threads:int) -> float:
    workdir = tempfile.mkdtemp(prefix="mat_", dir=temp_root)
    t0_all = time.time()
    print(f"🎬 开始素材 | 剧：{drama_name} | 第 {material_idx} / {material_total} 条 | 临时目录：{workdir}")

    try:
        t0 = time.time()
        segs = build_segments_at_episode_boundaries(episodes, start_ep_idx, start_offset, min_sec, max_sec)
        print(f"⏱️ 片段选择 用时：{human_duration(time.time()-t0)}")
        if not segs:
            print("⚠️ 无可用片段，跳过。")
            return 0.0

        tmp_parts = []
        seg_total = len(segs)
        print(f"ℹ️ 本条素材共 {seg_total} 个源片段待处理。")
        for idx, (ep_path, s, e) in enumerate(segs, start=1):
            tmp_out = os.path.join(workdir, f"norm_{idx:03d}.mp4")
            norm_and_trim(ep_path, s, e, tmp_out, ref_w, ref_h, fps, fontfile, drama_name, footer_text, side_text, workdir, use_hw=use_hw, seg_idx=idx, seg_total=seg_total, fast_mode=fast_mode, filter_threads=filter_threads)
            tmp_parts.append(tmp_out)

        list_path = os.path.join(workdir, "list_main.txt")
        write_ffconcat_list(tmp_parts, list_path)
        concat_main = os.path.join(workdir, "concat_main.mp4")
        t0 = time.time()
        concat_videos(list_path, concat_main, filter_threads=filter_threads)
        print(f"⏱️ 主片段拼接 用时：{human_duration(time.time()-t0)}")

        final_src = concat_main
        if tail_file and os.path.isfile(tail_file):
            tail_norm_cached = get_or_build_tail_norm(
                tail_src=tail_file,
                ref_w=ref_w, ref_h=ref_h, fps=fps,
                use_hw=use_hw,
                cache_dir=tail_cache_dir,
                refresh=refresh_tail_cache,
                filter_threads=filter_threads
            )
            if tail_norm_cached and os.path.isfile(tail_norm_cached):
                list2 = os.path.join(workdir, "list_with_tail.txt")
                write_ffconcat_list([concat_main, tail_norm_cached], list2)
                final_with_tail = os.path.join(workdir, "concat_with_tail.mp4")
                t0 = time.time()
                concat_videos(list2, final_with_tail, filter_threads=filter_threads)
                print(f"⏱️ 拼接尾部 用时：{human_duration(time.time()-t0)}")
                final_src = final_with_tail
                print("ℹ️ 已追加尾部（缓存）：", tail_norm_cached)
            else:
                print("⚠️ 尾部缓存不可用，跳过尾部。")
        else:
            if tail_file:
                print("⚠️ 指定的尾部文件不存在，跳过：", tail_file)

        t0 = time.time()
        run(["ffmpeg", "-y", "-i", final_src, "-c", "copy", "-movflags", "+faststart", out_path], label="封装")
        print(f"⏱️ 封装faststart 用时：{human_duration(time.time()-t0)}")

        chosen_cover = cover_img if (cover_img and os.path.isfile(cover_img)) else None
        if not chosen_cover:
            auto_cover = os.path.join(workdir, "auto_cover.jpg")
            try:
                t0 = time.time()
                extract_first_frame(out_path, auto_cover)
                print(f"⏱️ 抓取封面首帧 用时：{human_duration(time.time()-t0)}")
                if os.path.isfile(auto_cover):
                    chosen_cover = auto_cover
            except Exception as e:
                print("⚠️ 抓取第一帧封面失败：", e)

        if chosen_cover:
            tmp_with_cover = out_path + ".cover.mp4"
            try:
                t0 = time.time()
                attach_cover(out_path, chosen_cover, tmp_with_cover, workdir)
                print(f"⏱️ 追加封面流程 用时：{human_duration(time.time()-t0)}")
                shutil.move(tmp_with_cover, out_path)
                print("🖼️ 已追加封面：", chosen_cover)
            except Exception as e:
                print("⚠️ 追加封面失败：", e)

        dt_all = time.time() - t0_all
        print(f"✅ 素材完成 | 剧：{drama_name} | 第 {material_idx} 条 | 输出：{out_path} | 用时 {human_duration(dt_all)}")
        return dt_all
    finally:
        if not keep_temp:
            try:
                shutil.rmtree(workdir, ignore_errors=True)
            except Exception:
                pass
        else:
            print(f"🔧 保留临时目录：{workdir}")

# ============== 其他工具 ==============

def has_mp4(d: str) -> bool:
    return len(glob.glob(os.path.join(d, "*.mp4"))) > 0

def scan_drama_dirs(root_dir: str) -> List[str]:
    out = [e.path for e in os.scandir(root_dir)
           if e.is_dir() and not e.name.startswith(".") and e.name.lower() not in {"exports", "_exports"} and has_mp4(e.path)]
    return sorted(out)

def pick_cover_for_drama(drama_dir: str, drama_name: str, cover_file: Optional[str], cover_dir: Optional[str]) -> Optional[str]:
    if cover_file and os.path.isfile(cover_file):
        return cover_file
    exts = [".jpg", ".jpeg", ".png"]
    if cover_dir and os.path.isdir(cover_dir):
        for ext in exts:
            cand = os.path.join(cover_dir, drama_name + ext)
            if os.path.isfile(cand):
                return cand
    for ext in exts:
        cand = os.path.join(drama_dir, "cover" + ext)
        if os.path.isfile(cand):
            return cand
    return None

def prepare_export_dir(exports_root: str, drama_name: str) -> Tuple[str, Optional[str]]:
    existing = []
    base_plain = os.path.join(exports_root, drama_name)
    if os.path.isdir(base_plain):
        existing.append(-1)
    for e in os.scandir(exports_root):
        if not e.is_dir():
            continue
        name = e.name
        if name == drama_name:
            continue
        prefix = f"{drama_name}-"
        if name.startswith(prefix):
            suf = name[len(prefix):]
            if len(suf) == 3 and suf.isdigit():
                existing.append(int(suf))
    if not existing:
        out_dir = base_plain
        run_suffix = None
    else:
        next_idx = (max(existing) + 1) if max(existing) >= 0 else 1
        run_suffix = f"{next_idx:03d}"
        out_dir = os.path.join(exports_root, f"{drama_name}-{run_suffix}")
    os.makedirs(out_dir, exist_ok=True)
    return out_dir, run_suffix

def get_latest_export_dir(exports_root: str, drama_name: str) -> Tuple[Optional[str], Optional[str]]:
    if not os.path.isdir(exports_root):
        return None, None
    base_plain = os.path.join(exports_root, drama_name)
    max_suffix = -999
    best_dir = None
    best_suffix: Optional[str] = None
    if os.path.isdir(base_plain):
        best_dir = base_plain
        max_suffix = -1
        best_suffix = None
    prefix = f"{drama_name}-"
    for e in os.scandir(exports_root):
        if not e.is_dir():
            continue
        name = e.name
        if not name.startswith(prefix):
            continue
        suf = name[len(prefix):]
        if len(suf) == 3 and suf.isdigit():
            val = int(suf)
            if val > max_suffix:
                max_suffix = val
                best_dir = os.path.join(exports_root, name)
                best_suffix = f"{val:03d}"
    return best_dir, best_suffix

def count_existing_materials(dir_path: str) -> int:
    if not dir_path or not os.path.isdir(dir_path):
        return 0
    return len([p for p in glob.glob(os.path.join(dir_path, "*.mp4"))])

# ============== FPS 选择 ==============

def choose_output_fps(episodes: List[str], requested_fps: int, smart: bool) -> int:
    if not smart:
        return requested_fps
    src_fps = 0.0
    for ep in episodes:
        try:
            info = probe_video_stream(ep)
            if info.get("fps"):
                src_fps = info["fps"]
                break
        except Exception:
            continue
    if src_fps > 0:
        if src_fps < 40:
            out = int(round(src_fps))
        else:
            out = 45
        print(f"🎯 自适应 FPS：源约 {src_fps:.2f} -> 输出 {out}")
        return out
    return requested_fps

# ============== 入口 ==============

def main():
    t0_all = time.time()

    p = argparse.ArgumentParser(description="批量遍历根目录短剧并产出素材（集尾对齐/尾部缓存/交互多选/临时目录可控/计时日志增强/提速选项）")
    p.add_argument("root_dir", help="短剧根目录（其下每个子文件夹为一个短剧，内含 1.mp4,2.mp4,...）")
    p.add_argument("--count", type=int, default=10, help="每部短剧生成素材条数量（默认10）")
    p.add_argument("--min-sec", type=float, default=480, help="每条素材最小时长（默认480s=8分钟）")
    p.add_argument("--max-sec", type=float, default=900, help="每条素材最大时长（默认900s=15分钟）")
    p.add_argument("--date-str", type=str, default=None, help="文件名前缀日期，如 8.26；默认当天")
    p.add_argument("--random-start", action="store_true", default=True, help="随机起点，提升多样性（默认开启）")
    p.add_argument("--seed", type=int, default=None, help="随机起点种子；不传则每次运行都会不同")
    p.add_argument("--sw", action="store_true", help="使用软编(libx264)；默认硬编(h264_vaapi)")
    p.add_argument("--fps", type=int, default=TARGET_FPS_DEFAULT, help="输出帧率（默认60）")
    p.add_argument("--smart-fps", action="store_true", default=True, help="自适应帧率：源<40fps 用源帧率，否则封顶45fps（默认开启）")
    p.add_argument("--canvas", type=str, default=None, help="参考画布：'WxH' 或 'first'；默认自动选择最常见分辨率")
    p.add_argument("--font-file", type=str, default=DEFAULT_FONT, help="中文字体文件路径")
    p.add_argument("--footer-text", type=str, default=DEFAULT_FOOTER, help="底部居中文案")
    p.add_argument("--side-text", type=str, default=DEFAULT_SIDE, help="右上竖排文案（可横排传入，脚本会自动竖排化）")
    p.add_argument("--tail-file", type=str, default=None, help="尾部引导视频路径（默认脚本同级 tail.mp4；不存在则跳过）")
    p.add_argument("--cover-file", type=str, default=None, help="统一封面图路径（jpg/png），对所有剧生效；优先级最高")
    p.add_argument("--cover-dir", type=str, default="../源素材封面", help="按剧名匹配封面图的目录（默认 ../源素材封面）")
    p.add_argument("--include", action="append", default=None, help="仅处理指定短剧名（可多次传或用逗号分隔）")
    p.add_argument("--exclude", action="append", default=None, help="排除指定短剧名（可多次传或用逗号分隔）")
    p.add_argument("--jobs", type=int, default=1, help="每部剧内的并发生成数（默认1；建议2~4）")
    p.add_argument("--full", action="store_true", help="全量扫描当前根目录下的所有短剧")
    p.add_argument("--no-interactive", action="store_true", help="禁用交互式选择（默认在未指定 include/exclude/full 且在 TTY 下会交互选择）")
    # 临时目录 / 导出根目录
    p.add_argument("--temp-dir", type=str, default=None, help="临时工作目录根（默认 /tmp）")
    p.add_argument("--keep-temp", action="store_true", help="保留临时目录，便于调试（默认不保留）")
    p.add_argument("--out-dir", type=str, default="../导出素材", help="自定义导出目录（默认 ../导出素材）")
    # 尾部缓存
    p.add_argument("--tail-cache-dir", type=str, default=os.path.join("/tmp", "tails_cache"),
                   help="尾部规范化缓存目录（默认 /tmp/tails_cache）")
    p.add_argument("--refresh-tail-cache", action="store_true", help="强制刷新尾部缓存")
    # 方案A新增：
    p.add_argument("--fast-mode", action="store_true", help="更快：关闭 eq/hue 随机色彩扰动，仅保留缩放/裁切/填充与文字")
    p.add_argument("--filter-threads", type=int, default=max(2, (os.cpu_count() or 4)//2), help="滤镜并行线程数（默认=CPU核数一半，至少2）")

    args = p.parse_args()
    jobs = max(1, getattr(args, "jobs", 1))

    if args.min_sec <= 0 or args.max_sec <= 0 or args.min_sec > args.max_sec:
        print("参数错误：请保证 0 < --min-sec <= --max-sec。")
        sys.exit(2)

    root_dir = os.path.abspath(args.root_dir)
    if not os.path.isdir(root_dir):
        print("根目录不存在：", root_dir)
        sys.exit(2)

    # 导出根目录：默认 ../导出素材（相对当前工作目录）
    exports_root = args.out_dir if args.out_dir else os.path.join(root_dir, "exports")
    os.makedirs(exports_root, exist_ok=True)

    temp_root = ensure_temp_root(args.temp_dir)

    # 日期字符串：未传则用当天 M.D（如 8.26）
    date_str = args.date_str or f"{datetime.now().month}.{datetime.now().day}"

    script_dir = os.path.dirname(os.path.abspath(__file__))
    tail_path = args.tail_file if args.tail_file else os.path.join(script_dir, "tail.mp4")
    if not os.path.isfile(tail_path):
        tail_path = None

    all_drama_dirs = scan_drama_dirs(root_dir)
    if not all_drama_dirs:
        print("未在根目录下发现可处理的短剧目录。")
        sys.exit(0)

    # exclude / include 解析
    exclude_set = set()
    if args.exclude:
        ex_names = [s.strip() for part in args.exclude for s in part.split(",") if s.strip()]
        exclude_set = set(ex_names)

    include_set = None
    drama_dirs: List[str] = []

    # 交互式选择（优先，且仅在 TTY）
    is_tty = sys.stdin.isatty() and sys.stdout.isatty()
    interactive_used = False
    if (not args.include) and (not exclude_set) and (not args.full) and (not args.no_interactive) and is_tty:
        chosen = interactive_pick_dramas(all_drama_dirs, excludes=None)
        if chosen:
            drama_dirs = chosen
            include_set = set(os.path.basename(d.rstrip("/")) for d in chosen)
            print(f"🎯 本次按交互选择处理：{', '.join(sorted(include_set))}")
            interactive_used = True
        else:
            print("未选择任何剧，退出。")
            sys.exit(0)

    # include / full（若没走交互）
    if not interactive_used:
        if args.include:
            include_names = [s.strip() for part in args.include for s in part.split(",") if s.strip()]
            include_set = set(include_names)
            drama_dirs = [d for d in all_drama_dirs if os.path.basename(d.rstrip("/")) in include_set]
            if exclude_set:
                drama_dirs = [d for d in drama_dirs if os.path.basename(d.rstrip("/")) not in exclude_set]
            if not drama_dirs:
                print("未在根目录下发现与 --include 匹配的短剧目录（或被 --exclude 排除）。")
                sys.exit(0)
            print(f"🎯 本次按 include 指定处理：{', '.join(sorted(os.path.basename(x.rstrip('/')) for x in drama_dirs))}")
        elif args.full:
            drama_dirs = [d for d in all_drama_dirs if os.path.basename(d.rstrip("/")) not in exclude_set]
            print("📣 使用 --full：全量扫描处理。")
        else:
            if not is_tty:
                print("❌ 非交互环境且未提供 --include / --full。请：")
                print("   1) 传 --include 选择要处理的剧；或")
                print("   2) 传 --full 全量处理（可配合 --exclude）；或")
                print("   3) 在交互式终端运行，或显式传 --no-interactive 并提供 include/full。")
            else:
                print("未指定 --include/--exclude/--full。为安全起见直接退出。")
            sys.exit(2)

    # 全局统计
    total_materials_planned = 0
    total_materials_done = 0

    # 尾部缓存参数
    tail_cache_dir = ensure_dir(args.tail_cache_dir)
    refresh_tail_cache = bool(args.refresh_tail_cache)

    # 逐剧处理
    queue = list(drama_dirs)
    processed = set()

    i = 0
    while i < len(queue):
        d = queue[i]; i += 1
        if d in processed:
            continue
        drama_name = os.path.basename(d.rstrip("/"))
        t0_drama = time.time()

        episodes = list_episode_files(d)
        if not episodes:
            print("跳过无集文件目录：", d)
            processed.add(d)
            continue

        # 参考画布
        if args.canvas:
            if args.canvas.lower() == "first":
                info = probe_video_stream(episodes[0])
                ref_w, ref_h = even(info["w"]), even(info["h"])
            elif "x" in args.canvas.lower():
                w, h = args.canvas.lower().split("x")
                ref_w, ref_h = even(int(w)), even(int(h))
            else:
                raise RuntimeError("--canvas 需要 'first' 或 'WxH'")
        else:
            sizes = []
            for ep in episodes:
                info = probe_video_stream(ep)
                if info["w"] and info["h"]:
                    sizes.append((even(info["w"]), even(info["h"])))
            if not sizes:
                raise RuntimeError("未能探测到任何有效分辨率")
            ref_w, ref_h = Counter(sizes).most_common(1)[0][0]

        # 选择 FPS（方案A新增）
        out_fps = choose_output_fps(episodes, requested_fps=args.fps, smart=args.smart_fps)

        # === 输出目录与补齐策略 ===
        if include_set is not None and drama_name in include_set:
            out_dir, run_suffix = prepare_export_dir(exports_root, drama_name)
            start_index = 1
            total_to_make = args.count
            print(
                f"=== {drama_name} | 参考画布：{ref_w}x{ref_h} | 输出FPS：{out_fps} | 运行批次：{run_suffix or '首次'} | "
                f"计划生成：{total_to_make} 条，每条 {args.min_sec}~{args.max_sec}s ==="
            )
        else:
            latest_dir, run_suffix = get_latest_export_dir(exports_root, drama_name)
            if latest_dir:
                existing_n = count_existing_materials(latest_dir)
                if existing_n >= args.count:
                    print(f"⏭️ 跳过 {drama_name}：已存在 {existing_n} 条素材（≥ 目标 {args.count}）。")
                    processed.add(d)
                    continue
                out_dir = latest_dir
                start_index = existing_n + 1
                total_to_make = args.count - existing_n
                print(
                    f"=== {drama_name} | 参考画布：{ref_w}x{ref_h} | 输出FPS：{out_fps} | 运行批次：{run_suffix or '首次'}(补齐) | "
                    f"已存在 {existing_n} 条，补齐 {total_to_make} 条，目标 {args.count} 条 ==="
                )
            else:
                out_dir = os.path.join(exports_root, drama_name)
                os.makedirs(out_dir, exist_ok=True)
                run_suffix = None
                start_index = 1
                total_to_make = args.count
                print(
                    f"=== {drama_name} | 参考画布：{ref_w}x{ref_h} | 输出FPS：{out_fps} | 运行批次：首次 | "
                    f"计划生成：{total_to_make} 条，每条 {args.min_sec}~{args.max_sec}s ==="
                )

        cover_img = pick_cover_for_drama(d, drama_name, args.cover_file, args.cover_dir)
        if cover_img:
            print("🖼️ 使用封面：", cover_img)

        # 生成起点
        N, M = total_to_make, len(episodes)
        total_materials_planned += N
        starts: List[Tuple[int, float]] = []
        if args.random_start:
            if args.seed is not None:
                random.seed(args.seed)
            else:
                random.seed()
            for _ in range(N):
                ep_idx = random.randrange(0, M)
                dur = probe_duration(episodes[ep_idx])
                offset = round(random.uniform(0, max(0.0, min(60.0, dur / 3.0))), 3)
                starts.append((ep_idx, offset))
        else:
            step = max(1, M // max(1, N))
            for k in range(N):
                starts.append((min(k * step, M - 1), 0.0))

        # === 并行生成任务（命名从 start_index 开始） ===
        done_for_this_drama = 0
        tasks = []
        def _work(one_idx2: int, one_ep_idx: int, one_offset: float, one_out_path: str):
            try:
                dt = build_one_material(
                    episodes, drama_name, one_ep_idx, one_offset,
                    args.min_sec, args.max_sec,
                    one_out_path, ref_w, ref_h, out_fps, args.font_file,
                    args.footer_text, args.side_text,
                    use_hw=(not args.sw),
                    tail_file=tail_path,
                    cover_img=cover_img,
                    temp_root=temp_root,
                    keep_temp=args.keep_temp,
                    tail_cache_dir=tail_cache_dir,
                    refresh_tail_cache=refresh_tail_cache,
                    material_idx=one_idx2,
                    material_total=(start_index + N - 1),
                    fast_mode=args.fast_mode,
                    filter_threads=args.filter_threads
                )
                return (one_idx2, None, dt, one_out_path)
            except Exception as e:
                return (one_idx2, e, 0.0, one_out_path)

        with ThreadPoolExecutor(max_workers=jobs) as ex:
            for idx2, (ep_idx, offset) in enumerate(starts, start=start_index):
                base_name = f"{date_str}-{drama_name}-{MATERIAL_CODE}-{idx2:02d}"
                if run_suffix:
                    base_name += f"-{run_suffix}"
                out_path = os.path.join(out_dir, base_name + ".mp4")
                tasks.append(ex.submit(_work, idx2, ep_idx, offset, out_path))

            for fut in as_completed(tasks):
                done_idx, err, dt, path_out = fut.result()
                if err:
                    print(f"❌ {drama_name} 第 {done_idx} 条失败：{err}")
                else:
                    done_for_this_drama += 1
                    total_materials_done += 1
                    remain = total_to_make - done_for_this_drama
                    print(f"✅ 素材完成 | 剧：{drama_name} | 第 {done_idx} 条 | 用时 {human_duration(dt)} | 该剧剩余素材：{remain} 条")

        print(f"📦 本剧完成 | {drama_name} | 本轮生成 {done_for_this_drama}/{total_to_make} 条 | 用时 {human_duration(time.time()-t0_drama)}")

        processed.add(d)

    print(f"🎯 全部完成。输出根目录：{exports_root} | 总计 {total_materials_done}/{total_materials_planned} 条 | 总用时 {human_duration(time.time()-t0_all)}")

if __name__ == "__main__":
    main()
