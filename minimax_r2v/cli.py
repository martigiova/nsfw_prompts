"""CLI helpers: build a workflow locally or submit a RunPod job."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests

from minimax_r2v.download import download_weights
from minimax_r2v.graph import assert_workflow_links
from minimax_r2v.payload import parse_job_input
from minimax_r2v.volume import missing_weights, volume_is_present
from minimax_r2v.workflow import build_workflow


def build_cmd(args: argparse.Namespace) -> int:
    payload = {
        "prompt": args.prompt,
        "images": args.image or [],
        "video": args.video,
        "audio": args.audio,
        "duration": args.duration,
        "aspect_ratio": args.aspect,
        "seed": args.seed,
        "auto_prompt": args.auto_prompt,
    }
    job, error = parse_job_input(payload)
    if error:
        print(error, file=sys.stderr)
        return 1
    references = []
    for media in job.all_media():
        name = Path(media.url).name
        references.append({"kind": media.kind, "file": name, **(
            {"use_soundtrack": media.use_soundtrack} if media.kind == "video" else {}
        )})
        # parse_job_input stored URL as url; for local files treat basename as already on disk
    workflow = build_workflow(
        job,
        references,
        template_path=args.template,
        skip_motion_lora=args.skip_motion_lora,
        motion_lora_name=args.motion_lora,
    )
    assert_workflow_links(workflow)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(workflow, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


def check_cmd(args: argparse.Namespace) -> int:
    payload = {
        "prompt": "The woman from <Picture 1> appears in <Video 1>",
        "images": ["face.png"],
        "video": "clip.mp4",
        "duration": 8,
        "aspect_ratio": "9:16",
    }
    job, error = parse_job_input(payload)
    if error:
        print(error, file=sys.stderr)
        return 1
    workflow = build_workflow(
        job,
        [
            {"kind": "image", "file": "face.png"},
            {"kind": "video", "file": "clip.mp4", "use_soundtrack": True},
        ],
        template_path=args.template,
        skip_motion_lora=True,
    )
    assert_workflow_links(workflow)
    print("workflow graph: OK")
    if volume_is_present():
        missing = missing_weights()
        if missing:
            print("volume missing: " + ", ".join(missing), file=sys.stderr)
            return 1
        print("volume weights: OK")
    else:
        print("volume: not mounted (skip)")
    return 0


def download_cmd(args: argparse.Namespace) -> int:
    download_weights(args.volume_root)
    return 0


def submit_cmd(args: argparse.Namespace) -> int:
    endpoint = os.environ.get("RUNPOD_ENDPOINT_ID") or args.endpoint
    api_key = os.environ.get("RUNPOD_API_KEY")
    if not endpoint or not api_key:
        print("Set RUNPOD_ENDPOINT_ID and RUNPOD_API_KEY", file=sys.stderr)
        return 1
    payload = json.loads(Path(args.payload).read_text(encoding="utf-8"))
    url = f"https://api.runpod.ai/v2/{endpoint}/run"
    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={"input": payload},
        timeout=30,
    )
    print(response.status_code)
    print(response.text)
    response.raise_for_status()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="minimax-r2v")
    sub = parser.add_subparsers(dest="cmd", required=True)

    build = sub.add_parser("build-workflow", help="Patch the API template without GPU")
    build.add_argument("--prompt", required=True)
    build.add_argument("--image", action="append")
    build.add_argument("--video")
    build.add_argument("--audio")
    build.add_argument("--duration", type=float, default=8)
    build.add_argument("--aspect", default="9:16")
    build.add_argument("--seed", type=int, default=0)
    build.add_argument("--auto-prompt", action="store_true")
    build.add_argument("--skip-motion-lora", action="store_true")
    build.add_argument("--motion-lora", default="hmmotion_minimax-h3_epoch40.safetensors")
    build.add_argument("--template", default="workflows/api_template.json")
    build.add_argument("--output", type=Path, default=Path("tmp_outputs/workflow.json"))
    build.set_defaults(func=build_cmd)

    submit = sub.add_parser("submit", help="POST a JSON payload to RunPod /run")
    submit.add_argument("payload")
    submit.add_argument("--endpoint")
    submit.set_defaults(func=submit_cmd)

    check = sub.add_parser("check", help="Validate the API graph (and volume if mounted)")
    check.add_argument("--template", default="workflows/api_template.json")
    check.set_defaults(func=check_cmd)

    download = sub.add_parser("download-weights", help="Download MiniMax H3 weights onto VOLUME_ROOT")
    download.add_argument("--volume-root", default=None)
    download.set_defaults(func=download_cmd)

    parsed = parser.parse_args(argv)
    return parsed.func(parsed)


if __name__ == "__main__":
    raise SystemExit(main())
