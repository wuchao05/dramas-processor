import json
import math
import os
import re
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path

import httpx
from openai import OpenAI

REQUEST_TIMEOUT = httpx.Timeout(connect=30.0, read=300.0, write=300.0, pool=60.0)
UPLOAD_TIMEOUT = httpx.Timeout(connect=30.0, read=300.0, write=300.0, pool=60.0)
UPLOAD_POLICY_URL = "https://dashscope.aliyuncs.com/api/v1/uploads"
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

SOURCE_VIDEO_ROOT = Path(os.getenv("SOURCE_VIDEO_ROOT", ".")).resolve()
OUTPUT_JSON_PATH = Path(
    os.getenv("OUTPUT_JSON_PATH", "drama_highlights.json")
).resolve()
MODEL_NAME = os.getenv("QWEN_MODEL", "qwen3-vl-plus")
GROUP_COUNT = int(os.getenv("GROUP_COUNT", "10"))
TARGET_HIGHLIGHTS_PER_DRAMA = int(
    os.getenv("TARGET_HIGHLIGHTS_PER_DRAMA", "60")
)
GROUP_HIGHLIGHT_BUFFER = int(os.getenv("GROUP_HIGHLIGHT_BUFFER", "4"))
VIDEO_FPS = float(os.getenv("VIDEO_FPS", "1"))
ANALYZE_FIRST_PORTION_ONLY = (
    os.getenv("ANALYZE_FIRST_PORTION_ONLY", "true").lower()
    in {"1", "true", "yes"}
)
ANALYZE_PORTION_RATIO = float(os.getenv("ANALYZE_PORTION_RATIO", "0.3"))
ANALYSIS_CLIP_DIR = Path(os.getenv("ANALYSIS_CLIP_DIR", ".analysis_clips")).resolve()
AUTO_RETRY_INSUFFICIENT_GROUPS = (
    os.getenv("AUTO_RETRY_INSUFFICIENT_GROUPS", "true").lower()
    in {"1", "true", "yes"}
)
MAX_AUTO_RETRY_ROUNDS = int(os.getenv("MAX_AUTO_RETRY_ROUNDS", "2"))
ENABLE_POLLING = (
    os.getenv("ENABLE_POLLING", "false").lower() in {"1", "true", "yes"}
)
POLL_INTERVAL_MINUTES = float(os.getenv("POLL_INTERVAL_MINUTES", "10"))
USE_DASHSCOPE_PROXY = (
    os.getenv("DASHSCOPE_USE_PROXY", "").lower() in {"1", "true", "yes"}
)


def build_http_client(timeout):
    if not USE_DASHSCOPE_PROXY:
        print("proxy: <直连，已忽略环境代理>")
        return httpx.Client(timeout=timeout, trust_env=False)

    proxy = (
        os.getenv("HTTPS_PROXY")
        or os.getenv("https_proxy")
        or os.getenv("HTTP_PROXY")
        or os.getenv("http_proxy")
    )

    if proxy:
        print(f"proxy: {proxy}")
        return httpx.Client(proxy=proxy, timeout=timeout, trust_env=False)

    print("proxy: <直连>")
    return httpx.Client(timeout=timeout, trust_env=False)


def load_existing_results(output_path):
    if not output_path.exists():
        return {}

    with output_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(f"输出文件格式不正确: {output_path}")

    return data


def save_results(output_path, results):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(results, file, ensure_ascii=False, indent=2)


def parse_episode_number(file_path):
    try:
        return int(file_path.stem)
    except ValueError:
        return None


def list_episode_files(drama_dir):
    episodes = []
    for file_path in drama_dir.iterdir():
        if not file_path.is_file() or file_path.suffix.lower() != ".mp4":
            continue

        episode = parse_episode_number(file_path)
        if episode is None:
            continue

        episodes.append(file_path)

    return sorted(episodes, key=parse_episode_number)


