import hashlib
import json
import os
from pathlib import Path

import numpy as np

from cerveau.langage import normaliser, supprimer_stopwords, tokeniser, vectoriser
from cerveau.reseau import Reseau


BASE_DIR = Path(__file__).parent.parent
DONNEES_DIR = BASE_DIR / "donnees"
INTENTS_PATH = DONNEES_DIR / "intents.json"
BASE_COMPLETE_PATH = DONNEES_DIR / "base_complete.json"
MODELE_PATH = DONNEES_DIR / "modele.npz"
META_PATH = DONNEES_DIR / "metadata.json"

# Epochs réduits : 500 suffit amplement pour ce réseau (vs 5000 avant)
EPOCHS_ENTRAIN = 500
LEARNING_RATE = 0.05


class Entraineur:
    def __init__(
        self,
        intents_path=INTENTS_PATH,
        modele_path=MODELE_PATH,
        meta_path=META_PATH,
        extra_intents_path=BASE_COMPLETE_PATH,
    ):
        self.intents_path = Path(intents_path)
        self.extra_intents_path = Path(extra_intents_path) if extra_intents_path else None
        self.modele_path = Path(modele_path)
        self.meta_path = Path(meta_path)
        self.vocabulaire = {}
        self.intents = []
        self.reseau = None

    def charger_intents(self):
        self.intents = []
        index_tags = {}
        for chemin in self._chemins_intents():
            with open(chemin, "r", encoding="utf-8") as f:
                for intent in json.load(f)["intents"]:
                    tag = intent["tag"]
                    if tag in index_tags:
                        existant = self.intents[index_tags[tag]]
                        existant["patterns"] = list(
                            dict.fromkeys(existant["patterns"] + intent["patterns"])
                        )
                    else:
                        index_tags[tag] = len(self.intents)
                        self.intents.append({
                            "tag": tag,
                            "patterns": list(intent["patterns"]),
                            "responses": intent["responses"],
                        })

        mots = set()
        for intent in self.intents:
            for pattern in intent["patterns"]:
                tokens = supprimer_stopwords(tokeniser(normaliser(pattern)))
                mots.update(tokens)
        self.vocabulaire = {mot: i for i, mot in enumerate(sorted(mots))}

    def preparer_donnees(self):
        X = []
        y = []
        for i, intent in enumerate(self.intents):
            for pattern in intent["patterns"]:
                vec = vectoriser(pattern, self.vocabulaire)
                X.append(vec)
                etiquette = np.zeros(len(self.intents))
                etiquette[i] = 1
                y.append(etiquette)
        return np.array(X), np.array(y)

    def entrainer(self, force=False):
        hash_intents = self._calculer_hash_intents()
        if not force and self._modele_existe() and self._hash_correspond(hash_intents):
            # Chargement rapide depuis metadata.json — pas besoin de retokeniser
            self._charger_depuis_meta()
            return

        # Réentraînement complet
        self.charger_intents()
        X, y = self.preparer_donnees()
        self.reseau = Reseau(
            taille_entree=len(self.vocabulaire),
            taille_cachee=128,
            taille_sortie=len(self.intents),
        )
        self.reseau.entrainer(X, y, epochs=EPOCHS_ENTRAIN, learning_rate=LEARNING_RATE)
        self._sauvegarder_modele(hash_intents)

    def predire(self, texte):
        vec = vectoriser(texte, self.vocabulaire)
        probas = self.reseau.forward(np.array([vec]))
        indice = int(np.argmax(probas))
        confiance = float(np.max(probas))
        return indice, confiance

    def get_intent(self, indice):
        return self.intents[indice]

    def _chemins_intents(self):
        chemins = [self.intents_path]
        if self.extra_intents_path and self.extra_intents_path.exists():
            chemins.append(self.extra_intents_path)
        return chemins

    def _calculer_hash_intents(self):
        contenu = b""
        for chemin in self._chemins_intents():
            with open(chemin, "rb") as f:
                contenu += f.read()
        return hashlib.md5(contenu).hexdigest()

    def _modele_existe(self):
        return os.path.exists(self.modele_path) and os.path.exists(self.meta_path)

    def _hash_correspond(self, hash_intents):
        try:
            with open(self.meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            return meta.get("hash") == hash_intents
        except Exception:
            return False

    def _charger_depuis_meta(self):
        """Chargement rapide : vocabulaire et tags depuis metadata.json (pas de retokenisation)."""
        with open(self.meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        self.vocabulaire = meta["vocabulaire"]
        tags = meta["intents"]

        # Charger les réponses depuis les fichiers JSON (light — on n'a besoin que des réponses)
        reponses_par_tag = {}
        for chemin in self._chemins_intents():
            with open(chemin, "r", encoding="utf-8") as f:
                for intent in json.load(f)["intents"]:
                    reponses_par_tag[intent["tag"]] = intent["responses"]

        self.intents = [
            {"tag": t, "patterns": [], "responses": reponses_par_tag.get(t, ["..."])}
            for t in tags
        ]

        self.reseau = Reseau(
            taille_entree=len(self.vocabulaire),
            taille_cachee=128,
            taille_sortie=len(self.intents),
        )
        self.reseau.charger(self.modele_path)

    def _sauvegarder_modele(self, hash_intents):
        self.modele_path.parent.mkdir(exist_ok=True)
        self.reseau.sauvegarder(self.modele_path)
        meta = {
            "vocabulaire": self.vocabulaire,
            "intents": [i["tag"] for i in self.intents],
            "hash": hash_intents,
        }
        with open(self.meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)


def charger_modele():
    entraineur = Entraineur()
    entraineur.entrainer(force=False)
    return entraineur.reseau, entraineur.vocabulaire, [i["tag"] for i in entraineur.intents]


def entrainer_modele():
    entraineur = Entraineur()
    entraineur.entrainer(force=True)
    return entraineur.reseau, entraineur.vocabulaire, [i["tag"] for i in entraineur.intents]


def charger_intents():
    entraineur = Entraineur()
    entraineur.charger_intents()
    return entraineur.intents
