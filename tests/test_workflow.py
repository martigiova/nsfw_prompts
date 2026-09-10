import json
from pathlib import Path

from minimax_r2v.payload import parse_job_input
from minimax_r2v.workflow import build_workflow, LORA_NODE, TURBO_NODE, UNET_NODE

TEMPLATE = Path("workflows/api_template.json")


def _job(**overrides):
    payload = {
        "prompt": "The woman from <Picture 1> appears in <Video 1>",
        "images": ["https://example.com/a.png"],
        "video": "https://example.com/b.mp4",
        "duration": 8,
        "aspect_ratio": "9:16",
        "seed": 42,
    }
    payload.update(overrides)
    job, error = parse_job_input(payload)
    assert error is None
    return job


def test_template_has_no_secrets():
    raw = TEMPLATE.read_text(encoding="utf-8")
    assert "sk-or-" not in raw
    data = json.loads(raw)
    assert data["185"]["inputs"]["openrouter_api_key"] == ""
    assert data["185"]["inputs"]["prompt_provider"] == "none"
    assert data["184"]["inputs"]["ref_image_size"] == "match"


def test_dockerfile_pins_published_minimax_tag():
    text = Path("worker/Dockerfile.template").read_text(encoding="utf-8")
    assert "ls250824/run-comfyui-minimax:08092026" in text
    assert "run-comfyui-minimax:latest" not in text
    assert 'ENTRYPOINT ["/start-serverless.sh"]' in text


def test_patch_injects_prompt_refs_and_geometry():
    job = _job()
    references = [
        {"kind": "image", "file": "a.png"},
        {"kind": "video", "file": "b.mp4", "use_soundtrack": True},
    ]
    workflow = build_workflow(job, references, template_path=TEMPLATE, skip_motion_lora=True)
    pack = workflow["185"]["inputs"]
    assert pack["direction"] == job.prompt
    assert json.loads(pack["references_json"])["references"][0]["file"] == "a.png"
    assert pack["prompt_provider"] == "none"
    assert pack["openrouter_api_key"] == ""
    assert workflow["184"]["inputs"]["width"] == 1088
    assert workflow["184"]["inputs"]["height"] == 1920
    assert workflow["184"]["inputs"]["length"] == 192
    assert workflow["154"]["inputs"]["noise_seed"] == 42
    assert LORA_NODE not in workflow
    assert workflow[TURBO_NODE]["inputs"]["model"] == [UNET_NODE, 0]


def test_auto_prompt_sets_openrouter():
    job = _job(auto_prompt=True)
    workflow = build_workflow(
        job,
        [{"kind": "image", "file": "a.png"}],
        template_path=TEMPLATE,
        openrouter_api_key="sk-test",
        skip_motion_lora=True,
    )
    assert workflow["185"]["inputs"]["prompt_provider"] == "openrouter"
    assert workflow["185"]["inputs"]["openrouter_api_key"] == "sk-test"


def test_keeps_motion_lora_when_named():
    job = _job()
    workflow = build_workflow(
        job,
        [{"kind": "image", "file": "a.png"}],
        template_path=TEMPLATE,
        motion_lora_name="hmmotion_minimax-h3_epoch40.safetensors",
        skip_motion_lora=False,
    )
    assert workflow["137"]["class_type"] == "LoraLoaderModelOnly"
    assert workflow["137"]["inputs"]["lora_name"] == "hmmotion_minimax-h3_epoch40.safetensors"
    assert workflow["137"]["inputs"]["model"] == [UNET_NODE, 0]


def test_api_graph_avoids_gui_only_nodes():
    job = _job()
    workflow = build_workflow(
        job,
        [{"kind": "image", "file": "a.png"}],
        template_path=TEMPLATE,
        skip_motion_lora=True,
    )
    types = {node["class_type"] for node in workflow.values()}
    assert "PrimitiveFloat" not in types
    assert "Power Lora Loader (rgthree)" not in types
    assert "MiniMaxH3ReferencePack" in types
    assert "VHS_VideoCombine" in types


def test_strips_disabled_loras_and_bypasses_if_file_missing(tmp_path):
    job = _job()
    workflow = build_workflow(
        job,
        [{"kind": "image", "file": "a.png"}],
        template_path=TEMPLATE,
        motion_lora_name="hmmotion_minimax-h3_epoch40.safetensors",
        skip_motion_lora=False,
        lora_search_dirs=[tmp_path],
    )
    assert LORA_NODE not in workflow
    assert workflow[TURBO_NODE]["inputs"]["model"] == [UNET_NODE, 0]
