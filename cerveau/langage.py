import re
import unicodedata

import numpy as np


STOP_WORDS = {
    "le", "la", "les", "de", "du", "des", "un", "une", "et", "ou", "je", "tu",
    "il", "elle", "nous", "vous", "ils", "elles", "me", "te", "se", "moi", "toi",
    "lui", "leur", "mon", "ma", "mes", "ton", "ta", "tes", "son", "sa", "ses",
    "ce", "cette", "ces", "est", "sont", "suis", "es", "sommes", "etes", "a",
    "ai", "as", "avons", "avez", "ont", "pour", "dans", "avec", "sur",
    "que", "qui", "dont", "tres", "plus", "moins", "tout", "tous", "toute",
    "toutes", "s'il", "stp", "svp",
}


def normaliser(texte):
    """Normalise le texte : minuscules, accents, ponctuation."""
    texte = texte.lower().strip()
    texte = unicodedata.normalize("NFKD", texte).encode("ASCII", "ignore").decode("utf-8")
    texte = re.sub(r"[^\w\s']", " ", texte)
    texte = re.sub(r"\s+", " ", texte)
    return texte.strip()


def tokeniser(texte):
    """Transforme une chaine normalisee en liste de tokens."""
    return texte.split()


def supprimer_stopwords(tokens):
    """Supprime les mots vides de la liste de tokens."""
    return [t for t in tokens if t not in STOP_WORDS and len(t) > 1]


def vectoriser(texte, vocabulaire):
    """Convertit un texte en vecteur binaire (sac de mots)."""
    texte_norm = normaliser(texte)
    tokens = tokeniser(texte_norm)
    tokens_utiles = supprimer_stopwords(tokens)
    vecteur = np.zeros(len(vocabulaire), dtype=np.float32)
    for mot in tokens_utiles:
        if mot in vocabulaire:
            vecteur[vocabulaire[mot]] = 1.0
    return vecteur
