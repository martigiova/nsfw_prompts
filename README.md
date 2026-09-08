# MiniMax H3 R2V su RunPod Serverless + Airtable

Il template [get.runpod.io/minimax-template](https://get.runpod.io/minimax-template) è un **Pod** con ComfyUI. Questo repo lo trasforma in un **endpoint serverless**: i pesi restano su un Network Volume, l’API accetta immagine / video / audio opzionale / prompt, e Airtable può lanciare i job.

Senza SSH sul pod e senza `RUNPOD_API_KEY` non posso montare il volume sul tuo account né scaricare i ~56 GB di pesi da qui. Il codice è pronto: quando mi dai SSH RunPod + token Airtable + bucket S3/R2, il passo successivo è eseguirlo sul volume e creare l’endpoint.

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

Volume consigliato: **100–150 GB**, stessa regione dell’endpoint. GPU: RTX 4090 24 GB minimo, meglio 48 GB. Timeout esecuzione: 30 minuti. `workersMin=0`, `idleTimeout` 60–120 s così i pesi restano in VRAM tra un job e l’altro.

## 1. Network volume (una volta)

1. Crea un Network Volume nella regione dove girerà il serverless.
2. Avvia il template MiniMax **con quel volume attaccato**.
3. SSH sul pod e lancia:

```bash
git clone <questo-repo> /workspace/nsfw_prompts
bash /workspace/nsfw_prompts/scripts/on_pod.sh
```

`on_pod.sh` scarica i pesi ufficiali, linka quelli già presenti nel template GUI e verifica i file. Le LoRA custom (`hmmotion_...`) vengono copiate dal pod se esistono.

## 2. Immagine worker

Preferita: wrappa **la stessa immagine del template MiniMax** (`ls250824/run-comfyui-minimax`) così restano custom node, CUDA e ComfyUI che usi già nel Pod. Il provisioning GUI non parte: i pesi arrivano dal volume.

```bash
docker build -t YOURUSER/minimax-h3-r2v:1.0 -f worker/Dockerfile.template .
docker push YOURUSER/minimax-h3-r2v:1.0
```

Alternativa più piccola, senza lo stack GUI: `worker/Dockerfile` da `runpod/worker-comfyui:5.10.0-base` + MiniMaxRefPack, VHS, rgthree.

Il node `MiniMaxH3ReferencePack` risolve i file con `os.path.join(input_dir, filename)` dove `input_dir` è la cartella input di ComfyUI, non il volume. Il worker scarica gli allegati Airtable lì (`/ComfyUI/input` sul template, `/comfyui/input` su worker-comfyui).

## 3. Endpoint serverless

In console RunPod: template serverless con quell’immagine, Network Volume selezionato, GPU **NVIDIA GeForce RTX 4090** (o A6000 / L40S / A100), execution timeout 1 800 000 ms.

Oppure, con le env in `.env.example`:

```bash
python scripts/provision_runpod.py
```

`provision_runpod.py` usa i nomi GPU esatti dell’API (`NVIDIA GeForce RTX 4090`, non `NVIDIA RTX 4090`). Env obbligatorie sull’endpoint:

- `AIRTABLE_TOKEN`, `AIRTABLE_BASE_ID`
- `BUCKET_ENDPOINT_URL`, `BUCKET_ACCESS_KEY_ID`, `BUCKET_SECRET_ACCESS_KEY`, `BUCKET_NAME`, `BUCKET_PUBLIC_URL_PREFIX`
- `OPENROUTER_API_KEY` solo se usi Auto Prompt
- `MOTION_LORA_NAME=hmmotion_minimax-h3_epoch40.safetensors` oppure `SKIP_MOTION_LORA=1`

## 4. Airtable

Schema e script: `airtable/SCHEMA.md` e `airtable/submit_job.js`.

Campi: Prompt, Image, Video, Audio (opzionale), Duration, Aspect, Auto Prompt, Status, Output, Job ID, Errore.

Inserisci una riga, metti `Status=Queued`. L’automazione manda solo l’id del record (secret `RUNPOD_ENDPOINT_ID` + `RUNPOD_API_KEY`): il worker legge gli allegati (audio opzionale incluso) e riscrive il record a fine generazione.

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

1. SSH (o `PUBLIC_KEY`) di un pod MiniMax con il Network Volume
2. `RUNPOD_API_KEY` e id del volume
3. Token Airtable + `baseId`
4. Credenziali S3 o R2
5. Registry Docker (Docker Hub / GHCR) dove pushare il worker

A quel punto bootstrap pesi, build/push immagine, creazione endpoint e verifica di un job Airtable si fanno da qui.
