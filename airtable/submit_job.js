/**
 * Airtable Automation → Scripting
 *
 * Trigger: When a record matches conditions, Status = "Queued"
 * Input variables: only `recordId` (the triggering record).
 *
 * Secrets: RUNPOD_API_KEY
 *
 * The worker reads Prompt / Image / Video / Audio from Airtable itself.
 * Replace ENDPOINT_ID with your serverless endpoint id.
 */
const ENDPOINT_ID = "REPLACE_ME";
const config = input.config();
const recordId = config.recordId;

if (!recordId) {
  throw new Error("Map the triggering record id to the recordId input");
}

const apiKey = input.secret("RUNPOD_API_KEY");
const response = await fetch(`https://api.runpod.ai/v2/${ENDPOINT_ID}/run`, {
  method: "POST",
  headers: {
    Authorization: `Bearer ${apiKey}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    input: { airtable_record_id: recordId },
  }),
});

const text = await response.text();
if (!response.ok) {
  throw new Error(`RunPod ${response.status}: ${text}`);
}

console.log(text);
