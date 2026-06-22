"""Tests de l'extraction de mémoire active."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from cerveau.memoire_active import extraire_faits, extraire_prenom


def _cles(message):
    return [f[0].split(":")[0] for f in extraire_faits(message)]


def test_prenom():
    assert extraire_prenom("je m'appelle Louis") == "Louis"
    assert extraire_prenom("Mon prénom est Marie") == "Marie"
    assert extraire_prenom("bonjour ça va") is None


def test_age():
    assert "age" in _cles("j'ai 17 ans")


def test_lieu():
    assert "lieu" in _cles("j'habite à Paris")
    assert "lieu" in _cles("je vis en France")


def test_projet():
    assert "projet" in _cles("je travaille sur UNION IA")
    assert "projet" in _cles("je développe une application web")


def test_preferences():
    cles = _cles("j'aime Python et je déteste les bugs")
    assert "gout_aime" in cles
    assert "gout_deteste" in cles


def test_langage_prefere():
    assert "langage_prefere" in _cles("mon langage préféré est Rust")


def test_etudes_avec_elision():
    # Cas piège : l'apostrophe d'élision « l'informatique »
    faits = extraire_faits("j'étudie l'informatique")
    assert any("informatique" in v for _, v, _ in faits)


def test_pas_de_faux_positifs():
    assert extraire_faits("Bonjour, comment vas-tu aujourd'hui ?") == []


def test_coupure_aux_conjonctions():
    # « j'aime Python et ... » ne doit retenir que « Python »
    faits = dict((c.split(":")[0], v) for c, v, _ in extraire_faits("j'aime Python et le café"))
    assert faits.get("gout_aime") == "Aime Python"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"OK  {fn.__name__}")
    print(f"\n{len(fns)} tests memoire active OK")