def list_drama_directories(source_root):
    if not source_root.exists():
        raise FileNotFoundError(f"找不到源视频根目录: {source_root}")

    drama_dirs = []
    for path in sorted(source_root.iterdir(), key=lambda item: item.name):
        if not path.is_dir():
            continue
        if path.name.startswith(".") or path.name.startswith("__"):
            continue
        if list_episode_files(path):
            drama_dirs.append(path)

    return drama_dirs


def split_into_groups(items, group_count):
    if not items:
        return []

    actual_group_count = max(1, min(group_count, len(items)))
    groups = []
    start = 0

    for index in range(actual_group_count):
        size = len(items) // actual_group_count
        if index < len(items) % actual_group_count:
            size += 1

        group = items[start : start + size]
        if group:
            groups.append(group)
        start += size

    return groups


def get_upload_policy(http_client, api_key, model_name):
    response = http_client.get(
        UPLOAD_POLICY_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        params={"action": "getPolicy", "model": model_name},
    )
    response.raise_for_status()
    return response.json()["data"]


def get_video_duration(file_path):
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(file_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    return float(result.stdout.strip())


def prepare_video_for_analysis(file_path, drama_name, episode):
    full_duration = get_video_duration(file_path)

    if not ANALYZE_FIRST_PORTION_ONLY:
        return {
            "analysis_file_path": file_path,
            "full_duration_seconds": full_duration,
            "analysis_duration_seconds": full_duration,
            "analysis_scope": "full",
        }

    analysis_duration = max(1.0, full_duration * ANALYZE_PORTION_RATIO)
    drama_clip_dir = ANALYSIS_CLIP_DIR / drama_name
    drama_clip_dir.mkdir(parents=True, exist_ok=True)
    clip_file_path = (
        drama_clip_dir
        / f"{episode}_first_{int(ANALYZE_PORTION_RATIO * 100)}.mp4"
    )

    if not clip_file_path.exists():
        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(file_path),
            "-t",
            f"{analysis_duration:.3f}",
            "-c",
            "copy",
            str(clip_file_path),
        ]
        subprocess.run(command, capture_output=True, text=True, check=True)

    return {
        "analysis_file_path": clip_file_path,
        "full_duration_seconds": full_duration,
        "analysis_duration_seconds": analysis_duration,
        "analysis_scope": "first_portion",
    }


def upload_file_to_oss(http_client, policy_data, file_path):
    file_name = file_path.name
    key = f"{policy_data['upload_dir']}/{file_name}"

    with file_path.open("rb") as video_file:
        files = {
            "OSSAccessKeyId": (None, policy_data["oss_access_key_id"]),
            "Signature": (None, policy_data["signature"]),
            "policy": (None, policy_data["policy"]),
            "x-oss-object-acl": (None, policy_data["x_oss_object_acl"]),
            "x-oss-forbid-overwrite": (
                None,
                policy_data["x_oss_forbid_overwrite"],
            ),
            "key": (None, key),
            "success_action_status": (None, "200"),
            "file": (file_name, video_file, "video/mp4"),
        }

        response = http_client.post(policy_data["upload_host"], files=files)
        response.raise_for_status()

    return f"oss://{key}"


def upload_group_videos(http_client, api_key, model_name, drama_name, episode_files):
    print(f"[{drama_name}] 正在获取上传凭证...")
    policy_data = get_upload_policy(http_client, api_key, model_name)

    uploaded_videos = []
    for file_path in episode_files:
        episode = parse_episode_number(file_path)
        file_size = file_path.stat().st_size / 1024 / 1024
        prepared_video = prepare_video_for_analysis(file_path, drama_name, episode)
        analysis_file_path = Path(prepared_video["analysis_file_path"])
        analysis_size = analysis_file_path.stat().st_size / 1024 / 1024

        if prepared_video["analysis_scope"] == "first_portion":
            print(
                f"[{drama_name}] 第 {episode} 集仅分析前 {ANALYZE_PORTION_RATIO:.0%}，"
                f"原时长 {prepared_video['full_duration_seconds']:.1f}s，"
                f"分析时长 {prepared_video['analysis_duration_seconds']:.1f}s，"
                f"原大小 {file_size:.2f} MB，分析文件 {analysis_size:.2f} MB..."
            )
        else:
            print(f"[{drama_name}] 正在上传第 {episode} 集，大小 {file_size:.2f} MB...")

        video_url = upload_file_to_oss(http_client, policy_data, analysis_file_path)
        uploaded_videos.append(
            {
                "episode": episode,
                "file_name": file_path.name,
                "file_path": str(file_path),
                "analysis_file_path": str(analysis_file_path),
                "video_url": video_url,
                "analysis_scope": prepared_video["analysis_scope"],
                "full_duration_seconds": round(
                    prepared_video["full_duration_seconds"], 3
                ),
                "analysis_duration_seconds": round(
                    prepared_video["analysis_duration_seconds"], 3
                ),
            }
        )

    return uploaded_videos


