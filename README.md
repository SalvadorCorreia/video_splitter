# Video Splitting Suite

A command-line tool to process, split, and normalize videos.

## Setup

1. Install Python 3.
2. Install FFmpeg and ensure it is in your system path.
3. Place your input `.mp4` files in the `raw_videos` directory.
4. Processed files will appear in a timestamped folder inside the `split_videos` directory.

## Usage

Run the script with the required `--mode` argument and any additional configurations.

`python splitter.py --mode <continuous|individual> [options]`

### Core Options

* `--mode continuous`: Merges all input videos into one stream, then applies the splitting logic.
* `--mode individual`: Processes and splits each input video separately.

### Splitting Methods

Use `--split` combined with `--split-val` to define how videos are cut.

* `range`: Extract a specific time section. 
  * Example: `--split range --split-val 00:01:00 00:01:30`
* `n-chunk`: Divide the video into a specific number of equal parts. 
  * Example: `--split n-chunk --split-val 3`
* `time-constraint`: Split the video evenly so no chunk exceeds a specific number of seconds. 
  * Example: `--split time-constraint --split-val 60`
* `size`: Split the video into chunks of a specific size in MB. 
  * Example: `--split size --split-val 25`

### Presets & Media

* `--preset`: Apply built-in platform configurations.
  * Options: `ig_reel`, `tiktok`, `yt_short`, `discord_free`, `discord_nitro`.
* `--media`: Extract specific tracks. 
  * Options: `audio`, `video`, `all`. Default is `all`.

### Modifiers

* `--files`: Specify a list of files to process instead of the entire `raw_videos` folder. 
  * Example: `--files vid1.mp4 vid2.mp4`
* `--precise`: Force re-encoding for exact cuts (slower, but necessary if cuts must be frame-accurate).

## Examples

Split a video into exactly 3 equal parts:
`python splitter.py --mode individual --split n-chunk --split-val 3`

Process videos to fit Discord's free tier size limit (25MB):
`python splitter.py --mode individual --preset discord_free`

Merge specific videos and split them into 60-second chunks formatted for Instagram Reels:
`python splitter.py --mode continuous --preset ig_reel --files clip1.mp4 clip2.mp4`
