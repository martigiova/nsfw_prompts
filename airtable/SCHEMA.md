# Schema Airtable — tabella `Minimax`

Campi usati dal worker (i nomi coincidono con le env, default sotto).

| Campo | Tipo | Note |
| --- | --- | --- |
| `Prompt` | Long text | Direction MiniMax (`<Picture 1>`, `<Video 1>`, …) |
| `Image` | Attachment | Immagini di riferimento |
| `Video` | Attachment | Video di riferimento |
| `Audio` | Attachment | Opzionale |
| `Status` | Single select | `Queued`, `Running`, `Done`, `Error` |
| `Output` | URL | Link pubblico R2 (`References/<job>/…mp4`) |
| `Job ID` | Single line text | Id job RunPod |
| `Errore` | Long text | Messaggio se fallisce |

`python scripts/setup_airtable.py` crea/aggiorna questi campi.

## Automazione

1. When record matches → `Status` is `Queued`
2. Run script: incolla `submit_job.js`
3. Input `recordId` = record trigger
4. Secrets: `RUNPOD_API_KEY`, `RUNPOD_ENDPOINT_ID`