def build_group_prompt(drama_name, uploaded_videos, target_count):
    episode_lines = [
        f"- 第 {item['episode']} 集，对应文件 {item['file_name']}"
        for item in uploaded_videos
    ]
    episode_text = "\n".join(episode_lines)

    return (
        f"你将收到同一部短剧《{drama_name}》的一组视频片段。\n"
        f"本组共 {len(uploaded_videos)} 集，请跨所有视频一起分析，找出最多 {target_count} 个适合做混剪开场的高光起始点。\n"
        "注意：你看到的只是每一集用于分析的片段，不一定是整集完整内容。若某集只提供了前半集，请只基于已提供片段给出高光起始点。\n"
        "请优先选择以下类型的镜头：冲突爆发、反转揭晓、身份亮相、情绪爆点、强钩子台词、人物关系骤变。\n"
        "只输出 JSON，不要输出任何额外解释。\n"
        "返回格式必须是："
        '{"highlights":[{"episode":1,"start_time":"HH:MM:SS","score":95,"reason":"原因"}]}\n'
        "约束：\n"
        "1. episode 必须是本组内真实存在的集数。\n"
        "2. start_time 使用 HH:MM:SS 格式。\n"
        "3. score 使用 0 到 100 的整数，分数越高代表越适合做混剪开场。\n"
        "4. 同一集可以返回多个起始点，但不要重复。\n"
        "5. reason 用简洁中文说明为什么适合作为开场。\n"
        "本组视频列表：\n"
        f"{episode_text}"
    )


def request_group_highlights(client, drama_name, uploaded_videos, target_count):
    content = [
        {"type": "text", "text": build_group_prompt(drama_name, uploaded_videos, target_count)}
    ]

    for item in uploaded_videos:
        content.append(
            {
                "type": "text",
                "text": f"下面这个视频对应《{drama_name}》第 {item['episode']} 集。",
            }
        )
        content.append(
            {
                "type": "video_url",
                "video_url": {"url": item["video_url"]},
                "fps": VIDEO_FPS,
            }
        )

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": "你是一个短剧高光分析助手。你必须只输出 JSON，不要输出任何额外解释。",
            },
            {"role": "user", "content": content},
        ],
        response_format={"type": "json_object"},
        extra_body={"enable_thinking": False},
    )

    content_text = response.choices[0].message.content
    return json.loads(content_text)


def parse_episode_value(value):
    if isinstance(value, int):
        return value

    if isinstance(value, str):
        matched = re.search(r"\d+", value)
        if matched:
            return int(matched.group())

    return None


def parse_time_to_seconds(time_text):
    if not isinstance(time_text, str):
        return None

    parts = [part.strip() for part in time_text.split(":")]
    if len(parts) not in {2, 3}:
        return None
    if not all(part.isdigit() for part in parts):
        return None

    numbers = [int(part) for part in parts]
    if len(numbers) == 2:
        minutes, seconds = numbers
        return minutes * 60 + seconds

    hours, minutes, seconds = numbers
    return hours * 3600 + minutes * 60 + seconds


