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

# ── Init ───────────────────────────────────────────────────────────────────────
print("UNION IA — initialisation...")
_entraineur = Entraineur()
_entraineur.entrainer(force=False)
_cerveau = Cerveau(_entraineur)

_llm_ok = _cerveau.llm.actif
_nom_modele = _cerveau.llm.stats().get("modele", "Réseau neuronal") if _llm_ok else "Réseau neuronal"

print(f"Backend : {_nom_modele}")
print("Prêt → http://127.0.0.1:5000")

# ── Helpers ────────────────────────────────────────────────────────────────────
def _serve(filename: str):
    path = WEB_DIR / filename
    return Response(path.read_text(encoding="utf-8"), mimetype="text/html")

# ── Routes ─────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return _serve("index.html")

@app.route("/settings")
def settings():
    return _serve("settings.html")

@app.route("/api/status")
def api_status():
    stats = _cerveau.llm.stats() if _cerveau.llm.actif else {}
    return jsonify({
        "llm_actif": _cerveau.llm.actif,
        "modele": stats.get("modele", "Réseau neuronal"),
        "modele_id": _cerveau.llm.modele_actif,
        "echanges_llm": stats.get("echanges", 0),
        "gpu": "GTX 1650 · Vulkan",
        "gpu_couches": stats.get("gpu_couches", 0),
        "version": "1.0.0",
        "utilisateur": _cerveau.nom_utilisateur or "Louis",
        "messages_session": _cerveau.total_messages_session,
        "total_messages": _cerveau.memoire.get("total_messages", 0),
        "total_sessions": _cerveau.memoire.get("total_sessions", 0),
        "apprentissages": len(_cerveau.apprentissages),
    })

@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json(force=True, silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "Message vide"}), 400

    texte_llm, fichiers = _cerveau.injecter_fichiers(message)

    def generate():
        if fichiers:
            yield f"data: {json.dumps({'phase': 'fichiers', 'content': fichiers})}\n\n"

        if _cerveau.llm.actif and _cerveau.besoin_llm(message):
            source = "llm" if _cerveau.llm.modele_actif == "deepseek" else "kimi"
            yield f"data: {json.dumps({'phase': 'source', 'content': source})}\n\n"

            reponse_complete = ""
            with _llm_lock:
                for phase, contenu in _cerveau.llm.repondre_stream(
                    texte_llm, nom_utilisateur=_cerveau.nom_utilisateur
                ):
                    yield f"data: {json.dumps({'phase': phase, 'content': contenu})}\n\n"
                    if phase == "repondre":
                        reponse_complete += contenu
                    elif phase in ("done", "erreur"):
                        break

            if reponse_complete:
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
    return jsonify({"history": _cerveau.messages_session[-20:]})

@app.route("/api/history", methods=["DELETE"])
def api_history_delete():
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
        "actif": _cerveau.llm.modele_actif,
    })

@app.route("/api/modele", methods=["POST"])
def api_changer_modele():
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
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True, use_reloader=False)
