ARG BASE_IMAGE=runpod/worker-comfyui:5.10.0-base
FROM ${BASE_IMAGE}

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    WORKFLOW_PATH=/app/workflows/api_template.json \
    COMFY_INPUT_DIR=/comfyui/input \
    COMFY_OUTPUT_DIR=/comfyui/output

COPY worker/extra_model_paths.yaml /comfyui/extra_model_paths.yaml

WORKDIR /comfyui/custom_nodes
RUN set -eux; \
    if [ ! -d ComfyUI-MiniMaxRefPack ]; then \
      git clone --depth 1 https://github.com/Hearmeman24/ComfyUI-MiniMaxRefPack.git; \
    fi; \
    if [ ! -d ComfyUI-VideoHelperSuite ]; then \
      git clone --depth 1 https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git; \
    fi; \
    if [ ! -d rgthree-comfy ]; then \
      git clone --depth 1 https://github.com/rgthree/rgthree-comfy.git; \
    fi; \
    if [ -f ComfyUI-MiniMaxRefPack/requirements.txt ]; then uv pip install -r ComfyUI-MiniMaxRefPack/requirements.txt; fi; \
    if [ -f ComfyUI-VideoHelperSuite/requirements.txt ]; then uv pip install -r ComfyUI-VideoHelperSuite/requirements.txt; fi

WORKDIR /
COPY minimax_r2v /app/minimax_r2v
COPY workflows /app/workflows
COPY worker/handler.py /handler.py
COPY worker/requirements.txt /app/requirements.txt
RUN uv pip install -r /app/requirements.txt

WORKDIR /app
