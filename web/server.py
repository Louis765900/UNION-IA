import json
import sys
import threading
from pathlib import Path
from flask import Flask, Response, request, jsonify

WEB_DIR = Path(__file__).parent
BASE_DIR = WEB_DIR.parent
sys.path.insert(0, str(BASE_DIR))

from cerveau.entraineur import Entraineur
from cerveau.cerveau import Cerveau
from cerveau.llm_cerveau import LLMCerveau

app = Flask(__name__)
_llm_lock = threading.Lock()
_init_done = threading.Event()

# ── Init en arrière-plan pour ne pas bloquer le démarrage ──────────────────────
_entraineur: Entraineur | None = None
_cerveau: Cerveau | None = None

def _initialiser():
    global _entraineur, _cerveau
    print("UNION IA — chargement du réseau neuronal...")
    _entraineur = Entraineur()
    _entraineur.entrainer(force=False)
    print("UNION IA — connexion au backend LLM...")
    _cerveau = Cerveau(_entraineur)
    backend = _cerveau.llm.stats().get("modele", "Réseau neuronal") if _cerveau.llm.actif else "Réseau neuronal"
    print(f"Backend : {backend}")
    _init_done.set()
    print("Prêt → http://127.0.0.1:5000")

threading.Thread(target=_initialiser, daemon=True).start()

# ── Helpers ────────────────────────────────────────────────────────────────────
def _serve(filename: str):
    path = WEB_DIR / filename
    return Response(path.read_text(encoding="utf-8"), mimetype="text/html")

def _attendre_init():
    """Attend que l'init soit terminée (max 60s)."""
    _init_done.wait(timeout=60)

# ── Routes ─────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return _serve("index.html")

@app.route("/settings")
def settings():
    return _serve("settings.html")

@app.route("/api/status")
def api_status():
    if not _init_done.is_set():
        return jsonify({
            "llm_actif": False,
            "modele": "Démarrage en cours…",
            "modele_id": None,
            "initialisation": True,
            "version": "2.1.0",
            "utilisateur": "Louis",
            "messages_session": 0,
            "total_messages": 0,
            "total_sessions": 0,
            "apprentissages": 0,
        })
    stats = _cerveau.llm.stats() if _cerveau.llm.actif else {}
    return jsonify({
        "llm_actif": _cerveau.llm.actif,
        "modele": stats.get("modele", "Réseau neuronal"),
        "modele_id": _cerveau.llm.modele_actif,
        "echanges_llm": stats.get("echanges", 0),
        "version": "2.1.0",
        "utilisateur": _cerveau.nom_utilisateur or "Louis",
        "messages_session": _cerveau.total_messages_session,
        "total_messages": _cerveau.memoire.get("total_messages", 0),
        "total_sessions": _cerveau.memoire.get("total_sessions", 0),
        "apprentissages": len(_cerveau.apprentissages),
        "initialisation": False,
    })

@app.route("/api/chat", methods=["POST"])
def api_chat():
    _attendre_init()
    data = request.get_json(force=True, silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "Message vide"}), 400

    texte_llm, fichiers = _cerveau.injecter_fichiers(message)

    def generate():
        if fichiers:
            yield f"data: {json.dumps({'phase': 'fichiers', 'content': fichiers})}\n\n"

        if _cerveau.llm.actif and _cerveau.besoin_llm(message):
            yield f"data: {json.dumps({'phase': 'source', 'content': _cerveau.llm.modele_actif or 'llm'})}\n\n"

            reponse_complete = ""
            llm_erreur = False
            with _llm_lock:
                for phase, contenu in _cerveau.llm.repondre_stream(
                    texte_llm, nom_utilisateur=_cerveau.nom_utilisateur
                ):
                    if phase == "erreur":
                        llm_erreur = True
                        # Désactive le backend défaillant pour cette session
                        _cerveau.llm._backend = None
                        _cerveau.llm.modele_actif = None
                        break
                    yield f"data: {json.dumps({'phase': phase, 'content': contenu})}\n\n"
                    if phase == "repondre":
                        reponse_complete += contenu
                    elif phase == "done":
                        break

            if llm_erreur:
                # Fallback réseau neuronal
                yield f"data: {json.dumps({'phase': 'source', 'content': 'ia'})}\n\n"
                reponse, _ = _cerveau.repondre(message)
                yield f"data: {json.dumps({'phase': 'repondre', 'content': reponse})}\n\n"
                yield f"data: {json.dumps({'phase': 'done', 'content': reponse})}\n\n"
            elif reponse_complete:
                _cerveau.enregistrer_echange_llm(message, reponse_complete)
        else:
            yield f"data: {json.dumps({'phase': 'source', 'content': 'ia'})}\n\n"
            reponse, _ = _cerveau.repondre(message)
            yield f"data: {json.dumps({'phase': 'repondre', 'content': reponse})}\n\n"
            yield f"data: {json.dumps({'phase': 'done', 'content': reponse})}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )

@app.route("/api/history")
def api_history_get():
    _attendre_init()
    return jsonify({"history": _cerveau.messages_session[-20:]})

@app.route("/api/history", methods=["DELETE"])
def api_history_delete():
    _attendre_init()
    _cerveau.messages_session.clear()
    _cerveau.total_messages_session = 0
    if _cerveau.llm.actif:
        _cerveau.llm.vider_historique()
    return jsonify({"success": True})

@app.route("/api/modeles")
def api_modeles():
    disponibles = LLMCerveau.modeles_disponibles()
    return jsonify({
        "disponibles": disponibles,
        "actif": _cerveau.llm.modele_actif if _init_done.is_set() else None,
    })

@app.route("/api/modele", methods=["POST"])
def api_changer_modele():
    _attendre_init()
    data = request.get_json(force=True, silent=True) or {}
    modele = (data.get("modele") or "").strip()
    if not modele:
        return jsonify({"error": "Paramètre modele manquant"}), 400
    with _llm_lock:
        ok, msg = _cerveau.charger_llm(modele)
    if ok:
        return jsonify({"success": True, "message": msg, "modele": _cerveau.llm.modele_actif})
    return jsonify({"success": False, "error": msg}), 400

if __name__ == "__main__":
    print("UNION IA — démarrage...")
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True, use_reloader=False)
