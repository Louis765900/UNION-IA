"""Tests du Cerveau (routage, commandes, mémoire) — sans appel LLM réseau."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from cerveau.stockage import Stockage
from cerveau.cerveau import Cerveau


class FauxEntraineur:
    """Confiance nulle → le routage n'utilise jamais le NN (et le LLM est neutralisé)."""
    intents = [{"tag": "salutation", "responses": ["Salut !"]}]

    def predire(self, texte):
        return 0, 0.01

    def get_intent(self, i):
        return self.intents[i]


def _cerveau():
    tmp = Path(tempfile.mkdtemp()) / "test.db"
    c = Cerveau(FauxEntraineur(), stockage=Stockage(tmp))
    # Neutralise le LLM pour des tests déterministes hors-ligne
    c.llm.desactiver()
    return c


def test_commande_aide():
    rep, quitter = _cerveau().repondre("/aide")
    assert "Commandes UNION IA" in rep
    assert quitter is False


def test_detection_prenom():
    c = _cerveau()
    rep, _ = c.repondre("je m'appelle Louis")
    assert "Louis" in rep
    assert c.nom_utilisateur == "Louis"


def test_memoire_active():
    c = _cerveau()
    c.repondre("je travaille sur UNION IA et j'aime Python")
    faits = [f["valeur"] for f in c.stockage.lister_faits()]
    assert any("UNION IA" in f for f in faits)
    assert any("Python" in f for f in faits)


def test_apprentissage_live_preserve_casse():
    c = _cerveau()
    rep, _ = c.repondre("quand on dit coucou, tu réponds Hey toi !")
    assert "Mémorisé" in rep
    rep, _ = c.repondre("coucou")
    assert rep == "Hey toi !"  # casse préservée


def test_commande_memoire():
    c = _cerveau()
    c.repondre("j'aime Python")
    rep, _ = c.repondre("/memoire")
    assert "Python" in rep


def test_changement_mode():
    c = _cerveau()
    rep, _ = c.repondre("/mode flash")
    assert "Flash" in rep
    assert c.llm.mode == "flash"


def test_calcul():
    c = _cerveau()
    # Force un intent calcul via réponse directe
    assert "8" in c._calculer("5 + 3")


def test_persistance():
    tmp = Path(tempfile.mkdtemp()) / "p.db"
    c1 = Cerveau(FauxEntraineur(), stockage=Stockage(tmp))
    c1.llm.desactiver()
    c1.repondre("je m'appelle Louis")
    c1.repondre("j'aime Python")

    c2 = Cerveau(FauxEntraineur(), stockage=Stockage(tmp))
    assert c2.nom_utilisateur == "Louis"
    assert len(c2.stockage.lister_faits()) >= 1


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"OK  {fn.__name__}")
    print(f"\n{len(fns)} tests cerveau OK")
