import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import { ServerManager } from './serverManager';
import { StatusBarManager } from './statusBar';
import { registerCommands } from './commands';
import { NeuralMindHoverProvider } from './hoverProvider';

export function activate(context: vscode.ExtensionContext): void {
  const projectRoot = getProjectRoot();
  const outputChannel = vscode.window.createOutputChannel('NeuralMind');
  context.subscriptions.push(outputChannel);

  const serverManager = new ServerManager(projectRoot, outputChannel);
  context.subscriptions.push(serverManager);

  const statusBar = new StatusBarManager(projectRoot, outputChannel, context);

  if (projectRoot) {
    serverManager.start();
    checkStaleness(projectRoot);
  }

  registerCommands(context, projectRoot, outputChannel, serverManager, statusBar);

  const config = vscode.workspace.getConfiguration('neuralmind');
  if (config.get<boolean>('enableHover') && projectRoot) {
    const pythonPath = config.get<string>('pythonPath', 'python');
    context.subscriptions.push(
      vscode.languages.registerHoverProvider(
        ['python', 'typescript', 'javascript', 'go', 'rust', 'java', 'c', 'cpp'],
        new NeuralMindHoverProvider(projectRoot, pythonPath, outputChannel, statusBar)
      )
    );
  }
}

export function deactivate(): void {
  // ServerManager and StatusBarManager cleanup runs via context.subscriptions
}

function getProjectRoot(): string | undefined {
  return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
}

function checkStaleness(projectRoot: string): void {
  const config = vscode.workspace.getConfiguration('neuralmind');
  const thresholdHours = config.get<number>('autoBuildThresholdHours', 24);
  const thresholdMs = thresholdHours * 3600 * 1000;

  let isStale = true;
  try {
    const stat = fs.statSync(path.join(projectRoot, 'graphify-out', 'graph.json'));
    isStale = Date.now() - stat.mtimeMs > thresholdMs;
  } catch { /* no index file → stale */ }

  if (isStale) {
    vscode.window.showInformationMessage(
      'NeuralMind: Index is stale or not built. Build now?',
      'Build'
    ).then(choice => {
      if (choice === 'Build') {
        vscode.commands.executeCommand('neuralmind.build');
      }
    });
  }
}
