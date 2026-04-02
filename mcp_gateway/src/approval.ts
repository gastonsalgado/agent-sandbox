import * as readline from "readline";

interface Grant {
  pattern: string;
  expires: number;
}

class ApprovalService {
  private grants: Grant[] = [];
  private pendingPromise: Promise<string> | null = null;

  async requestApproval(label: string, detail: string): Promise<boolean> {
    if (this.checkGrant(label)) return true;

    const separator = "=".repeat(60);
    process.stderr.write(`\n${separator}\n`);
    process.stderr.write(`  APPROVAL REQUIRED: ${label}\n`);
    process.stderr.write(`  Detail: ${detail}\n`);
    process.stderr.write(`${separator}\n`);
    process.stderr.write("  [y] Approve  [g] Approve + grant 5min  [n] Deny\n");
    process.stderr.write("  > ");

    const response = await this.readLine();

    if (response === "g") {
      this.createGrant(label, 300);
      process.stderr.write(`  Granted for 5 minutes\n`);
      return true;
    }

    const approved = response === "y";
    process.stderr.write(approved ? `  Approved\n` : `  Denied\n`);
    return approved;
  }

  createGrant(pattern: string, ttl: number = 300): void {
    this.grants.push({ pattern, expires: Date.now() + ttl * 1000 });
  }

  private checkGrant(label: string): boolean {
    const now = Date.now();
    this.grants = this.grants.filter((g) => g.expires > now);
    return this.grants.some((g) => label.includes(g.pattern));
  }

  private readLine(): Promise<string> {
    return new Promise((resolve) => {
      const onData = (data: Buffer) => {
        process.stdin.removeListener("data", onData);
        resolve(data.toString().trim().toLowerCase());
      };

      // Ensure stdin is in flowing mode
      if (process.stdin.isPaused()) {
        process.stdin.resume();
      }
      process.stdin.once("data", onData);
    });
  }
}

export const approvalService = new ApprovalService();
