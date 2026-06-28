import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import { spawnCli } from './utils';

export class StatusBarManager implements vscode.Disposable {
  private item: vscode.StatusBarItem;
  private timer: ReturnType<typeof setInterval> | null = null;
  private _isBuilt = false;

  constructor(
    private readonly projectRoot: string | undefined,
    private readonly outputChannel: vscode.OutputChannel,
    context: vscode.ExtensionContext
  ) {
    this.item = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
    this.item.command = 'neuralmind.openGraph';
    this.item.tooltip = 'NeuralMind — click to open graph view';
    this.item.text = '$(loading~spin) NeuralMind';
    this.item.show();
    context.subscriptions.push(this.item);

    if (projectRoot) {
      this.refresh();
      this.timer = setInterval(() => this.refresh(), 60_000);
    }
  }

  get isBuilt(): boolean { return this._isBuilt; }

  async refresh(): Promise<void> {
    if (!this.projectRoot) {
      this.item.text = '$(circle-slash) NeuralMind';
      this.item.backgroundColor = new vscode.ThemeColor('statusBarItem.errorBackground');
      return;
    }
    const config = vscode.workspace.getConfiguration('neuralmind');
    const pythonPath = config.get<string>('pythonPath', 'python');

    const result = await spawnCli(
      ['-m', 'neuralmind.cli', 'stats', this.projectRoot, '--json'],
      pythonPath
    );

    let stats: { built?: boolean; total_nodes?: number; error?: string } = {};
    try { stats = JSON.parse(result.stdout); } catch { /* unparseable */ }

    if (!stats.built || stats.error) {
      this._isBuilt = false;
      this.item.text = '$(circle-slash) NeuralMind';
      this.item.backgroundColor = new vscode.ThemeColor('statusBarItem.errorBackground');
      return;
    }

    this._isBuilt = true;
    const nodeCount = formatK(stats.total_nodes ?? 0);
    const thresholdHours = config.get<number>('autoBuildThresholdHours', 24);
    const stale = checkStale(this.projectRoot, thresholdHours);

    if (stale) {
      this.item.text = `$(warning) NeuralMind · ${nodeCount} nodes`;
      this.item.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
    } else {
      this.item.text = `$(check) NeuralMind · ${nodeCount} nodes`;
      this.item.backgroundColor = undefined;
    }
  }

  dispose(): void {
    if (this.timer !== null) clearInterval(this.timer);
  }
}

function formatK(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n);
}

function checkStale(projectRoot: string, thresholdHours: number): boolean {
  const thresholdMs = thresholdHours * 3600 * 1000;
  for (const candidate of [
    path.join(projectRoot, '.neuralmind'),
    path.join(projectRoot, 'graphify-out', 'graph.json'),
  ]) {
    try {
      const stat = fs.statSync(candidate);
      return Date.now() - stat.mtimeMs > thresholdMs;
    } catch { /* try next */ }
  }
  return true;
}
