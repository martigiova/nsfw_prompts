# Schema Airtable

Crea una tabella `Generazioni` con questi campi (i nomi devono coincidere con le env del worker, o cambia le env).

| Campo | Tipo | Note |
| --- | --- | --- |
| `Prompt` | Long text | Testo / direction MiniMax. Usa i tag `<Picture 1>`, `<Video 1>`, `<Audio 1>` se `Auto Prompt` è spento. |
| `Image` | Attachment | 1–9 immagini di riferimento |
| `Video` | Attachment | 1 video di riferimento (consigliato) |
| `Audio` | Attachment | Opzionale, fino a 3 clip |
| `Duration` | Number | Secondi, default 8, max 15 |
| `Aspect` | Single select | `9:16`, `16:9`, `1:1` |
| `Auto Prompt` | Checkbox | Se attivo, OpenRouter riscrive il prompt dal workflow originale |
| `Status` | Single select | `Queued`, `Running`, `Done`, `Error` |
| `Output` | Attachment | Il worker ci attacca l'mp4 a fine job |
| `Job ID` | Single line text | Id RunPod |
| `Errore` | Long text | Messaggio se fallisce |

## Automazione

1. Automation: **When record matches conditions** → `Status` is `Queued`.
2. Action: **Run script**, incolla `submit_job.js`.
3. Input variable: `recordId` = id del record che ha triggerato.
4. Secret: `RUNPOD_API_KEY`.

Il worker legge da solo Prompt, Image (anche più file), Video, Audio opzionale, Duration, Aspect, Auto Prompt. A fine job fa PATCH: `Status=Done` e `Output` con URL pubblico S3/R2.

Senza bucket S3/R2 l'mp4 non può essere allegato (limite 5 MB dell'upload diretto Airtable). Configura un bucket.
