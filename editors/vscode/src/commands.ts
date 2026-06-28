import * as vscode from 'vscode';
import * as path from 'path';
import { spawnCli } from './utils';
import { StatusBarManager } from './statusBar';
import { GraphPanel } from './graphPanel';
import { ServerManager } from './serverManager';

export function registerCommands(
  context: vscode.ExtensionContext,
  projectRoot: string | undefined,
  outputChannel: vscode.OutputChannel,
  serverManager: ServerManager,
  statusBar: StatusBarManager
): void {
  const getPython = () =>
    vscode.workspace.getConfiguration('neuralmind').get<string>('pythonPath', 'python');

  const requireProject = (): string | undefined => {
    if (!projectRoot) {
      vscode.window.showWarningMessage('NeuralMind: No workspace folder open.');
    }
    return projectRoot;
  };

  context.subscriptions.push(

    vscode.commands.registerCommand('neuralmind.query', async () => {
      const root = requireProject();
      if (!root) return;
      const question = await vscode.window.showInputBox({
        prompt: 'NeuralMind: Enter your question about the codebase',
        placeHolder: 'e.g. How does authentication work?',
      });
      if (!question) return;
      outputChannel.show(true);
      outputChannel.appendLine(`\n[NeuralMind Query] ${question}`);
      const result = await spawnCli(
        ['-m', 'neuralmind.cli', 'query', root, question, '--json'],
        getPython()
      );
      if (result.exitCode !== 0) {
        outputChannel.appendLine(`Error: ${result.stderr}`);
        return;
      }
      try {
        const parsed = JSON.parse(result.stdout);
        outputChannel.appendLine(parsed.context ?? result.stdout);
        outputChannel.appendLine(
          `\n[${parsed.tokens ?? '?'} tokens · ${parsed.reduction_ratio ?? '?'}× reduction]`
        );
      } catch {
        outputChannel.appendLine(result.stdout);
      }
    }),

    vscode.commands.registerCommand('neuralmind.wakeup', async () => {
      const root = requireProject();
      if (!root) return;
      outputChannel.show(true);
      outputChannel.appendLine('\n[NeuralMind Wakeup]');
      const result = await spawnCli(
        ['-m', 'neuralmind.cli', 'wakeup', root, '--json'],
        getPython()
      );
      if (result.exitCode !== 0) {
        outputChannel.appendLine(`Error: ${result.stderr}`);
        return;
      }
      try {
        const parsed = JSON.parse(result.stdout);
        outputChannel.appendLine(parsed.context ?? result.stdout);
      } catch {
        outputChannel.appendLine(result.stdout);
      }
    }),

    vscode.commands.registerCommand('neuralmind.skeleton', async () => {
      const root = requireProject();
      if (!root) return;
      const filePath = vscode.window.activeTextEditor?.document.uri.fsPath;
      if (!filePath) {
        vscode.window.showWarningMessage('NeuralMind: No active file.');
        return;
      }
      outputChannel.show(true);
      outputChannel.appendLine(`\n[NeuralMind Skeleton] ${path.basename(filePath)}`);
      // arg order: skeleton <file_path> --project-path <project_root> (verified from cli.py:1788)
      const result = await spawnCli(
        ['-m', 'neuralmind.cli', 'skeleton', filePath, '--project-path', root, '--json'],
        getPython()
      );
      if (result.exitCode !== 0) {
        outputChannel.appendLine(`Error: ${result.stderr}`);
        return;
      }
      try {
        const parsed = JSON.parse(result.stdout);
        outputChannel.appendLine(parsed.skeleton ?? result.stdout);
      } catch {
        outputChannel.appendLine(result.stdout);
      }
    }),

    vscode.commands.registerCommand('neuralmind.build', async () => {
      const root = requireProject();
      if (!root) return;
      await vscode.window.withProgress(
        {
          location: vscode.ProgressLocation.Notification,
          title: 'NeuralMind: Building index...',
          cancellable: false,
        },
        async () => {
          const result = await spawnCli(
            ['-m', 'neuralmind.cli', 'build', root],
            getPython()
          );
          if (result.exitCode === 0) {
            vscode.window.showInformationMessage('NeuralMind: Build complete.');
          } else {
            outputChannel.show(true);
            outputChannel.appendLine(`[NeuralMind Build]\n${result.stderr || result.stdout}`);
            vscode.window.showErrorMessage('NeuralMind: Build failed — see Output panel.');
          }
          await statusBar.refresh();
        }
      );
    }),

    vscode.commands.registerCommand('neuralmind.probe', async () => {
      const root = requireProject();
      if (!root) return;
      outputChannel.show(true);
      outputChannel.appendLine('\n[NeuralMind Probe]');
      const result = await spawnCli(
        ['-m', 'neuralmind.cli', 'probe', root, '--json'],
        getPython()
      );
      if (result.exitCode !== 0) {
        outputChannel.appendLine(`Error: ${result.stderr}`);
        return;
      }
      try {
        const parsed = JSON.parse(result.stdout);
        outputChannel.appendLine([
          `answerability : ${((parsed.answerability_pct ?? 0) as number).toFixed(1)}%`,
          `MRR           : ${((parsed.mrr ?? 0) as number).toFixed(3)}`,
          `recall@1/3/5  : ${parsed['recall@1'] ?? '?'} / ${parsed['recall@3'] ?? '?'} / ${parsed['recall@5'] ?? '?'}`,
          `blind spots   : ${(parsed.blind_spots as unknown[])?.length ?? 0}`,
        ].join('\n'));
      } catch {
        outputChannel.appendLine(result.stdout);
      }
    }),

    vscode.commands.registerCommand('neuralmind.openGraph', () => {
      GraphPanel.createOrShow(context.extensionUri, serverManager);
    }),

    vscode.commands.registerCommand('neuralmind.setupCline', async () => {
      const root = requireProject();
      if (!root) return;
      const result = await spawnCli(
        ['-m', 'neuralmind.cli', 'install-mcp', root, '--client', 'cline'],
        getPython()
      );
      if (result.exitCode === 0) {
        vscode.window.showInformationMessage(
          'NeuralMind MCP registered with Cline. Restart Cline to activate.'
        );
      } else {
        vscode.window.showErrorMessage(`NeuralMind: Setup failed — ${result.stderr}`);
      }
    }),

    vscode.commands.registerCommand('neuralmind.setupVscode', async () => {
      const root = requireProject();
      if (!root) return;
      const result = await spawnCli(
        ['-m', 'neuralmind.cli', 'install-mcp', root, '--client', 'vscode'],
        getPython()
      );
      if (result.exitCode === 0) {
        vscode.window.showInformationMessage(
          'NeuralMind MCP registered with VS Code (requires VS Code 1.99+ with MCP support). Reload window to activate.'
        );
      } else {
        vscode.window.showErrorMessage(`NeuralMind: Setup failed — ${result.stderr}`);
      }
    })

  );
}
