from minimax_r2v.graph import (
    assert_workflow_links,
    dangling_links,
    missing_class_types,
)
from minimax_r2v.payload import parse_job_input
from minimax_r2v.workflow import build_workflow, TURBO_NODE, UNET_NODE
from pathlib import Path

TEMPLATE = Path("workflows/api_template.json")


def _job():
    job, error = parse_job_input(
        {
            "prompt": "The woman from <Picture 1> appears in <Video 1>",
            "images": ["https://example.com/a.png"],
            "video": "https://example.com/b.mp4",
        }
    )
    assert error is None
    return job


def test_skip_motion_does_not_leave_dangling_137():
    workflow = build_workflow(
        _job(),
        [{"kind": "image", "file": "a.png"}],
        template_path=TEMPLATE,
        skip_motion_lora=True,
    )
    assert dangling_links(workflow) == []
    assert missing_class_types(workflow) == []
    assert "137" not in workflow
    assert workflow[TURBO_NODE]["inputs"]["model"] == [UNET_NODE, 0]
    assert_workflow_links(workflow)


def test_motion_lora_graph_is_fully_wired():
    workflow = build_workflow(
        _job(),
        [{"kind": "image", "file": "a.png"}],
        template_path=TEMPLATE,
        motion_lora_name="hmmotion_minimax-h3_epoch40.safetensors",
        skip_motion_lora=False,
    )
    assert dangling_links(workflow) == []
    assert_workflow_links(workflow)
    assert workflow["158"]["inputs"]["model"] == ["137", 0]
    assert workflow["137"]["inputs"]["model"] == ["135", 0]


def test_dangling_links_reports_missing_node():
    workflow = build_workflow(
        _job(),
        [{"kind": "image", "file": "a.png"}],
        template_path=TEMPLATE,
        skip_motion_lora=True,
    )
    workflow["158"]["inputs"]["model"] = ["137", 0]
    assert "158.model -> 137" in dangling_links(workflow)
    try:
        assert_workflow_links(workflow)
        raise AssertionError("should have raised")
    except ValueError as exc:
        assert "137" in str(exc)


def test_missing_vhs_node_is_rejected():
    workflow = build_workflow(
        _job(),
        [{"kind": "image", "file": "a.png"}],
        template_path=TEMPLATE,
        skip_motion_lora=True,
    )
    del workflow["119"]
    try:
        assert_workflow_links(workflow)
        raise AssertionError("should have raised")
    except ValueError as exc:
        assert "VHS_VideoCombine" in str(exc)
