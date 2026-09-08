"""High-level job payload from Airtable or a direct API call."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass(frozen=True)
class MediaRef:
    kind: str  # image | video | audio
    url: str
    filename: str | None = None
    use_soundtrack: bool = True


@dataclass(frozen=True)
class AirtableTarget:
    record_id: str
    base_id: str | None = None
    table: str | None = None


@dataclass
class JobRequest:
    prompt: str
    images: list[MediaRef] = field(default_factory=list)
    videos: list[MediaRef] = field(default_factory=list)
    audios: list[MediaRef] = field(default_factory=list)
    duration: float = 8.0
    aspect_ratio: str = "9:16"
    seed: int = 0
    auto_prompt: bool = False
    job_type: str = "auto"
    motion_lora: str | None = None
    skip_motion_lora: bool = False
    airtable: AirtableTarget | None = None
    workflow: dict[str, Any] | None = None

    def all_media(self) -> list[MediaRef]:
        return [*self.images, *self.videos, *self.audios]


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _filename_from_url(url: str) -> str:
    path = url.split("?", 1)[0].rstrip("/")
    name = path.rsplit("/", 1)[-1]
    return name or "file.bin"


def _media_from_value(value: Any, kind: str) -> MediaRef | None:
    if value is None or value == "":
        return None
    if isinstance(value, MediaRef):
        return value
    if isinstance(value, str):
        return MediaRef(kind=kind, url=value, filename=_filename_from_url(value))
    if isinstance(value, dict):
        url = value.get("url") or value.get("href")
        if not url:
            return None
        return MediaRef(
            kind=kind,
            url=url,
            filename=value.get("filename") or value.get("name") or _filename_from_url(url),
            use_soundtrack=bool(value.get("use_soundtrack", True)),
        )
    return None


def _media_list(value: Any, kind: str, limit: int) -> list[MediaRef]:
    items: list[MediaRef] = []
    for raw in _as_list(value):
        item = _media_from_value(raw, kind)
        if item:
            items.append(item)
        if len(items) >= limit:
            break
    return items


def parse_job_input(job_input: Any) -> tuple[JobRequest | None, str | None]:
    if job_input is None:
        return None, "Please provide input"
    if isinstance(job_input, str):
        import json

        try:
            job_input = json.loads(job_input)
        except json.JSONDecodeError:
            return None, "Invalid JSON format in input"
    if not isinstance(job_input, dict):
        return None, "Input must be an object"

    # Advanced escape hatch: raw ComfyUI API workflow
    if job_input.get("workflow") and not job_input.get("prompt"):
        return (
            JobRequest(
                prompt="",
                workflow=job_input["workflow"],
                airtable=_airtable_from(job_input),
            ),
            None,
        )

    prompt = (job_input.get("prompt") or job_input.get("direction") or "").strip()
    if not prompt:
        return None, "Missing 'prompt'"

    images = _media_list(
        job_input.get("images") or job_input.get("image") or job_input.get("image_url"),
        "image",
        9,
    )
    videos = _media_list(
        job_input.get("videos") or job_input.get("video") or job_input.get("video_url"),
        "video",
        3,
    )
    audios = _media_list(
        job_input.get("audios") or job_input.get("audio") or job_input.get("audio_url"),
        "audio",
        3,
    )

    if not images and not videos:
        return None, "Provide at least one reference image or video"

    duration = float(job_input.get("duration") or job_input.get("length_seconds") or 8)
    if duration <= 0 or duration > 15:
        return None, "duration must be between 0 and 15 seconds"

    seed = job_input.get("seed", 0)
    try:
        seed = int(seed)
    except (TypeError, ValueError):
        return None, "seed must be an integer"

    auto_prompt = _as_bool(job_input.get("auto_prompt", False))
    skip_motion = _as_bool(job_input.get("skip_motion_lora", False))

    return (
        JobRequest(
            prompt=prompt,
            images=images,
            videos=videos,
            audios=audios,
            duration=duration,
            aspect_ratio=str(job_input.get("aspect_ratio") or job_input.get("aspect") or "9:16"),
            seed=seed,
            auto_prompt=auto_prompt,
            job_type=str(job_input.get("job_type") or "auto"),
            motion_lora=job_input.get("motion_lora"),
            skip_motion_lora=skip_motion,
            airtable=_airtable_from(job_input),
        ),
        None,
    )


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _airtable_from(job_input: dict[str, Any]) -> AirtableTarget | None:
    raw = job_input.get("airtable")
    record_id = job_input.get("airtable_record_id")
    if isinstance(raw, dict):
        record_id = raw.get("record_id") or record_id
        if record_id:
            return AirtableTarget(
                record_id=str(record_id),
                base_id=raw.get("base_id"),
                table=raw.get("table"),
            )
    if record_id:
        return AirtableTarget(record_id=str(record_id))
    return None


def references_manifest(saved: Iterable[tuple[MediaRef, str]]) -> list[dict[str, Any]]:
    """Build MiniMaxH3ReferencePack references_json.references."""
    refs: list[dict[str, Any]] = []
    for original, filename in saved:
        item: dict[str, Any] = {"kind": original.kind, "file": filename}
        if original.kind == "video":
            item["use_soundtrack"] = original.use_soundtrack
        refs.append(item)
    return refs
