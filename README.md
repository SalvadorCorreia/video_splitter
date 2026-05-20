# Video Splitter

A Python script that cuts videos into 1-minute segments. 

## Requirements

1. Python 3 installed.
2. FFmpeg installed and added to your system path.

## Usage

Run the script from your terminal:

`python splitter.py <folder_path> [options]`

### Required Options (Choose one)

* `--continuous`: Combines all videos in the folder into one long video, then cuts it into 1-minute parts.
* `--individual`: Cuts each video in the folder into 1-minute parts separately.

### Additional Options

* `--precise`: Ensures cuts are exactly 60 seconds long. This process takes longer because it rebuilds the video.
* `--normalize`: Resizes all videos to Instagram format (1080x1920) and sets them to 30 frames per second. Use this if your videos have different sizes, especially before using `--continuous`.

## Examples

Merge all videos, make them the same size, and split:
`python splitter.py /path/to/videos --continuous --normalize`

Split each video exactly at 60 seconds:
`python splitter.py /path/to/videos --individual --precise`