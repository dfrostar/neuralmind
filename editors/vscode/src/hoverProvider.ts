import * as vscode from 'vscode';
import * as path from 'path';
import { spawnCli } from './utils';
import { StatusBarManager } from './statusBar';

interface CacheEntry {
  skeleton: string;
  expiry: number;
}

export class NeuralMindHoverProvider implements vscode.HoverProvider {
  private readonly cache = new Map<string, CacheEntry>();
  private readonly cacheTtlMs = 60_000;
  private readonly cacheMax = 50;

  constructor(
    private readonly projectRoot: string,
    private readonly pythonPath: string,
    private readonly outputChannel: vscode.OutputChannel,
    private readonly statusBar: StatusBarManager
  ) {}

  async provideHover(
    document: vscode.TextDocument,
    _position: vscode.Position,
  ): Promise<vscode.Hover | undefined> {
    if (!this.statusBar.isBuilt) return undefined;

    const filePath = document.uri.fsPath;
    const now = Date.now();

    const cached = this.cache.get(filePath);
    if (cached && cached.expiry > now) {
      return buildHover(cached.skeleton, filePath);
    }

    const result = await spawnCli(
      ['-m', 'neuralmind.cli', 'skeleton', filePath, '--project-path', this.projectRoot, '--json'],
      this.pythonPath
    );
    if (result.exitCode !== 0) return undefined;

    let skeleton: string | undefined;
    try {
      const parsed = JSON.parse(result.stdout) as { skeleton?: string };
      skeleton = parsed.skeleton;
    } catch {
      return undefined;
    }
    if (!skeleton) return undefined;

    if (this.cache.size >= this.cacheMax) {
      const oldest = this.cache.keys().next().value;
      if (oldest !== undefined) this.cache.delete(oldest);
    }
    this.cache.set(filePath, { skeleton, expiry: now + this.cacheTtlMs });

    return buildHover(skeleton, filePath);
  }
}

function buildHover(skeleton: string, filePath: string): vscode.Hover {
  const md = new vscode.MarkdownString(
    `**NeuralMind** — \`${path.basename(filePath)}\`\n\n\`\`\`\n${skeleton}\n\`\`\``
  );
  md.isTrusted = false;
  return new vscode.Hover(md);
}
