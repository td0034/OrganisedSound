#!/usr/bin/env python3
import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate rater session links via the running rater survey server."
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:18080",
        help="Base URL for the rater survey server (default: http://localhost:18080).",
    )
    parser.add_argument("--start", type=int, default=1, help="Start index (default: 1).")
    parser.add_argument("--end", type=int, default=100, help="End index (default: 100).")
    parser.add_argument(
        "--prefix",
        default="",
        help="Optional prefix for rater labels (e.g., 'R').",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("Rater Survey/hosting/session_links_001_100.csv"),
        help="Output path for the links file.",
    )
    return parser.parse_args()


def create_session(base_url: str, label: str) -> dict:
    payload = json.dumps({"rater_label": label}).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/session/create",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        data = resp.read().decode("utf-8")
    return json.loads(data)


def main() -> int:
    args = parse_args()
    if args.end < args.start:
        print("End must be >= start.", file=sys.stderr)
        return 1

    base_url = args.base_url.rstrip("/")
    width = max(len(str(args.end)), 3)

    args.output.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for idx in range(args.start, args.end + 1):
        label = f"{args.prefix}{idx:0{width}d}"
        try:
            res = create_session(base_url, label)
        except urllib.error.URLError as exc:
            print(f"Failed to create session for {label}: {exc}", file=sys.stderr)
            return 1
        share_url = res.get("share_url", "")
        link = share_url
        if share_url.startswith("/"):
            link = f"{base_url}{share_url}"
        rows.append((label, res.get("token", ""), link))

    with args.output.open("w", encoding="utf-8", newline="") as handle:
        handle.write("rater_label,token,session_link\n")
        for row in rows:
            handle.write(",".join(str(item) for item in row) + "\n")

    print(f"Wrote {len(rows)} links to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
