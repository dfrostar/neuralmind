import * as vscode from 'vscode';
import * as net from 'net';
import { spawn, ChildProcess } from 'child_process';

export class ServerManager implements vscode.Disposable {
  private proc: ChildProcess | null = null;
  private _port: number | null = null;
  private _ready = false;
  private _killTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(
    private readonly projectRoot: string | undefined,
    private readonly outputChannel: vscode.OutputChannel
  ) {}

  get port(): number | null { return this._port; }
  get isReady(): boolean { return this._ready; }

  async start(): Promise<void> {
    if (this.proc !== null) return; // already running — start() is idempotent
    if (!this.projectRoot) return;
    const config = vscode.workspace.getConfiguration('neuralmind');
    const pythonPath = config.get<string>('pythonPath', 'python');

    try {
      const port = await findFreePort();
      this._port = port;

      this.proc = spawn(
        pythonPath,
        ['-m', 'neuralmind.cli', 'serve', this.projectRoot,
         '--no-auth', '--port', String(port), '--no-browser'],
        {
          stdio: ['ignore', 'pipe', 'pipe'],
          env: { ...process.env, PYTHONUNBUFFERED: '1' },
        }
      );

      this.proc.stderr?.on('data', (chunk: Buffer) => {
        this.outputChannel.appendLine(`[serve] ${chunk.toString().trimEnd()}`);
      });

      this.proc.on('error', (err: NodeJS.ErrnoException) => {
        if (err.code === 'ENOENT') {
          vscode.window.showInformationMessage(
            'NeuralMind: CLI not found. Install with: pip install neuralmind'
          );
        }
        this._ready = false;
      });

      this.proc.on('exit', () => { this._ready = false; this.proc = null; this._port = null; });

      const healthy = await waitForHealthy(port);
      this._ready = healthy;

      if (!healthy) {
        vscode.window.showWarningMessage(
          'NeuralMind: Graph server did not start. Graph view unavailable; CLI commands still work.'
        );
      }
    } catch (err) {
      this.outputChannel.appendLine(`[serve] start error: ${err}`);
    }
  }

  dispose(): void {
    this._ready = false;
    if (this.proc) {
      this.proc.kill('SIGTERM');
      this._killTimer = setTimeout(() => {
        this.proc?.kill('SIGKILL');
      }, 2000);
    }
  }
}

function findFreePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.listen(0, '127.0.0.1', () => {
      const port = (srv.address() as net.AddressInfo).port;
      srv.close(() => resolve(port));
    });
    srv.on('error', reject);
  });
}

async function waitForHealthy(port: number, timeoutMs = 10_000): Promise<boolean> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/healthz`);
      if (res.ok) return true;
    } catch { /* server not up yet */ }
    await new Promise(r => setTimeout(r, 500));
  }
  return false;
}
