# 9x3 Montage Generator

This script builds labeled 9x3 montage snapshots (plus a participant ID column) from the clips in
`Rater Survey/rotated_clips`. It can generate a montage for every second or specific timestamps.

## Requirements

- Python 3.8+ (stdlib only)
- `ffmpeg` and `ffprobe` available in your PATH

## Setup (venv)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

Default (15s, 30s, 45s):

```bash
python3 generate_montage.py
```

Every second (0s up to the shortest clip):

```bash
python3 generate_montage.py --every-second
```

Common options:

```bash
python3 generate_montage.py --scale 2
python3 generate_montage.py --seed 42
python3 generate_montage.py --no-rotate
python3 generate_montage.py --times 5,10,12.5
```

## Output

- Montages: `Montage/9x3/output/montage_*.png`
- Row mapping: `Montage/9x3/output/row_order.txt` (maps row + numeric ID to participant)

Notes:
- The left column shows numeric participant IDs (1-9) to obscure actual IDs.
- All thumbnails are square and cropped to remove horizontal white space.
