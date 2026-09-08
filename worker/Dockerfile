ARG BASE_IMAGE=runpod/worker-comfyui:5.10.0-base
FROM ${BASE_IMAGE}

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    WORKFLOW_PATH=/app/workflows/api_template.json \
    COMFY_INPUT_DIR=/comfyui/input \
    COMFY_OUTPUT_DIR=/comfyui/output

COPY worker/extra_model_paths.yaml /comfyui/extra_model_paths.yaml

WORKDIR /comfyui/custom_nodes
RUN git clone --depth 1 https://github.com/Hearmeman24/ComfyUI-MiniMaxRefPack.git \
 && git clone --depth 1 https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git \
 && git clone --depth 1 https://github.com/rgthree/rgthree-comfy.git \
 && ( [ -f ComfyUI-MiniMaxRefPack/requirements.txt ] && uv pip install -r ComfyUI-MiniMaxRefPack/requirements.txt || true ) \
 && ( [ -f ComfyUI-VideoHelperSuite/requirements.txt ] && uv pip install -r ComfyUI-VideoHelperSuite/requirements.txt || true )

WORKDIR /
COPY minimax_r2v /app/minimax_r2v
COPY workflows /app/workflows
COPY worker/handler.py /handler.py
COPY worker/requirements.txt /app/requirements.txt
RUN uv pip install -r /app/requirements.txt

WORKDIR /app
