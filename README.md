# MiniMax H3 R2V su RunPod Serverless + Airtable

Il template [get.runpod.io/minimax-template](https://get.runpod.io/minimax-template) è un **Pod** con ComfyUI. Questo repo lo trasforma in un **endpoint serverless**: i pesi restano su un Network Volume, l’API accetta immagine / video / audio opzionale / prompt, e Airtable può lanciare i job.

Senza SSH sul pod e senza `RUNPOD_API_KEY` non posso montare il volume sul tuo account né scaricare i ~56 GB di pesi da qui. Il codice è pronto: quando mi dai `RUNPOD_API_KEY` + id del volume (e opzionalmente token Airtable + bucket S3/R2), il passo successivo è `CONFIRM_BOOTSTRAP=1 python scripts/bootstrap_via_runpod.py` e poi creare l’endpoint.

Il pod CPU di bootstrap viene creato **nella stessa data center del volume**. Lo script scrive `status.json` anche se il download fallisce, così non resta acceso 2 ore in silenzio.

## Architettura

```
Airtable (Status = Queued, solo record id)
    → script submit_job.js
    → POST https://api.runpod.ai/v2/<endpoint>/run
    → Worker GPU (stesso stack ComfyUI del template MiniMax)
         legge Prompt/Image/Video/Audio dal record Airtable
         legge i pesi da /runpod-volume/models o /runpod-volume/ComfyUI/models
    → upload mp4 su S3/R2
    → PATCH Airtable (Status=Done, Output=video)
```

Su un Pod il volume è `/workspace`. Sul serverless lo stesso volume è `/runpod-volume`. Il worker cerca i pesi in entrambi i layout (`models/` in radice e `ComfyUI/models/`).

## Pesi del workflow allegato

Tutti da [`Comfy-Org/MiniMax-H3`](https://huggingface.co/Comfy-Org/MiniMax-H3), gli stessi file del graph `MiniMax R2V - Auto Prompting + Reference Manager`:

| File | Cartella | Dimensione |
| --- | --- | --- |
| `minimax_h3_ref2va_pruned_int8_convrot.safetensors` | `models/diffusion_models` | ~21 GB |
| `qwen3vl_32b_minimax_h3_int8_convrot.safetensors` | `models/text_encoders` | ~27 GB |
| `minimax_h3_video_vae_fp16.safetensors` | `models/vae` | ~5.2 GB |
| `minimax_h3_audio_vae_fp32.safetensors` | `models/vae` | ~0.6 GB |
| `minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors` | `models/loras` | ~2 GB |
| `hmmotion_minimax-h3_epoch40.safetensors` | `models/loras` | già sul pod GUI |

Volume consigliato: **100–150 GB** di Network Volume (pesi MiniMax), stessa data center dell’endpoint. Container disk del worker: **250 GB** (come il deploy GUI). **Non** pinna EU-RO-1 se il catalogo Serverless 4090 è `LOW` (i worker restano `throttled`). `scripts/create_volume.py` sceglie un DC con stock `HIGH` se `RUNPOD_DATA_CENTER_ID` è vuoto. GPU preferita: **RTX PRO 6000 Blackwell Server Edition** (96 GB); fallback RTX 4090 24 GB. Timeout esecuzione: 30 minuti. `workersMin=0`, `idleTimeout` 60–120 s così i pesi restano in VRAM tra un job e l’altro.

## 1. Network volume (una volta)

1. Crea un Network Volume (100–150 GB) nella regione dove girerà il serverless.
2. Popolalo **senza SSH e senza GPU** (pod CPU, ~56 GB da Hugging Face):

```bash
export RUNPOD_API_KEY=...
export RUNPOD_NETWORK_VOLUME_ID=...
python scripts/deploy.py --check
CONFIRM_BOOTSTRAP=1 python scripts/bootstrap_via_runpod.py
```

Il pod CPU clona questo repo, lancia `scripts/on_pod.sh`, verifica i file e si spegne.

In alternativa, avvia il template MiniMax **con quel volume attaccato**, SSH, e:

```bash
git clone <questo-repo> /workspace/nsfw_prompts
bash /workspace/nsfw_prompts/scripts/on_pod.sh
```

`on_pod.sh` scarica i pesi ufficiali, linka quelli già presenti nel template GUI e verifica i file. Le LoRA custom (`hmmotion_...`) vengono copiate dal pod se esistono.

## 2. Immagine worker

Preferita: usa **direttamente** `ls250824/run-comfyui-minimax:08092026` (su Docker Hub **non esiste** `:latest`). Il codice worker sta sul Network Volume in `nsfw_prompts/`; non serve build/push di un’immagine custom.

L’immagine GUI ha `CMD ["/start.sh"]` (provisioning ComfyUI + Code Server) e **ignora** gli argomenti extra. Il provisioning scrive `args` in JSON `{"entrypoint":["/bin/bash","-lc"],"cmd":[...]}` così parte `worker/start_from_volume.sh`. Quello script disattiva `ComfyUI-Login` (altrimenti `/prompt` risponde 401).

```bash
docker build -t YOURUSER/minimax-h3-r2v:1.0 -f worker/Dockerfile.template .
docker push YOURUSER/minimax-h3-r2v:1.0
```

(Opzionale. Il provisioning default usa l’immagine pubblica + codice sul volume.)

Alternativa più piccola, senza lo stack GUI: `worker/Dockerfile` da `runpod/worker-comfyui:5.10.0-base` + MiniMaxRefPack, VHS, rgthree.

Il node `MiniMaxH3ReferencePack` risolve i file con `os.path.join(input_dir, filename)` dove `input_dir` è la cartella input di ComfyUI, non il volume. Il worker scarica gli allegati Airtable lì (`/ComfyUI/input` sul template, `/comfyui/input` su worker-comfyui).

## 3. Endpoint serverless

In console RunPod: template serverless con quell’immagine, Network Volume selezionato, GPU **NVIDIA RTX PRO 6000 Blackwell Server Edition** (96 GB, stessa scheda del deploy GUI), fallback 4090 / A6000 / L40S. Container disk **250 GB**. Timeout 1 800 000 ms.

Oppure, con le env in `.env.example`:

```bash
python scripts/deploy.py --check
python scripts/provision_runpod.py
# oppure, per spostare un endpoint già creato su un volume nuovo:
python scripts/provision_runpod.py --update
```

`provision_runpod.py` usa i nomi GPU esatti dell’API (`NVIDIA RTX PRO 6000 Blackwell Server Edition`, `NVIDIA GeForce RTX 4090`) e attacca l’endpoint alla **stessa data center del Network Volume**. Container disk default **250 GB**. Env obbligatorie sull’endpoint:

- `AIRTABLE_TOKEN`, `AIRTABLE_BASE_ID`
- `BUCKET_ENDPOINT_URL`, `BUCKET_ACCESS_KEY_ID`, `BUCKET_SECRET_ACCESS_KEY`, `BUCKET_NAME`, `BUCKET_PUBLIC_URL_PREFIX`
- `OPENROUTER_API_KEY` solo se usi Auto Prompt
- `MOTION_LORA_NAME=hmmotion_minimax-h3_epoch40.safetensors` oppure `SKIP_MOTION_LORA=1`

## 4. Airtable

Schema e script: `airtable/SCHEMA.md` e `airtable/submit_job.js`.

Campi: Prompt, Image, Video, Audio (opzionale), Duration, Aspect, Auto Prompt, Status, Output, Job ID, Errore.

Inserisci una riga, metti `Status=Queued`. L’automazione nativa Airtable **non si crea via API**: incolla `airtable/submit_job.js` (trigger Status=Queued, secrets `RUNPOD_ENDPOINT_ID` + `RUNPOD_API_KEY`). In alternativa, dallo stesso repo:

```bash
python scripts/submit_airtable_job.py --image https://.../face.jpg --prompt "The person from <Picture 1> smiles"
# fallback se il serverless resta sul CMD GUI:
CONFIRM_GPU_JOB=1 python scripts/run_gpu_pod_job.py --record recXXXXXXXX
```

Il worker legge gli allegati (audio opzionale incluso) e riscrive il record a fine generazione.

L’mp4 MiniMax supera i 5 MB: Airtable accetta allegati grandi solo da **URL pubblico**. Serve S3 o Cloudflare R2.

## 5. Chiamata API diretta

```bash
curl -X POST https://api.runpod.ai/v2/$RUNPOD_ENDPOINT_ID/run \
  -H "Authorization: Bearer $RUNPOD_API_KEY" \
  -H "Content-Type: application/json" \
  -d @examples/runpod_payload.json
```

Payload:

```json
{
  "prompt": "The woman from <Picture 1> appears in the scene from <Video 1>...",
  "images": ["https://.../face.png"],
  "video": "https://.../motion.mp4",
  "audio": null,
  "duration": 8,
  "aspect_ratio": "9:16",
  "auto_prompt": false,
  "airtable_record_id": "rec..."
}
```

`auto_prompt: true` usa OpenRouter come nel workflow originale (Gemini Flash) e riscrive la direction. Con `false` il prompt di Airtable va dritto a MiniMax.

## Workflow

`workflows/api_template.json` è il graph che hai esportato, ripulito per l’API:

- niente preview TAE (risparmio VRAM)
- niente chiave OpenRouter nel JSON
- `MiniMaxH3ReferencePack` riceve `references_json` costruito dal worker
- turbo LoRA 4-step sempre on
- motion LoRA configurabile

## Test locali (senza GPU)

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m pytest -q
python3 -m minimax_r2v check
python3 -m minimax_r2v build-workflow \
  --prompt "The woman from <Picture 1> walks like <Video 1>" \
  --image face.png \
  --video clip.mp4 \
  --skip-motion-lora \
  --output tmp_outputs/workflow.json
```

## Sicurezza

Nel workflow che hai caricato c’era una `openrouter_api_key` in chiaro. Ruotala su OpenRouter: finisce dentro ogni export ComfyUI. Qui la chiave sta solo in env.

## Cosa mi serve per chiudere il deploy

1. `RUNPOD_API_KEY` e `RUNPOD_NETWORK_VOLUME_ID` (SSH non è più obbligatorio: il bootstrap gira su un pod CPU)
2. Token Airtable + `baseId`
3. Credenziali S3 o R2
4. Registry Docker (Docker Hub / GHCR) dove pushare il worker

A quel punto: `CONFIRM_BOOTSTRAP=1 python scripts/bootstrap_via_runpod.py` → build/push `worker/Dockerfile.template` → `python scripts/provision_runpod.py` → incolla `airtable/submit_job.js`.
