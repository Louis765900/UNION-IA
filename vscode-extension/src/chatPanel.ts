import * as vscode from 'vscode';

export class ChatPanel {
  static instance: ChatPanel | undefined;
  private static readonly viewType = 'unionia.chat';

  private readonly _panel: vscode.WebviewPanel;
  private readonly _extensionUri: vscode.Uri;
  private _disposables: vscode.Disposable[] = [];

  static createOrShow(extensionUri: vscode.Uri) {
    const column = vscode.window.activeTextEditor
      ? vscode.ViewColumn.Beside
      : vscode.ViewColumn.One;

    if (ChatPanel.instance) {
      ChatPanel.instance._panel.reveal(column);
      return;
    }

    const panel = vscode.window.createWebviewPanel(
      ChatPanel.viewType,
      'UNION IA',
      column,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
        localResourceRoots: [vscode.Uri.joinPath(extensionUri, 'media')],
      }
    );

    ChatPanel.instance = new ChatPanel(panel, extensionUri);
  }

  private constructor(panel: vscode.WebviewPanel, extensionUri: vscode.Uri) {
    this._panel = panel;
    this._extensionUri = extensionUri;
    this._update();

    this._panel.onDidDispose(() => this.dispose(), null, this._disposables);

    this._panel.webview.onDidReceiveMessage(
      message => {
        if (message.type === 'ready') {
          // Panel prêt
        }
      },
      null,
      this._disposables
    );
  }

  sendMessage(texte: string) {
    this._panel.webview.postMessage({ type: 'sendMessage', text: texte });
    this._panel.reveal();
  }

  private _update() {
    const cfg = vscode.workspace.getConfiguration('unionia');
    const serverUrl = cfg.get<string>('serverUrl') || 'http://127.0.0.1:5000';
    const token = cfg.get<string>('token') || '';

    this._panel.webview.html = this._getHtml(serverUrl, token);
  }

  private _getHtml(serverUrl: string, token: string): string {
    return `<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; connect-src ${serverUrl}; style-src 'unsafe-inline'; img-src data:;">
  <title>UNION IA</title>
  <style>
    :root { --bg:#0f0f0f; --surface:#1a1a1a; --border:#2a2a2a; --text:#e8e8e8;
            --muted:#888; --accent:#7c6ff7; --user-bg:#7c6ff7; --ia-bg:#1e1e1e; }
    * { box-sizing:border-box; margin:0; padding:0; }
    body { font-family:system-ui,sans-serif; background:var(--bg); color:var(--text);
           display:flex; flex-direction:column; height:100vh; font-size:13px; }
    #chat { flex:1; overflow-y:auto; padding:1rem; display:flex; flex-direction:column; gap:.6rem; }
    .msg { max-width:88%; padding:.6rem .9rem; border-radius:10px; line-height:1.5; white-space:pre-wrap; word-break:break-word; }
    .msg-user { background:var(--user-bg); color:#fff; align-self:flex-end; }
    .msg-ia { background:var(--ia-bg); border:1px solid var(--border); align-self:flex-start; }
    #input-zone { display:flex; gap:.5rem; padding:.7rem; border-top:1px solid var(--border);
                  background:var(--surface); }
    #input { flex:1; background:var(--bg); border:1px solid var(--border); border-radius:8px;
             color:var(--text); padding:.5rem .8rem; font-size:13px; resize:none; font-family:inherit; }
    #input:focus { outline:none; border-color:var(--accent); }
    #send { background:var(--accent); color:#fff; border:none; border-radius:8px;
            padding:.5rem .9rem; cursor:pointer; font-size:13px; }
    #send:hover { opacity:.9; }
    .typing { color:var(--muted); font-style:italic; font-size:.85rem; padding:.3rem 0; }
    .status-bar { padding:.3rem .7rem; background:var(--surface); border-bottom:1px solid var(--border);
                  font-size:.78rem; color:var(--muted); display:flex; align-items:center; gap:.5rem; }
    .dot { width:6px; height:6px; border-radius:50%; background:var(--muted); }
    .dot.ok { background:#4c9; }
    pre { background:#111; border:1px solid var(--border); border-radius:6px; padding:.6rem;
          overflow-x:auto; font-size:.82rem; white-space:pre-wrap; }
    code { font-family:'Consolas','Courier New',monospace; }
  </style>
</head>
<body>
  <div class="status-bar">
    <div class="dot" id="dot"></div>
    <span id="status">Connexion à UNION IA…</span>
  </div>
  <div id="chat">
    <div class="msg msg-ia">Bonjour ! Je suis UNION IA, ton assistant IA. Pose-moi une question ou sélectionne du code dans l'éditeur.</div>
  </div>
  <div id="input-zone">
    <textarea id="input" placeholder="Pose une question…" rows="2"></textarea>
    <button id="send" onclick="envoyer()">Envoyer</button>
  </div>

<script>
const SERVER = ${JSON.stringify(serverUrl)};
const TOKEN = ${JSON.stringify(token)};

let convId = null;
let enCours = false;

async function verifierStatut() {
  try {
    const r = await fetch(SERVER + '/api/status');
    const d = await r.json();
    document.getElementById('dot').className = 'dot ok';
    document.getElementById('status').textContent = d.modele + ' — ' + (d.mode_label || 'UNION IA 2.1');
  } catch(e) {
    document.getElementById('status').textContent = 'Serveur inaccessible (' + SERVER + ')';
  }
}

function ajouterMsg(role, texte) {
  const chat = document.getElementById('chat');
  const div = document.createElement('div');
  div.className = 'msg msg-' + role;
  div.textContent = texte;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
  return div;
}

async function envoyer() {
  if (enCours) return;
  const inp = document.getElementById('input');
  const texte = inp.value.trim();
  if (!texte) return;
  inp.value = '';
  ajouterMsg('user', texte);

  const typingEl = document.createElement('div');
  typingEl.className = 'typing';
  typingEl.textContent = 'UNION IA réfléchit…';
  document.getElementById('chat').appendChild(typingEl);

  enCours = true;
  let iaDiv = null;
  let reponse = '';

  try {
    const headers = {'Content-Type':'application/json'};
    if (TOKEN) headers['Authorization'] = 'Bearer ' + TOKEN;
    const r = await fetch(SERVER + '/api/chat', {
      method: 'POST',
      headers,
      body: JSON.stringify({message: texte, conversation_id: convId}),
      credentials: 'include',
    });

    const reader = r.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';

    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      buf += decoder.decode(value, {stream: true});
      const lines = buf.split('\\n');
      buf = lines.pop();
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        try {
          const evt = JSON.parse(line.slice(6));
          if (evt.phase === 'conversation') { convId = evt.content; }
          else if (evt.phase === 'repondre') {
            typingEl.remove();
            if (!iaDiv) iaDiv = ajouterMsg('ia', '');
            reponse += evt.content;
            iaDiv.textContent = reponse;
            document.getElementById('chat').scrollTop = document.getElementById('chat').scrollHeight;
          }
        } catch(e) {}
      }
    }
  } catch(e) {
    typingEl.remove();
    ajouterMsg('ia', 'Erreur : impossible de joindre le serveur UNION IA sur ' + SERVER);
  }
  enCours = false;
}

document.getElementById('input').addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); envoyer(); }
});

// Écoute les messages de l'extension (code sélectionné → auto-envoi)
window.addEventListener('message', evt => {
  const msg = evt.data;
  if (msg.type === 'sendMessage') {
    document.getElementById('input').value = msg.text;
    envoyer();
  }
});

verifierStatut();
</script>
</body>
</html>`;
  }

  dispose() {
    ChatPanel.instance = undefined;
    this._panel.dispose();
    while (this._disposables.length) {
      const d = this._disposables.pop();
      if (d) d.dispose();
    }
  }
}
