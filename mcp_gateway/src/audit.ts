import { appendFileSync, existsSync, mkdirSync, renameSync, statSync, unlinkSync } from "fs";
import { dirname } from "path";
import { homedir } from "os";

export interface AuditEntry {
  action: string;
  client_id: string;
  reason: string;
  fields: Record<string, string>;
  timestamp?: number;
}

const AUDIT_PATH = process.env.AUDIT_LOG ?? `${homedir()}/.agent-sandbox/audit.jsonl`;
const MAX_SIZE = parseInt(process.env.AUDIT_MAX_SIZE ?? String(10 * 1024 * 1024));

export function log(entry: AuditEntry): void {
  try {
    const dir = dirname(AUDIT_PATH);
    if (!existsSync(dir)) mkdirSync(dir, { recursive: true });

    rotateIfNeeded();

    const record = { ...entry, timestamp: entry.timestamp ?? Date.now() / 1000 };
    appendFileSync(AUDIT_PATH, JSON.stringify(record) + "\n");
  } catch (e) {
    console.error(`Audit write failed: ${e}`);
  }
}

function rotateIfNeeded(): void {
  if (!existsSync(AUDIT_PATH)) return;
  const size = statSync(AUDIT_PATH).size;
  if (size < MAX_SIZE) return;

  const rotated = AUDIT_PATH + ".1";
  if (existsSync(rotated)) unlinkSync(rotated);
  renameSync(AUDIT_PATH, rotated);
}
