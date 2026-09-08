/**
 * Airtable Automation → Scripting
 *
 * Trigger: When a record matches conditions, Status = "Queued"
 * Input variables (map them in the automation UI):
 *   recordId, prompt, imageUrl, videoUrl, audioUrl, duration, aspectRatio, autoPrompt
 *
 * Secrets:
 *   RUNPOD_API_KEY
 *
 * Replace ENDPOINT_ID with your serverless endpoint id.
 */
const ENDPOINT_ID = "REPLACE_ME";
const config = input.config();

const recordId = config.recordId;
const prompt = config.prompt;
const imageUrl = config.imageUrl || "";
const videoUrl = config.videoUrl || "";
const audioUrl = config.audioUrl || "";
const duration = Number(config.duration || 8);
const aspectRatio = config.aspectRatio || "9:16";
const autoPrompt = Boolean(config.autoPrompt);

if (!recordId || !prompt) {
  throw new Error("recordId and prompt are required");
}

const images = imageUrl
  .split(",")
  .map((url) => url.trim())
  .filter(Boolean);

const body = {
  input: {
    prompt,
    images,
    video: videoUrl || undefined,
    audio: audioUrl || undefined,
    duration,
    aspect_ratio: aspectRatio,
    auto_prompt: autoPrompt,
    airtable_record_id: recordId,
  },
};

const apiKey = input.secret("RUNPOD_API_KEY");
const response = await fetch(`https://api.runpod.ai/v2/${ENDPOINT_ID}/run`, {
  method: "POST",
  headers: {
    Authorization: `Bearer ${apiKey}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify(body),
});

const text = await response.text();
if (!response.ok) {
  throw new Error(`RunPod ${response.status}: ${text}`);
}

console.log(text);
