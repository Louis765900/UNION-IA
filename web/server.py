"""
Serveur web de UNION IA (Flask).

Expose l'interface de chat et une API REST/SSE complète :
  - conversations persistantes (créer, lister, charger, supprimer, rechercher)
  - mémoire active (voir, modifier, oublier)
  - gamme de modes (2.1 / Flash / Flashlight) et choix du moteur

L'initialisation (réseau neuronal + moteur LLM) se fait en arrière-plan pour
un démarrage instantané.
"""

import json
import sys
import threading
import tempfile
import os
from pathlib import Path
from functools import wraps

from flask import Flask, Response, request, jsonify, send_from_directory

WEB_DIR = Path(__file__).parent
BASE_DIR = WEB_DIR.parent
sys.path.insert(0, str(BASE_DIR))

from cerveau.entraineur import Entraineur
from cerveau.cerveau import Cerveau
from cerveau.llm_cerveau import LLMCerveau, MODES
from cerveau.auth import Auth

app = Flask(__name__)
_llm_lock = threading.Lock()
_init_done = threading.Event()
_auth = Auth()

# CORS pour l'app mobile et l'extension VS Code
_CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")

@app.after_request
def add_cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = _CORS_ORIGINS
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
    resp.headers["Access-Control-Allow-Credentials"] = "true"
    return resp

@app.route("/", defaults={"path": ""}, methods=["OPTIONS"])
@app.route("/<path:path>", methods=["OPTIONS"])
def options_handler(path=""):
    return jsonify({}), 200

_cerveau: Cerveau | None = None
# Conversation active côté serveur (l'historique LLM lui est lié)
_conv_active: int | None = None


def _initialiser():
    global _cerveau
    print("UNION IA — chargement du réseau neuronal...")
    entraineur = Entraineur()
    entraineur.entrainer(force=False)
    print("UNION IA — connexion au moteur LLM...")
    _cerveau = Cerveau(entraineur)
    backend = _cerveau.llm.stats().get("modele", "Réseau neuronal") if _cerveau.llm.actif else "Réseau neuronal"
    print(f"Moteur : {backend}")
    _init_done.set()
    print("Prêt → http://127.0.0.1:5000")


threading.Thread(target=_initialiser, daemon=True).start()


# ── Auth helpers ───────────────────────────────────────────────────────────────

def _token_request() -> str | None:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return request.cookies.get("union_token")


def _utilisateur_courant() -> dict | None:
    return _auth.valider_token(_token_request())


