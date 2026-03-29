import * as readline from "readline";

interface Grant {
  pattern: string;
  expires: number;
}

class ApprovalService {
  private grants: Grant[] = [];

  async requestApproval(label: string, detail: string): Promise<boolean> {
    if (this.checkGrant(label)) return true;

    const separator = "=".repeat(60);
    process.stderr.write(`\n${separator}\n`);
    process.stderr.write(`  APPROVAL REQUIRED: ${label}\n`);
    process.stderr.write(`  Detail: ${detail}\n`);
    process.stderr.write(`${separator}\n`);
    process.stderr.write("  [y] Approve  [g] Approve + grant 5min  [n] Deny\n");

    const response = await this.prompt("  > ");

    if (response === "g") {
      this.createGrant(label, 300);
      return true;
    }

    return response === "y";
  }

  createGrant(pattern: string, ttl: number = 300): void {
    this.grants.push({ pattern, expires: Date.now() + ttl * 1000 });
  }

  private checkGrant(label: string): boolean {
    const now = Date.now();
    this.grants = this.grants.filter((g) => g.expires > now);
    return this.grants.some((g) => label.includes(g.pattern));
  }

  private prompt(query: string): Promise<string> {
    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stderr,
    });
    return new Promise((resolve) => {
      rl.question(query, (answer) => {
        rl.close();
        resolve(answer.trim().toLowerCase());
      });
    });
  }
}

export const approvalService = new ApprovalService();
