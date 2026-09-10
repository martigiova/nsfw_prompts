from minimax_r2v.payload import parse_job_input, references_manifest, MediaRef


def test_airtable_style_payload():
    job, error = parse_job_input(
        {
            "prompt": "A woman from <Picture 1> walks like <Video 1>",
            "image": {
                "url": "https://v5.airtableusercontent.com/img.png",
                "filename": "face.png",
            },
            "video": "https://cdn.example.com/clip.mp4",
            "audio": None,
            "duration": 8,
            "aspect_ratio": "9:16",
            "airtable_record_id": "rec123",
        }
    )
    assert error is None
    assert job.prompt.startswith("A woman")
    assert len(job.images) == 1
    assert job.images[0].filename == "face.png"
    assert len(job.videos) == 1
    assert job.audios == []
    assert job.airtable.record_id == "rec123"


def test_airtable_record_id_only_is_allowed():
    job, error = parse_job_input({"airtable_record_id": "recOnly"})
    assert error is None
    assert job.needs_hydrate() is True
    assert job.airtable.record_id == "recOnly"


def test_requires_prompt_and_media():
    job, error = parse_job_input({"prompt": "hi"})
    assert job is None
    assert "image or video" in error

    job, error = parse_job_input({"video": "https://x/v.mp4"})
    assert job is None
    assert "prompt" in error


def test_references_manifest_keeps_soundtrack_flag():
    refs = references_manifest(
        [
            (MediaRef("image", "http://x/a.png", "a.png"), "a.png"),
            (MediaRef("video", "http://x/b.mp4", "b.mp4", use_soundtrack=True), "b.mp4"),
            (MediaRef("audio", "http://x/c.wav", "c.wav"), "c.wav"),
        ],
    )
    assert refs[0] == {"kind": "image", "file": "a.png"}
    assert refs[1]["use_soundtrack"] is True
    assert refs[2]["kind"] == "audio"
