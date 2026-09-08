/**
 * Airtable Automation → Scripting
 *
 * Trigger: When a record matches conditions, Status = "Queued"
 * Input variables:
 *   - recordId (required) = the triggering record
 *   - tableName (optional, default Generazioni)
 *
 * Secrets:
 *   - RUNPOD_API_KEY
 *   - RUNPOD_ENDPOINT_ID
 *
 * The worker reads Prompt / Image / Video / Audio from Airtable itself.
 */
const config = input.config();
const recordId = config.recordId;
const tableName = config.tableName || "Generazioni";
const endpointId = input.secret("RUNPOD_ENDPOINT_ID");
const apiKey = input.secret("RUNPOD_API_KEY");

if (!recordId) {
  throw new Error("Map the triggering record id to the recordId input");
}
if (!endpointId || endpointId === "REPLACE_ME") {
  throw new Error("Set the RUNPOD_ENDPOINT_ID automation secret");
}

const table = base.getTable(tableName);

async function markError(message) {
  try {
    await table.updateRecordAsync(recordId, {
      Status: "Error",
      Errore: String(message).slice(0, 10000),
    });
  } catch (updateError) {
    console.error("Failed to write Airtable error", updateError);
  }
}

const response = await fetch(`https://api.runpod.ai/v2/${endpointId}/run`, {
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
  const message = `RunPod ${response.status}: ${text}`;
  await markError(message);
  throw new Error(message);
}

let payload = {};
try {
  payload = JSON.parse(text);
} catch (parseError) {
  await markError(`RunPod returned non-JSON: ${text}`);
  throw parseError;
}

if (payload.id) {
  await table.updateRecordAsync(recordId, {
    Status: "Running",
    "Job ID": payload.id,
  });
}

console.log(text);
