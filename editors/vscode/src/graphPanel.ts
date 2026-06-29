import * as vscode from 'vscode';
import { ServerManager } from './serverManager';

export class GraphPanel {
  static currentPanel: GraphPanel | undefined;

  private constructor(private readonly panel: vscode.WebviewPanel) {
    this.panel.onDidDispose(() => {
      GraphPanel.currentPanel = undefined;
    });
  }

  static createOrShow(extensionUri: vscode.Uri, serverManager: ServerManager): void {
    const column = vscode.ViewColumn.Two;

    if (GraphPanel.currentPanel) {
      GraphPanel.currentPanel.panel.reveal(column);
      return;
    }

    const panel = vscode.window.createWebviewPanel(
      'neuralmind.graph',
      'NeuralMind Graph',
      column,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
      }
    );

    panel.webview.html = GraphPanel.buildHtml(serverManager);
    GraphPanel.currentPanel = new GraphPanel(panel);
  }

  private static buildHtml(serverManager: ServerManager): string {
    if (serverManager.isReady && serverManager.port !== null) {
      const port = serverManager.port;
      return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta http-equiv="Content-Security-Policy"
        content="default-src 'none'; frame-src http://127.0.0.1:${port};">
  <style>
    html, body, iframe {
      margin: 0; padding: 0; width: 100%; height: 100vh; border: none; display: block;
    }
  </style>
</head>
<body>
  <iframe src="http://127.0.0.1:${port}/" allow="scripts"></iframe>
</body>
</html>`;
    }

    return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline';">
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; padding: 2rem;
           color: #ccc; background: #1e1e1e; }
    code, pre { background: #2d2d2d; padding: 2px 8px; border-radius: 4px; font-size: 0.9em; }
    pre { padding: 1rem; display: block; margin: 0.5rem 0; }
    h2 { color: #e2e2e2; }
    p { line-height: 1.6; }
  </style>
</head>
<body>
  <h2>NeuralMind Graph View</h2>
  <p>The NeuralMind graph server is not running.</p>
  <p>Make sure NeuralMind is installed and your index is built:</p>
  <pre><code>pip install neuralmind
neuralmind build .</code></pre>
  <p>Then use <strong>NeuralMind: Open Graph View</strong> again to retry.</p>
</body>
</html>`;
  }
}
