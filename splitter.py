import argparse
import subprocess
import tempfile
import math
import json
from pathlib import Path

# ==========================================
# CONFIGURATION & PRESETS
# ==========================================

# Easy to update size and time limits
LIMITS = {
    "discord_free_mb": 25,
    "discord_nitro_mb": 500,
    "default_chunk_duration": 60
}

# Platform-specific presets (resolution, fps, max duration in seconds)
PRESETS = {
    "ig_reel": {"vf": "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2", "fps": 30, "duration": 60},
    "tiktok": {"vf": "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2", "fps": 30, "duration": 180},
    "yt_short": {"vf": "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2", "fps": 30, "duration": 60}
}

# ==========================================
# HELPER FUNCTIONS
# ==========================================

def run_ffmpeg(args):
    command = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"] + args
    subprocess.run(command, check=True)

def get_video_info(input_path):
    cmd = ["ffprobe", "-v", "error", "-show_entries", 
           "format=duration,bit_rate", "-of", 
           "default=noprint_wrappers=1:nokey=1", str(input_path)]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, text=True)
    duration, bitrate = result.stdout.strip().split('\n')
    return float(duration), float(bitrate)

def apply_preset(input_path, output_path, preset_name):
    settings = PRESETS.get(preset_name)
    if not settings:
        return
    
    vf = f"{settings['vf']},fps={settings['fps']},setsar=1"
    run_ffmpeg([
        "-i", str(input_path), 
        "-vf", vf, 
        "-c:v", "libx264", "-c:a", "aac", 
        str(output_path)
    ])

def concat_videos(video_paths, output_path):
    list_file = output_path.with_name("concat_list.txt")
    with open(list_file, "w") as f:
        for p in video_paths:
            f.write(f"file '{p.resolve()}'\n")
    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(output_path)])
    list_file.unlink()

# ==========================================
# SPLITTING LOGIC
# ==========================================

def process_video(input_path, output_pattern, args):
    duration, bitrate = get_video_info(input_path)
    ffmpeg_args = ["-i", str(input_path)]

    # Media Separation Category
    if args.audio_only:
        ffmpeg_args.extend(["-vn", "-c:a", "copy"])
        output_pattern = str(output_pattern).replace(".mp4", ".aac")
    elif args.video_only:
        ffmpeg_args.extend(["-an", "-c:v", "copy"])
    else:
        # Default behavior: re-encode for precision or copy
        if args.precise:
            ffmpeg_args.extend(["-c:v", "libx264", "-c:a", "aac"])
        else:
            ffmpeg_args.extend(["-c", "copy"])

    # Splitting Methods Category
    if args.time_range:
        start, end = args.time_range
        ffmpeg_args.extend(["-ss", start, "-to", end, str(output_pattern).replace("_%03d", "")])
        run_ffmpeg(ffmpeg_args)
        return

    segment_time = LIMITS["default_chunk_duration"]

    if args.preset:
        segment_time = PRESETS[args.preset]["duration"]
    elif args.n_chunk:
        segment_time = duration / args.n_chunk
    elif args.time_constraint:
        chunks = math.ceil(duration / args.time_constraint)
        segment_time = duration / chunks
    elif args.size_limit:
        target_size_bits = args.size_limit * 1024 * 1024 * 8
        segment_time = target_size_bits / bitrate

    if args.precise:
        ffmpeg_args.extend(["-force_key_frames", f"expr:gte(t,n_forced*{segment_time})"])

    ffmpeg_args.extend([
        "-map", "0",
        "-segment_time", str(segment_time),
        "-f", "segment",
        "-reset_timestamps", "1",
        str(output_pattern)
    ])
    
    run_ffmpeg(ffmpeg_args)

# ==========================================
# MAIN EXECUTION
# ==========================================

def main():
    parser = argparse.ArgumentParser(description="Video Splitting Suite")
    
    # Category 1: Processing Mode
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--continuous", action="store_true", help="Merge selected videos, then split.")
    mode_group.add_argument("--individual", action="store_true", help="Split selected videos individually.")
    
    # Category 2: Splitting Methods
    split_group = parser.add_mutually_exclusive_group()
    split_group.add_argument("--time-range", nargs=2, metavar=('START', 'END'), help="Extract a specific section (e.g., 00:01:00 00:02:30).")
    split_group.add_argument("--n-chunk", type=int, help="Divide video into N equal parts.")
    split_group.add_argument("--time-constraint", type=int, help="Evenly split video so no chunk exceeds this duration in seconds.")
    split_group.add_argument("--size-limit", type=int, help="Split video into chunks of this size in MB.")
    
    # Category 3: Media Separation
    media_group = parser.add_mutually_exclusive_group()
    media_group.add_argument("--audio-only", action="store_true", help="Extract only the audio track.")
    media_group.add_argument("--video-only", action="store_true", help="Extract only the video track.")
    
    # Category 4: Presets & Normalization
    preset_group = parser.add_mutually_exclusive_group()
    preset_group.add_argument("--preset", choices=PRESETS.keys(), help="Apply a platform-specific preset.")
    preset_group.add_argument("--normalize", action="store_true", help="Standardize resolution and framerate to basic 1080p.")
    
    # Global Modifiers
    parser.add_argument("--files", nargs="+", help="Specific files to process in raw_videos.")
    parser.add_argument("--precise", action="store_true", help="Re-encode for exact cuts.")
    
    args = parser.parse_args()

    input_dir = Path("raw_videos")
    output_dir = Path("split_videos")
    input_dir.mkdir(exist_ok=True)
    output_dir.mkdir(exist_ok=True)

    if args.files:
        videos = [input_dir / f for f in args.files if (input_dir / f).exists()]
    else:
        videos = sorted(list(input_dir.glob("*.mp4")))

    if not videos:
        print("No valid mp4 files found in raw_videos.")
        return

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        working_videos = videos

        if args.preset or args.normalize:
            working_videos = []
            for video in videos:
                norm_path = temp_dir_path / f"norm_{video.name}"
                if args.preset:
                    apply_preset(video, norm_path, args.preset)
                else:
                    apply_preset(video, norm_path, "ig_reel") # default normalizer
                working_videos.append(norm_path)

        if args.continuous:
            merged_path = temp_dir_path / "merged.mp4"
            out_pattern = output_dir / "out_continuous_%03d.mp4"
            concat_videos(working_videos, merged_path)
            process_video(merged_path, out_pattern, args)

        elif args.individual:
            for i, video in enumerate(working_videos):
                original_name = videos[i].stem
                out_pattern = output_dir / f"out_{original_name}_%03d.mp4"
                process_video(video, out_pattern, args)

if __name__ == "__main__":
    main()
