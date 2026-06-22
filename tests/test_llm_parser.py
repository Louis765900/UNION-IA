"""Tests du parser de streaming et de la construction du system prompt."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from cerveau.llm_cerveau import _parser_think, construire_systeme, MODES, _suffixe_partiel


def _collect(deltas):
    out = {"penser": "", "repondre": "", "signaux": [], "done": None}
    for phase, contenu in _parser_think(iter(deltas)):
        if phase == "signal":
            out["signaux"].append(contenu)
        elif phase in ("penser", "repondre"):
            out[phase] += contenu
        elif phase == "done":
            out["done"] = contenu
    return out


def test_reponse_simple():
    r = _collect(["Salut ", "Louis"])
    assert r["repondre"] == "Salut Louis"
    assert r["done"] == "Salut Louis"


def test_bloc_think():
    r = _collect(["<think>je réfléchis</think>", "Réponse"])
    assert r["penser"] == "je réfléchis"
    assert r["repondre"] == "Réponse"
    assert r["signaux"] == ["penser_debut", "penser_fin"]


def test_think_coupe_entre_fragments():
    r = _collect(["<thi", "nk>raisonnement</thi", "nk>Final"])
    assert r["penser"] == "raisonnement"
    assert r["repondre"] == "Final"


def test_think_token_par_token():
    r = _collect(list("<think>x</think>abc"))
    assert r["penser"] == "x"
    assert r["repondre"] == "abc"


def test_inferieur_non_confondu():
    r = _collect(["si a < b alors"])
    assert r["repondre"] == "si a < b alors"


def test_suffixe_partiel():
    assert _suffixe_partiel("texte<thi", "<think>") == 4
    assert _suffixe_partiel("texte", "<think>") == 0
    assert _suffixe_partiel("a<", "<think>") == 1


def test_construire_systeme():
    s = construire_systeme("Louis", "- Aime Python", MODES["flash"]["hint"])
    assert "Louis" in s
    assert "Aime Python" in s
    assert "concise" in s.lower()


def test_construire_systeme_minimal():
    s = construire_systeme(None, None, "")
    assert "UNION IA" in s


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"OK  {fn.__name__}")
    print(f"\n{len(fns)} tests parser OK")