def format_seconds_to_hhmmss(total_seconds):
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def normalize_group_highlights(drama_name, group_index, raw_highlights, uploaded_videos):
    allowed_episodes = {item["episode"] for item in uploaded_videos}
    file_name_map = {item["episode"]: item["file_name"] for item in uploaded_videos}
    normalized = []

    for item in raw_highlights:
        if not isinstance(item, dict):
            continue

        episode = parse_episode_value(item.get("episode"))
        start_seconds = parse_time_to_seconds(item.get("start_time"))
        score = item.get("score")
        reason = item.get("reason", "")

        if episode not in allowed_episodes:
            continue
        if start_seconds is None:
            continue
        if not isinstance(score, int):
            continue

        normalized.append(
            {
                "episode": episode,
                "episode_file": file_name_map[episode],
                "start_time": format_seconds_to_hhmmss(start_seconds),
                "start_seconds": start_seconds,
                "score": score,
                "reason": str(reason).strip(),
                "group_index": group_index,
                "drama_name": drama_name,
            }
        )

    return normalized


def merge_highlights(highlights, target_count):
    deduped = {}

    for item in highlights:
        key = (item["episode"], item["start_seconds"])
        existing = deduped.get(key)
        if existing is None or item["score"] > existing["score"]:
            deduped[key] = item

    merged = sorted(
        deduped.values(),
        key=lambda item: (-item["score"], item["episode"], item["start_seconds"]),
    )

    trimmed = []
    for item in merged[:target_count]:
        trimmed.append(
            {
                "episode": item["episode"],
                "episode_file": item["episode_file"],
                "start_time": item["start_time"],
                "score": item["score"],
                "reason": item["reason"],
                "group_index": item["group_index"],
            }
        )

    return trimmed


def calculate_group_target(target_count, group_count):
    return math.ceil(target_count / max(1, group_count)) + GROUP_HIGHLIGHT_BUFFER


def should_retry_group(group_run):
    episode_count = len(group_run["episode_files"])
    retry_threshold = max(1, min(3, math.ceil(group_run["group_target"] / 2)))

    if episode_count > 1:
        return group_run["result_count"] < retry_threshold

    return group_run["result_count"] == 0


def build_retry_groups(group_runs):
    retry_groups = []

    for group_run in group_runs:
        episode_files = group_run["episode_files"]
        if len(episode_files) > 1:
            retry_groups.extend(split_into_groups(episode_files, len(episode_files)))
        else:
            retry_groups.append(episode_files)

    deduped_groups = []
    seen = set()
    for group_files in retry_groups:
        key = tuple(str(file_path) for file_path in group_files)
        if key in seen:
            continue
        seen.add(key)
        deduped_groups.append(group_files)

    return deduped_groups


def run_group_batch(
    drama_name,
    api_key,
    upload_http_client,
    client,
    group_batches,
    target_count,
    retry_round=0,
):
    batch_highlights = []
    batch_runs = []
    group_target = calculate_group_target(target_count, len(group_batches))

    for group_index, group_files in enumerate(group_batches, start=1):
        group_episode_text = ", ".join(
            str(parse_episode_number(file_path)) for file_path in group_files
        )

        if retry_round == 0:
            print(
                f"[{drama_name}] 正在分析第 {group_index}/{len(group_batches)} 组，包含第 {group_episode_text} 集"
            )
        else:
            print(
                f"[{drama_name}] 正在执行第 {retry_round} 轮补跑，"
                f"子组 {group_index}/{len(group_batches)}，包含第 {group_episode_text} 集"
            )

        uploaded_videos = upload_group_videos(
            upload_http_client,
            api_key,
            MODEL_NAME,
            drama_name,
            group_files,
        )

        print(f"[{drama_name}] 正在请求模型返回本组高光起始点...")
        parsed = request_group_highlights(
            client, drama_name, uploaded_videos, group_target
        )
        raw_highlights = parsed.get("highlights", [])
        normalized = normalize_group_highlights(
            drama_name,
            group_index,
            raw_highlights,
            uploaded_videos,
        )

        if retry_round == 0:
            print(f"[{drama_name}] 第 {group_index} 组返回 {len(normalized)} 个候选起始点")
        else:
            print(
                f"[{drama_name}] 第 {retry_round} 轮补跑的子组 {group_index} 返回 {len(normalized)} 个候选起始点"
            )

        batch_highlights.extend(normalized)
        batch_runs.append(
            {
                "episode_files": group_files,
                "result_count": len(normalized),
                "group_target": group_target,
                "retry_round": retry_round,
            }
        )

    return batch_highlights, batch_runs


