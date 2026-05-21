import argparse
import subprocess
import tempfile
from pathlib import Path

def run_ffmpeg(args):
    command = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"] + args
    subprocess.run(command, check=True)

def normalize_video(input_path, output_path):
    vf = "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,fps=30,setsar=1"
    run_ffmpeg([
        "-i", str(input_path), 
        "-vf", vf, 
        "-c:v", "libx264", "-c:a", "aac", 
        str(output_path)
    ])

def split_video(input_path, output_pattern, precise=False):
    codec_args = [
        "-c:v", "libx264", "-c:a", "aac", 
        "-force_key_frames", "expr:gte(t,n_forced*60)"
    ] if precise else ["-c", "copy"]

    args = ["-i", str(input_path)] + codec_args + [
        "-map", "0", 
        "-segment_time", "60", 
        "-f", "segment", 
        "-reset_timestamps", "1",
        str(output_pattern)
    ]
    run_ffmpeg(args)

def concat_videos(video_paths, output_path):
    list_file = output_path.with_name("concat_list.txt")
    with open(list_file, "w") as f:
        for p in video_paths:
            f.write(f"file '{p.resolve()}'\n")
    
    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(output_path)])
    list_file.unlink()

def main():
    parser = argparse.ArgumentParser(description="Video Splitting Suite")
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--continuous", action="store_true", help="Merge selected videos, then split.")
    group.add_argument("--individual", action="store_true", help="Split selected videos individually.")
    
    parser.add_argument("--files", nargs="+", help="Specific files to process in raw_videos. Dictates order.")
    parser.add_argument("--precise", action="store_true", help="Re-encode for exact 60s cuts.")
    parser.add_argument("--normalize", action="store_true", help="Standardize resolution and framerate.")
    args = parser.parse_args()

    input_dir = Path("raw_videos")
    output_dir = Path("split_videos")
    
    # Create directories if they do not exist
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

        if args.normalize:
            working_videos = []
            for video in videos:
                norm_path = temp_dir_path / f"norm_{video.name}"
                normalize_video(video, norm_path)
                working_videos.append(norm_path)

        if args.continuous:
            merged_path = temp_dir_path / "merged.mp4"
            out_pattern = output_dir / "out_continuous_%03d.mp4"
            
            concat_videos(working_videos, merged_path)
            split_video(merged_path, out_pattern, args.precise)

        elif args.individual:
            for i, video in enumerate(working_videos):
                original_name = videos[i].stem
                out_pattern = output_dir / f"out_{original_name}_%03d.mp4"
                split_video(video, out_pattern, args.precise)

if __name__ == "__main__":
    main()
