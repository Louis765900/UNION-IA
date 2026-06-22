"""Tests de la couche de stockage SQLite."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from cerveau.stockage import Stockage


def _db():
    return Stockage(Path(tempfile.mkdtemp()) / "test.db")


def test_profil():
    s = _db()
    s.profil_set("nom_utilisateur", "Louis")
    assert s.profil_get("nom_utilisateur") == "Louis"
    assert s.profil_get("inexistant", "defaut") == "defaut"
    assert s.incrementer("compteur") == 1
    assert s.incrementer("compteur", 5) == 6


def test_conversations_et_messages():
    s = _db()
    cid = s.creer_conversation("Ma conv")
    s.ajouter_message(cid, "user", "salut")
    s.ajouter_message(cid, "assistant", "Salut !", modele="deepseek-api")
    msgs = s.lister_messages(cid)
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["modele"] == "deepseek-api"
    convs = s.lister_conversations()
    assert len(convs) == 1
    assert convs[0]["nb"] == 2


def test_recherche():
    s = _db()
    cid = s.creer_conversation("Conv")
    s.ajouter_message(cid, "user", "parle-moi de Python")
    res = s.rechercher_messages("python")
    assert len(res) == 1
    assert "Python" in res[0]["contenu"]


def test_faits_memoire():
    s = _db()
    s.memoriser_fait("projet", "Travaille sur X", "projet")
    s.memoriser_fait("projet", "Travaille sur Y", "projet")  # update
    faits = s.lister_faits()
    assert len(faits) == 1
    assert faits[0]["valeur"] == "Travaille sur Y"
    s.oublier_fait("projet")
    assert len(s.lister_faits()) == 0


def test_apprentissages():
    s = _db()
    s.apprentissage_set("Coucou", "Hey !")
    assert s.apprentissages_tout()["coucou"] == "Hey !"  # clé normalisée
    s.oublier_apprentissage("coucou")
    assert "coucou" not in s.apprentissages_tout()


def test_suppression_cascade():
    s = _db()
    cid = s.creer_conversation("X")
    s.ajouter_message(cid, "user", "test")
    s.supprimer_conversation(cid)
    assert s.lister_messages(cid) == []


def test_faits_resume():
    s = _db()
    assert s.faits_resume() == ""
    s.memoriser_fait("a", "Aime Python", "preference")
    resume = s.faits_resume()
    assert "Aime Python" in resume


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"OK  {fn.__name__}")
    print(f"\n{len(fns)} tests stockage OK")