def process_drama(drama_dir, api_key):
    drama_name = drama_dir.name
    episode_files = list_episode_files(drama_dir)
    groups = split_into_groups(episode_files, GROUP_COUNT)

    print(f"\n开始处理短剧：{drama_name}")
    print(f"共 {len(episode_files)} 集，分为 {len(groups)} 组")

    upload_http_client = build_http_client(UPLOAD_TIMEOUT)
    openai_http_client = build_http_client(REQUEST_TIMEOUT)
    client = OpenAI(
        api_key=api_key,
        base_url=BASE_URL,
        default_headers={"X-DashScope-OssResourceResolve": "enable"},
        http_client=openai_http_client,
    )

    all_highlights = []
    retry_rounds_used = 0

    try:
        initial_highlights, initial_group_runs = run_group_batch(
            drama_name=drama_name,
            api_key=api_key,
            upload_http_client=upload_http_client,
            client=client,
            group_batches=groups,
            target_count=TARGET_HIGHLIGHTS_PER_DRAMA,
            retry_round=0,
        )
        all_highlights.extend(initial_highlights)

        final_highlights = merge_highlights(
            all_highlights, TARGET_HIGHLIGHTS_PER_DRAMA
        )

        if AUTO_RETRY_INSUFFICIENT_GROUPS:
            retry_source_runs = initial_group_runs
            for retry_round in range(1, MAX_AUTO_RETRY_ROUNDS + 1):
                if len(final_highlights) >= TARGET_HIGHLIGHTS_PER_DRAMA:
                    break

                retry_candidates = [
                    group_run
                    for group_run in retry_source_runs
                    if should_retry_group(group_run)
                ]
                if not retry_candidates:
                    print(f"[{drama_name}] 没有可继续补跑的缺口组，停止自动补跑")
                    break

                retry_groups = build_retry_groups(retry_candidates)
                if not retry_groups:
                    print(f"[{drama_name}] 缺口组无法继续拆分，停止自动补跑")
                    break

                remaining_needed = (
                    TARGET_HIGHLIGHTS_PER_DRAMA - len(final_highlights)
                )
                print(
                    f"[{drama_name}] 当前仅拿到 {len(final_highlights)}/{TARGET_HIGHLIGHTS_PER_DRAMA} 个高光点，"
                    f"开始第 {retry_round} 轮自动补跑，补跑子组数量 {len(retry_groups)}"
                )

                retry_highlights, retry_runs = run_group_batch(
                    drama_name=drama_name,
                    api_key=api_key,
                    upload_http_client=upload_http_client,
                    client=client,
                    group_batches=retry_groups,
                    target_count=remaining_needed,
                    retry_round=retry_round,
                )
                all_highlights.extend(retry_highlights)
                final_highlights = merge_highlights(
                    all_highlights, TARGET_HIGHLIGHTS_PER_DRAMA
                )
                retry_source_runs = retry_runs
                retry_rounds_used = retry_round
    finally:
        upload_http_client.close()
        openai_http_client.close()

    final_highlights = merge_highlights(all_highlights, TARGET_HIGHLIGHTS_PER_DRAMA)
    print(f"[{drama_name}] 最终保留 {len(final_highlights)} 个高光起始点")

    return {
        "drama_name": drama_name,
        "source_dir": str(drama_dir),
        "model": MODEL_NAME,
        "analyze_first_portion_only": ANALYZE_FIRST_PORTION_ONLY,
        "analyze_portion_ratio": ANALYZE_PORTION_RATIO,
        "auto_retry_insufficient_groups": AUTO_RETRY_INSUFFICIENT_GROUPS,
        "max_auto_retry_rounds": MAX_AUTO_RETRY_ROUNDS,
        "retry_rounds_used": retry_rounds_used,
        "episode_count": len(episode_files),
        "group_count": len(groups),
        "target_highlights": TARGET_HIGHLIGHTS_PER_DRAMA,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "highlights": final_highlights,
    }


