import argparse
import subprocess
import tempfile
import math
import shutil
from pathlib import Path

# ==========================================
# PRESETS
# ==========================================

PRESETS = {
    "ig_reel": {"vf": "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2", "fps": 30, "duration": 60},
    "tiktok": {"vf": "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2", "fps": 30, "duration": 180},
    "yt_short": {"vf": "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2", "fps": 30, "duration": 60},
    "discord_free": {"size_mb": 25},
    "discord_nitro": {"size_mb": 500}
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
    if not settings or "vf" not in settings:
        shutil.copy(input_path, output_path)
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

    if args.media == "audio":
        ffmpeg_args.extend(["-vn", "-c:a", "copy"])
        output_pattern = str(output_pattern).replace(".mp4", ".aac")
    elif args.media == "video":
        ffmpeg_args.extend(["-an", "-c:v", "copy"])
    else:
        if args.precise:
            ffmpeg_args.extend(["-c:v", "libx264", "-c:a", "aac"])
        else:
            ffmpeg_args.extend(["-c", "copy"])

    if args.split == "range":
        start, end = args.split_val
        ffmpeg_args.extend(["-ss", start, "-to", end, str(output_pattern).replace("_%03d", "")])
        run_ffmpeg(ffmpeg_args)
        return

    segment_time = 60

    if args.preset:
        preset = PRESETS[args.preset]
        if "duration" in preset:
            segment_time = preset["duration"]
        elif "size_mb" in preset:
            target_size_bits = preset["size_mb"] * 1024 * 1024 * 8
            segment_time = target_size_bits / bitrate
    elif args.split == "n-chunk":
        segment_time = duration / int(args.split_val[0])
    elif args.split == "time-constraint":
        chunks = math.ceil(duration / int(args.split_val[0]))
        segment_time = duration / chunks
    elif args.split == "size":
        target_size_bits = float(args.split_val[0]) * 1024 * 1024 * 8
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
    parser = argparse.ArgumentParser(
        description="Video Splitting Suite",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument("--mode", choices=["continuous", "individual"], required=True, 
                        help="Processing mode.")
    
    parser.add_argument("--split", choices=["range", "n-chunk", "time-constraint", "size"], 
                        help="Splitting method.\n"
                             "range: args = START END (e.g. 00:01 00:02)\n"
                             "n-chunk: args = N\n"
                             "time-constraint: args = SECONDS\n"
                             "size: args = MB")
    
    parser.add_argument("--split-val", nargs="+", help="Values for the chosen split method.")
    
    parser.add_argument("--media", choices=["audio", "video", "all"], default="all", 
                        help="Extract specific media track.")
    
    parser.add_argument("--preset", choices=PRESETS.keys(), 
                        help="Apply platform-specific configurations.")
    
    parser.add_argument("--files", nargs="+", help="Specific files to process in raw_videos.")
    parser.add_argument("--precise", action="store_true", help="Re-encode for exact cuts.")
    
    args = parser.parse_args()

    if args.split:
        if not args.split_val:
            parser.error("--split requires --split-val.")
        if args.split == "range" and len(args.split_val) != 2:
            parser.error("--split range requires two values: START END.")
        if args.split in ["n-chunk", "time-constraint", "size"] and len(args.split_val) != 1:
            parser.error(f"--split {args.split} requires one numeric value.")

    input_dir = Path("raw_videos")
    output_dir = Path("split_videos")
    input_dir.mkdir(exist_ok=True)
    output_dir.mkdir(exist_ok=True)

    if args.files:
        videos = [input_dir / Path(f).name for f in args.files if (input_dir / Path(f).name).exists()]
    else:
        videos = sorted(list(input_dir.glob("*.mp4")))

    if not videos:
        print("No valid mp4 files found in raw_videos.")
        return

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        working_videos = videos

        if args.preset:
            working_videos = []
            for video in videos:
                norm_path = temp_dir_path / f"preset_{video.name}"
                apply_preset(video, norm_path, args.preset)
                working_videos.append(norm_path)

        if args.mode == "continuous":
            merged_path = temp_dir_path / "merged.mp4"
            out_pattern = output_dir / "out_continuous_%03d.mp4"
            concat_videos(working_videos, merged_path)
            process_video(merged_path, out_pattern, args)

        elif args.mode == "individual":
            for i, video in enumerate(working_videos):
                original_name = videos[i].stem
                out_pattern = output_dir / f"out_{original_name}_%03d.mp4"
                process_video(video, out_pattern, args)

if __name__ == "__main__":
    main()
