# Clip Cropping (Square)

This utility crops the rater survey clips to a centered square using the shorter dimension (e.g., 1920x1080 -> 1080x1080) and writes the results to a new folder so the originals remain untouched. It can also migrate `manifest.csv` to the new folder.

## Requirements
- Python 3.9+ (for the script)
- ffmpeg on your PATH

## Create a virtual environment
From the repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

## Run the cropper
From the repo root:

```bash
python "Rater Survey/clip_cropping/crop_clips.py" \
  --input-dir "Rater Survey/clips" \
  --output-dir "Rater Survey/clips_square"
```

This will:
- create `Rater Survey/clips_square`
- write cropped clips into that folder
- write `Rater Survey/clips_square/manifest.csv` (if `Rater Survey/clips/manifest.csv` exists)

## Manifest path options
By default the migrated manifest keeps filenames only (like the original). If you want filepaths that include the new folder, add a prefix:

```bash
python "Rater Survey/clip_cropping/crop_clips.py" \
  --input-dir "Rater Survey/clips" \
  --output-dir "Rater Survey/clips_square" \
  --manifest-prefix "clips_square/"
```

You can also override manifest locations:

```bash
python "Rater Survey/clip_cropping/crop_clips.py" \
  --manifest-in "Rater Survey/clips/manifest.csv" \
  --manifest-out "Rater Survey/clips_square/manifest.csv"
```

## Re-running
Use `--overwrite` to replace existing outputs:

```bash
python "Rater Survey/clip_cropping/crop_clips.py" --overwrite
```

## Using the cropped clips in the survey
The survey app reads clips from `CLIPS_DIR` in `Rater Survey/docker-compose.yml`. To use the cropped clips, update the volume mapping to point at `./clips_square` (and keep `CLIPS_DIR` as `/data/clips`).