def scan_and_process_once(api_key):
    existing_results = load_existing_results(OUTPUT_JSON_PATH)
    drama_dirs = list_drama_directories(SOURCE_VIDEO_ROOT)
    pending_drama_dirs = [
        drama_dir for drama_dir in drama_dirs if drama_dir.name not in existing_results
    ]

    print(f"当前扫描时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"待扫描短剧数量: {len(drama_dirs)}")
    print(f"待处理短剧数量: {len(pending_drama_dirs)}")

    processed_count = 0

    for drama_dir in pending_drama_dirs:
        drama_name = drama_dir.name
        try:
            result = process_drama(drama_dir, api_key)
            existing_results[drama_name] = result
            save_results(OUTPUT_JSON_PATH, existing_results)
            processed_count += 1
            print(f"[{drama_name}] 已写入 {OUTPUT_JSON_PATH}")
        except Exception as error:
            print(f"[{drama_name}] 处理失败：{error}")
            if not ENABLE_POLLING:
                raise

    return {
        "drama_count": len(drama_dirs),
        "pending_count": len(pending_drama_dirs),
        "processed_count": processed_count,
    }


def main():
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise RuntimeError("未读取到 DASHSCOPE_API_KEY 环境变量，请先 export")

    if GROUP_COUNT <= 0:
        raise ValueError("GROUP_COUNT 必须大于 0")

    if TARGET_HIGHLIGHTS_PER_DRAMA <= 0:
        raise ValueError("TARGET_HIGHLIGHTS_PER_DRAMA 必须大于 0")
    if not 0.1 <= VIDEO_FPS <= 10:
        raise ValueError("VIDEO_FPS 必须在 0.1 到 10 之间")
    if not 0 < ANALYZE_PORTION_RATIO <= 1:
        raise ValueError("ANALYZE_PORTION_RATIO 必须在 0 到 1 之间")
    if MAX_AUTO_RETRY_ROUNDS < 0:
        raise ValueError("MAX_AUTO_RETRY_ROUNDS 不能小于 0")
    if POLL_INTERVAL_MINUTES <= 0:
        raise ValueError("POLL_INTERVAL_MINUTES 必须大于 0")

    print(f"源视频根目录: {SOURCE_VIDEO_ROOT}")
    print(f"输出 JSON: {OUTPUT_JSON_PATH}")
    print(f"默认模型: {MODEL_NAME}")
    print(f"目标高光点数量: {TARGET_HIGHLIGHTS_PER_DRAMA}")
    print(f"分组数: {GROUP_COUNT}")
    print(f"视频抽帧 fps: {VIDEO_FPS}")
    print(f"仅分析前半段: {ANALYZE_FIRST_PORTION_ONLY}")
    print(f"分析片段比例: {ANALYZE_PORTION_RATIO:.0%}")
    print(f"自动补跑缺口组: {AUTO_RETRY_INSUFFICIENT_GROUPS}")
    print(f"最大自动补跑轮数: {MAX_AUTO_RETRY_ROUNDS}")
    print(f"开启轮询模式: {ENABLE_POLLING}")
    print(f"轮询间隔分钟: {POLL_INTERVAL_MINUTES}")

    if not ENABLE_POLLING:
        scan_and_process_once(api_key)
        return

    while True:
        summary = scan_and_process_once(api_key)
        next_scan_time = datetime.now() + timedelta(minutes=POLL_INTERVAL_MINUTES)
        print(
            f"本轮完成：共扫描 {summary['drama_count']} 部，"
            f"待处理 {summary['pending_count']} 部，"
            f"实际处理 {summary['processed_count']} 部"
        )
        print(f"下次扫描时间: {next_scan_time.strftime('%Y-%m-%d %H:%M:%S')}")
        time.sleep(POLL_INTERVAL_MINUTES * 60)


if __name__ == "__main__":
    main()
