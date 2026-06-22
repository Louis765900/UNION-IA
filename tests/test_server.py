"""Tests des routes du serveur web — LLM désactivé (aucun appel réseau)."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Isole la base AVANT d'importer le serveur (DB_PATH résolu dynamiquement)
import cerveau.stockage as st_mod
st_mod.DB_PATH = Path(tempfile.mkdtemp()) / "test_srv.db"

import web.server as srv

# Attend l'init en arrière-plan puis neutralise le LLM (tests hors-ligne)
srv._init_done.wait(timeout=60)
srv._cerveau.llm.desactiver()

client = srv.app.test_client()


def test_status():
    d = client.get("/api/status").get_json()
    assert d["initialisation"] is False
    assert "version" in d


def test_modes():
    d = client.get("/api/modes").get_json()
    assert {m["id"] for m in d["modes"]} == {"2.1", "flash", "flashlight"}


def test_changer_mode():
    d = client.post("/api/mode", json={"mode": "flashlight"}).get_json()
    assert d["success"] and d["mode"] == "flashlight"


def test_mode_invalide():
    r = client.post("/api/mode", json={"mode": "inexistant"})
    assert r.status_code == 400


def test_conversation_crud():
    # Créer
    cid = client.post("/api/conversations").get_json()["id"]
    assert isinstance(cid, int)
    # Lister
    convs = client.get("/api/conversations").get_json()["conversations"]
    assert any(c["id"] == cid for c in convs)
    # Supprimer
    assert client.delete(f"/api/conversations/{cid}").get_json()["success"]


def test_chat_fallback_nn():
    # LLM désactivé → réponse du réseau neuronal, persistée en base
    r = client.post("/api/chat", json={"message": "/aide"})
    texte = r.get_data(as_text=True)
    assert "data:" in texte
    assert "conversation" in texte


def test_memoire_crud():
    client.post("/api/memory", json={"cle": "k1", "valeur": "Aime tester", "categorie": "preference"})
    faits = client.get("/api/memory").get_json()["faits"]
    assert any(f["cle"] == "k1" for f in faits)
    client.delete("/api/memory/k1")
    faits = client.get("/api/memory").get_json()["faits"]
    assert not any(f["cle"] == "k1" for f in faits)


def test_recherche():
    cid = client.post("/api/conversations").get_json()["id"]
    srv._cerveau.stockage.ajouter_message(cid, "user", "question sur les fractales")
    res = client.get("/api/search?q=fractales").get_json()["resultats"]
    assert len(res) >= 1


def test_profil():
    d = client.post("/api/profil", json={"nom": "Louis"}).get_json()
    assert d["nom"] == "Louis"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"OK  {fn.__name__}")
    print(f"\n{len(fns)} tests serveur OK")