def auth_requis(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        u = _utilisateur_courant()
        if not u:
            return jsonify({"error": "Non authentifié"}), 401
        return fn(*args, **kwargs)
    return wrapper


def admin_requis(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        u = _utilisateur_courant()
        if not u:
            return jsonify({"error": "Non authentifié"}), 401
        if u.get("role") != "admin":
            return jsonify({"error": "Accès refusé"}), 403
        return fn(*args, **kwargs)
    return wrapper


# ── Helpers ────────────────────────────────────────────────────────────────────

def _serve(filename: str):
    path = WEB_DIR / filename
    return Response(path.read_text(encoding="utf-8"), mimetype="text/html")


def _attendre_init():
    _init_done.wait(timeout=60)


def _charger_conversation(conv_id: int):
    """Bascule la conversation active et recharge l'historique LLM associé."""
    global _conv_active
    _conv_active = conv_id
    messages = _cerveau.stockage.lister_messages(conv_id)
    hist = []
    user_courant = None
    for m in messages:
        if m["role"] == "user":
            user_courant = m["contenu"]
        elif m["role"] == "assistant" and user_courant is not None:
            hist.append({"user": user_courant, "assistant": m["contenu"]})
            user_courant = None
    _cerveau.llm.charger_historique(hist)


def _titre_depuis(message: str) -> str:
    t = message.strip().replace("\n", " ")
    return (t[:55] + "…") if len(t) > 55 else t or "Nouvelle conversation"


# ── Pages ──────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return _serve("index.html")


@app.route("/settings")
def settings():
    return _serve("settings.html")


# ── Statut ─────────────────────────────────────────────────────────────────────

@app.route("/api/status")
def api_status():
    if not _init_done.is_set():
        return jsonify({
            "initialisation": True,
            "llm_actif": False,
            "modele": "Démarrage…",
            "modele_id": None,
            "mode": "2.1",
            "version": "2.1.0",
            "utilisateur": "Louis",
        })
    stats = _cerveau.llm.stats() if _cerveau.llm.actif else {}
    return jsonify({
        "initialisation": False,
        "llm_actif": _cerveau.llm.actif,
        "modele": stats.get("modele", "Réseau neuronal"),
        "modele_id": _cerveau.llm.moteur_id,
        "mode": _cerveau.llm.mode,
        "mode_label": stats.get("mode_label", "UNION IA 2.1"),
        "version": "2.1.0",
        "utilisateur": _cerveau.nom_utilisateur or "Louis",
        "messages_session": _cerveau.total_messages_session,
        "total_messages": _cerveau.memoire["total_messages"],
        "total_sessions": _cerveau.memoire["total_sessions"],
        "apprentissages": len(_cerveau.apprentissages),
        "faits": len(_cerveau.stockage.lister_faits()),
    })


# ── Chat (SSE) ─────────────────────────────────────────────────────────────────

@app.route("/api/chat", methods=["POST"])
def api_chat():
    _attendre_init()
    global _conv_active
    data = request.get_json(force=True, silent=True) or {}
    message = (data.get("message") or "").strip()
    conv_id = data.get("conversation_id")
    if not message:
        return jsonify({"error": "Message vide"}), 400

    # Conversation : créer ou reprendre
    if conv_id and _cerveau.stockage.conversation_existe(conv_id):
        if _conv_active != conv_id:
            _charger_conversation(conv_id)
    else:
        conv_id = _cerveau.stockage.creer_conversation(_titre_depuis(message))
        _conv_active = conv_id
        _cerveau.llm.vider_historique()

    _cerveau.stockage.ajouter_message(conv_id, "user", message)
    texte_llm, fichiers = _cerveau.injecter_fichiers(message)

    def generate():
        yield f"data: {json.dumps({'phase': 'conversation', 'content': conv_id})}\n\n"
        if fichiers:
            yield f"data: {json.dumps({'phase': 'fichiers', 'content': fichiers, 'nb': len(fichiers)})}\n\n"

        if _cerveau.llm.actif and _cerveau.besoin_llm(message):
            yield f"data: {json.dumps({'phase': 'source', 'content': _cerveau.llm.moteur_id or 'llm'})}\n\n"
            reponse_complete = ""
            llm_erreur = False
            with _llm_lock:
                for phase, contenu in _cerveau.llm.repondre_stream(
                    texte_llm, nom_utilisateur=_cerveau.nom_utilisateur
                ):
                    if phase == "erreur":
                        llm_erreur = True
                        _cerveau.llm.desactiver()
                        break
                    yield f"data: {json.dumps({'phase': phase, 'content': contenu})}\n\n"
                    if phase == "repondre":
                        reponse_complete += contenu
                    elif phase == "done":
                        break

            if llm_erreur:
                yield f"data: {json.dumps({'phase': 'source', 'content': 'ia'})}\n\n"
                reponse, _ = _cerveau.repondre(message)
                yield f"data: {json.dumps({'phase': 'repondre', 'content': reponse})}\n\n"
                yield f"data: {json.dumps({'phase': 'done', 'content': reponse})}\n\n"
                reponse_complete = reponse
            else:
                _cerveau.enregistrer_echange_llm(message, reponse_complete)

            if reponse_complete:
                _cerveau.stockage.ajouter_message(
                    conv_id, "assistant", reponse_complete, modele=_cerveau.llm.moteur_id
                )
        else:
            yield f"data: {json.dumps({'phase': 'source', 'content': 'ia'})}\n\n"
            reponse, _ = _cerveau.repondre(message)
            yield f"data: {json.dumps({'phase': 'repondre', 'content': reponse})}\n\n"
            yield f"data: {json.dumps({'phase': 'done', 'content': reponse})}\n\n"
            _cerveau.stockage.ajouter_message(conv_id, "assistant", reponse, modele="ia")

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── Conversations ──────────────────────────────────────────────────────────────

@app.route("/api/conversations")
def api_conversations():
    _attendre_init()
    return jsonify({"conversations": _cerveau.stockage.lister_conversations()})


@app.route("/api/conversations", methods=["POST"])
def api_conversation_creer():
    _attendre_init()
    global _conv_active
    cid = _cerveau.stockage.creer_conversation()
    _conv_active = cid
    _cerveau.llm.vider_historique()
    return jsonify({"id": cid})


@app.route("/api/conversations/<int:conv_id>")
def api_conversation_charger(conv_id):
    _attendre_init()
    if not _cerveau.stockage.conversation_existe(conv_id):
        return jsonify({"error": "Conversation introuvable"}), 404
    _charger_conversation(conv_id)
    return jsonify({
        "id": conv_id,
        "messages": _cerveau.stockage.lister_messages(conv_id),
    })


@app.route("/api/conversations/<int:conv_id>", methods=["DELETE"])
def api_conversation_supprimer(conv_id):
    _attendre_init()
    global _conv_active
    _cerveau.stockage.supprimer_conversation(conv_id)
    if _conv_active == conv_id:
        _conv_active = None
        _cerveau.llm.vider_historique()
    return jsonify({"success": True})


@app.route("/api/conversations/<int:conv_id>/titre", methods=["POST"])
def api_conversation_renommer(conv_id):
    _attendre_init()
    data = request.get_json(force=True, silent=True) or {}
    titre = (data.get("titre") or "").strip()
    if titre:
        _cerveau.stockage.renommer_conversation(conv_id, titre)
    return jsonify({"success": True})


@app.route("/api/search")
def api_search():
    _attendre_init()
    requete = (request.args.get("q") or "").strip()
    if not requete:
        return jsonify({"resultats": []})
    return jsonify({"resultats": _cerveau.stockage.rechercher_messages(requete)})


# ── Mémoire active ─────────────────────────────────────────────────────────────

@app.route("/api/memory")
def api_memory():
    _attendre_init()
    return jsonify({
        "faits": _cerveau.stockage.lister_faits(),
        "profil": _cerveau.stockage.profil_tout(),
        "apprentissages": _cerveau.stockage.apprentissages_tout(),
    })


@app.route("/api/memory", methods=["POST"])
def api_memory_ajouter():
    _attendre_init()
    data = request.get_json(force=True, silent=True) or {}
    cle = (data.get("cle") or "").strip()
    valeur = (data.get("valeur") or "").strip()
    categorie = (data.get("categorie") or "general").strip()
    if not cle or not valeur:
        return jsonify({"error": "cle et valeur requises"}), 400
    _cerveau.stockage.memoriser_fait(cle, valeur, categorie, source="manuel")
    return jsonify({"success": True})


@app.route("/api/memory/<path:cle>", methods=["DELETE"])
def api_memory_oublier(cle):
    _attendre_init()
    _cerveau.stockage.oublier_fait(cle)
    return jsonify({"success": True})


@app.route("/api/memory", methods=["DELETE"])
def api_memory_vider():
    _attendre_init()
    _cerveau.stockage.vider_faits()
    return jsonify({"success": True})


# ── Modes & moteurs ────────────────────────────────────────────────────────────

@app.route("/api/modes")
def api_modes():
    return jsonify({
        "modes": [{"id": k, "label": v["label"]} for k, v in MODES.items()],
        "actif": _cerveau.llm.mode if _init_done.is_set() else "2.1",
    })


@app.route("/api/mode", methods=["POST"])
def api_mode():
    _attendre_init()
    data = request.get_json(force=True, silent=True) or {}
    mode = (data.get("mode") or "").strip()
    ok, msg = _cerveau.llm.changer_mode(mode)
    if ok:
        return jsonify({"success": True, "mode": _cerveau.llm.mode, "label": msg})
    return jsonify({"success": False, "error": msg}), 400


@app.route("/api/modeles")
def api_modeles():
    return jsonify({
        "disponibles": LLMCerveau.modeles_disponibles(),
        "actif": _cerveau.llm.moteur_id if _init_done.is_set() else None,
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
        return jsonify({"success": True, "message": msg, "modele": _cerveau.llm.moteur_id})
    return jsonify({"success": False, "error": msg}), 400


# ── Profil ─────────────────────────────────────────────────────────────────────

@app.route("/api/profil", methods=["POST"])
def api_profil():
    _attendre_init()
    data = request.get_json(force=True, silent=True) or {}
    nom = (data.get("nom") or "").strip()
    if nom:
        _cerveau.nom_utilisateur = nom
    return jsonify({"success": True, "nom": _cerveau.nom_utilisateur})


# ── Authentification ───────────────────────────────────────────────────────────

@app.route("/login")
def page_login():
    return _serve("login.html")


@app.route("/api/auth/register", methods=["POST"])
def api_register():
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get("email") or "").strip()
    mdp = (data.get("password") or "").strip()
    nom = (data.get("nom") or "").strip()
    try:
        compte = _auth.creer_compte(email, mdp, nom)
        token = _auth.connecter(email, mdp)
        resp = jsonify({"success": True, "user": compte})
        resp.set_cookie("union_token", token, max_age=60*60*24*30, httponly=True, samesite="Lax")
        return resp
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get("email") or "").strip()
    mdp = (data.get("password") or "").strip()
    token = _auth.connecter(email, mdp)
    if not token:
        return jsonify({"error": "Email ou mot de passe incorrect"}), 401
    u = _auth.valider_token(token)
    resp = jsonify({"success": True, "token": token, "user": u})
    resp.set_cookie("union_token", token, max_age=60*60*24*30, httponly=True, samesite="Lax")
    return resp


@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    token = _token_request()
    if token:
        _auth.deconnecter(token)
    resp = jsonify({"success": True})
    resp.delete_cookie("union_token")
    return resp


@app.route("/api/auth/me")
def api_me():
    u = _utilisateur_courant()
    if not u:
        return jsonify({"authentifie": False}), 401
    return jsonify({"authentifie": True, "user": u})


# ── Upload & skills (fichiers binaires) ────────────────────────────────────────

@app.route("/api/upload", methods=["POST"])
def api_upload():
    """
    Reçoit un fichier multipart, le traite via les skills et retourne
    le texte extrait prêt à être injecté dans un message.
    """
    _attendre_init()
    if "fichier" not in request.files:
        return jsonify({"error": "Pas de fichier dans la requête"}), 400

    f = request.files["fichier"]
    nom = f.filename or "fichier"
    suffix = Path(nom).suffix or ".bin"

    # Sauvegarde temporaire
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        f.save(tmp.name)
        chemin = Path(tmp.name)

    try:
        md = _cerveau.skills.traiter_fichier(chemin)
        if md is not None:
            # Remplace le nom temporaire par le nom original du fichier
            md = md.replace(chemin.name, nom, 1)
            return jsonify({
                "succes": True,
                "nom": nom,
                "contenu": md,
                "skill": True,
            })
        # Fallback : tente lecture texte brute
        try:
            texte = chemin.read_text(encoding="utf-8", errors="replace")
            ext = suffix.lstrip(".")
            md = f"\n\n**Fichier `{nom}` :**\n```{ext}\n{texte[:12000]}\n```\n"
            return jsonify({"succes": True, "nom": nom, "contenu": md, "skill": False})
        except Exception:
            return jsonify({"error": f"Aucun skill disponible pour {suffix}"}), 415
    finally:
        chemin.unlink(missing_ok=True)


# ── Skills ─────────────────────────────────────────────────────────────────────

@app.route("/api/skills")
def api_skills_lister():
    _attendre_init()
    return jsonify({"skills": _cerveau.skills.lister()})


@app.route("/api/skills", methods=["POST"])
def api_skills_ajouter():
    _attendre_init()
    data = request.get_json(force=True, silent=True) or {}
    nom = (data.get("nom") or "").strip()
    if not nom:
        return jsonify({"error": "Nom requis"}), 400
    result = _cerveau.skills.ajouter_custom(data)
    return jsonify({"success": True, **result})


@app.route("/api/skills/<skill_id>", methods=["DELETE"])
def api_skills_supprimer(skill_id):
    _attendre_init()
    ok = _cerveau.skills.supprimer_custom(skill_id)
    if ok:
        return jsonify({"success": True})
    return jsonify({"error": "Skill introuvable"}), 404


# ── Admin ──────────────────────────────────────────────────────────────────────

@app.route("/admin")
def page_admin():
    return _serve("admin.html")


@app.route("/api/admin/utilisateurs")
@admin_requis
def api_admin_utilisateurs():
    return jsonify({"utilisateurs": _auth.lister_utilisateurs()})


@app.route("/api/admin/utilisateurs/<int:uid>", methods=["DELETE"])
@admin_requis
def api_admin_supprimer_user(uid):
    _auth.supprimer_utilisateur(uid)
    return jsonify({"success": True})


@app.route("/api/admin/utilisateurs/<int:uid>/role", methods=["POST"])
@admin_requis
def api_admin_changer_role(uid):
    data = request.get_json(force=True, silent=True) or {}
    role = (data.get("role") or "").strip()
    try:
        _auth.changer_role(uid, role)
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/admin/stats")
@admin_requis
def api_admin_stats():
    _attendre_init()
    stats = _cerveau.llm.stats() if _cerveau and _cerveau.llm.actif else {}
    return jsonify({
        "utilisateurs": len(_auth.lister_utilisateurs()),
        "modele": stats.get("modele", "Réseau neuronal"),
        "mode": _cerveau.llm.mode if _cerveau else "2.1",
        "faits": len(_cerveau.stockage.lister_faits()) if _cerveau else 0,
        "conversations": len(_cerveau.stockage.lister_conversations()) if _cerveau else 0,
    })


if __name__ == "__main__":
    print("UNION IA — démarrage...")
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True, use_reloader=False)
