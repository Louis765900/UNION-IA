import * as vscode from 'vscode';
import { ChatPanel } from './chatPanel';

export function activate(context: vscode.ExtensionContext) {
  console.log('UNION IA activé');

  // Ouvrir le panel de chat
  context.subscriptions.push(
    vscode.commands.registerCommand('unionia.openChat', () => {
      ChatPanel.createOrShow(context.extensionUri);
    })
  );

  // Expliquer le code sélectionné
  context.subscriptions.push(
    vscode.commands.registerCommand('unionia.explainCode', () => {
      const code = getSelection();
      if (!code) return;
      const lang = getLanguage();
      const prompt = `Explique ce code ${lang} en français, de manière claire et concise :\n\`\`\`${lang}\n${code}\n\`\`\``;
      ChatPanel.createOrShow(context.extensionUri);
      ChatPanel.instance?.sendMessage(prompt);
    })
  );

  // Revoir le code sélectionné
  context.subscriptions.push(
    vscode.commands.registerCommand('unionia.reviewCode', () => {
      const code = getSelection();
      if (!code) return;
      const lang = getLanguage();
      const prompt = `Fais une revue de code de ce snippet ${lang}. Identifie les bugs potentiels, les problèmes de lisibilité et les améliorations possibles :\n\`\`\`${lang}\n${code}\n\`\`\``;
      ChatPanel.createOrShow(context.extensionUri);
      ChatPanel.instance?.sendMessage(prompt);
    })
  );

  // Générer la documentation
  context.subscriptions.push(
    vscode.commands.registerCommand('unionia.generateDoc', () => {
      const code = getSelection();
      if (!code) return;
      const lang = getLanguage();
      const prompt = `Génère la documentation (commentaires / docstring) pour ce code ${lang} :\n\`\`\`${lang}\n${code}\n\`\`\``;
      ChatPanel.createOrShow(context.extensionUri);
      ChatPanel.instance?.sendMessage(prompt);
    })
  );

  // Poser une question rapide
  context.subscriptions.push(
    vscode.commands.registerCommand('unionia.askQuestion', async () => {
      const question = await vscode.window.showInputBox({
        prompt: 'Question pour UNION IA',
        placeHolder: 'Comment faire une liste Python ?',
      });
      if (!question) return;
      ChatPanel.createOrShow(context.extensionUri);
      ChatPanel.instance?.sendMessage(question);
    })
  );

  // Vue dans la barre latérale
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider('unionia.chatView', {
      resolveWebviewView(webviewView) {
        webviewView.webview.options = { enableScripts: true };
        webviewView.webview.html = getSidebarHtml(getConfig().serverUrl);
      },
    })
  );
}

export function deactivate() {}

// ── Helpers ──────────────────────────────────────────────────────────────────

function getSelection(): string {
  const editor = vscode.window.activeTextEditor;
  if (!editor) return '';
  const sel = editor.selection;
  if (sel.isEmpty) {
    vscode.window.showWarningMessage('UNION IA : Sélectionne du texte d\'abord.');
    return '';
  }
  return editor.document.getText(sel);
}

function getLanguage(): string {
  return vscode.window.activeTextEditor?.document.languageId || 'code';
}

function getConfig() {
  const cfg = vscode.workspace.getConfiguration('unionia');
  return {
    serverUrl: cfg.get<string>('serverUrl') || 'http://127.0.0.1:5000',
    token: cfg.get<string>('token') || '',
    mode: cfg.get<string>('mode') || '2.1',
  };
}

function getSidebarHtml(serverUrl: string): string {
  return `<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
  <style>body{margin:0;padding:0;background:transparent}iframe{width:100%;height:100vh;border:none}</style>
  </head><body><iframe src="${serverUrl}?embed=1" sandbox="allow-scripts allow-forms allow-same-origin"></iframe></body></html>`;
}
