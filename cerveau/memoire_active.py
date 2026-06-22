"""
Mémoire active de UNION IA.

Analyse les messages de l'utilisateur pour en extraire automatiquement des
faits durables (prénom, métier, lieu, préférences, projets en cours…) et les
mémorise dans le stockage. Ces faits sont ensuite injectés dans le contexte du
LLM pour que UNION IA « se souvienne » sans qu'on ait à tout répéter.

L'extraction est basée sur des motifs (regex) pour rester fiable, gratuite et
instantanée — aucun appel réseau nécessaire.
"""

import re

# Mots à ne jamais retenir comme prénom / valeur (faux positifs courants)
_STOP_VALEURS = {
    "un", "une", "le", "la", "les", "de", "du", "des", "ce", "cette",
    "pas", "plus", "très", "bien", "là", "ici", "ok", "oui", "non",
    "désolé", "désolée", "content", "contente", "sûr", "sûre", "en", "train",
}


# Articles élidés / déterminants en tête de valeur à retirer
_RE_ARTICLE_TETE = re.compile(
    r"^(?:l['’]|d['’]|le |la |les |un |une |des |de |du )\s*", re.IGNORECASE
)


# Coupe la valeur au premier connecteur (on ne garde que le 1er complément)
_RE_CONNECTEUR = re.compile(
    r"\s+(?:et|mais|car|donc|puis|ou|parce que|quand|pendant)\s+.*$", re.IGNORECASE
)


def _nettoyer(valeur: str) -> str:
    valeur = re.sub(r"\s+", " ", valeur).strip(" .,;:!?\"'’")
    valeur = _RE_CONNECTEUR.sub("", valeur)
    valeur = re.split(r"[,;]", valeur)[0]
    valeur = _RE_ARTICLE_TETE.sub("", valeur).strip()
    return valeur


def _valide(valeur: str, max_mots: int = 12) -> bool:
    v = valeur.strip().lower()
    if not v or v in _STOP_VALEURS:
        return False
    if len(valeur) < 2 or len(valeur) > 120:
        return False
    if len(valeur.split()) > max_mots:
        return False
    return True


# Classe de caractères pour une valeur textuelle (lettres, espaces, apostrophes…)
_VAL = r"[A-Za-zÀ-ÿ0-9'’\+#\-\. ]"

# Chaque règle : (clé, catégorie, regex, fonction de formatage du fait)
# La regex capture la valeur dans le groupe 1.
_REGLES = [
    # ── Identité ──────────────────────────────────────────────────────────────
    (
        "prenom", "identite",
        r"\b(?:je m['’ ]?appelle|mon (?:nom|prénom) est|appelle[- ]moi)\s+([A-Za-zÀ-ÿ\-]{2,30})",
        lambda v: f"Son prénom est {v.capitalize()}",
    ),
    (
        "age", "identite",
        r"\bj['’ ]?ai\s+(\d{1,2})\s+ans?\b",
        lambda v: f"A {v} ans",
    ),
    # ── Localisation ──────────────────────────────────────────────────────────
    (
        "lieu", "localisation",
        r"\b(?:j['’ ]?habite|je vis|je réside)\s+(?:à|en|au|aux|dans)\s+(" + _VAL + r"{2,40})",
        lambda v: f"Habite à {v}",
    ),
    # ── Métier / études ───────────────────────────────────────────────────────
    (
        "metier", "activite",
        r"\bje (?:travaille|bosse)\s+(?:comme|en tant que|dans)\s+(" + _VAL + r"{2,40})",
        lambda v: f"Travaille comme {v}",
    ),
    (
        "etudes", "activite",
        r"\b(?:j['’ ]?étudie|je fais des études (?:de|en)|je suis étudiant(?:e)? en)\s+(" + _VAL + r"{2,40})",
        lambda v: f"Étudie {v}",
    ),
    # ── Projets ───────────────────────────────────────────────────────────────
    (
        "projet", "projet",
        r"\b(?:je (?:travaille|bosse) sur|je développe|je code|mon projet (?:s['’ ]?appelle|est|c['’ ]?est))\s+(" + _VAL + r"{2,50})",
        lambda v: f"Projet en cours : {v}",
    ),
    # ── Préférences ───────────────────────────────────────────────────────────
    (
        "gout_aime", "preference",
        r"\b(?:j['’ ]?aime(?:\s+beaucoup|\s+bien)?|j['’ ]?adore|je préfère)\s+(" + _VAL + r"{2,40})",
        lambda v: f"Aime {v}",
    ),
    (
        "gout_deteste", "preference",
        r"\b(?:je déteste|je n['’ ]?aime pas|j['’ ]?ai horreur (?:de|d['’]))\s+(" + _VAL + r"{2,40})",
        lambda v: f"N'aime pas {v}",
    ),
    (
        "langage_prefere", "preference",
        r"\bmon langage (?:de programmation )?préféré (?:est|c['’ ]?est)\s+(" + _VAL + r"{2,30})",
        lambda v: f"Langage de programmation préféré : {v}",
    ),
]

_REGLES_COMPILEES = [
    (cle, cat, re.compile(rx, re.IGNORECASE), fmt) for cle, cat, rx, fmt in _REGLES
]


def extraire_faits(message: str) -> list[tuple[str, str, str]]:
    """Analyse un message et retourne les faits détectés.

    Retourne une liste de tuples (cle, valeur_formatee, categorie).
    """
    faits = []
    vus = set()
    for cle, categorie, regex, formateur in _REGLES_COMPILEES:
        m = regex.search(message)
        if not m:
            continue
        valeur = _nettoyer(m.group(1))
        # Pour les préférences/projets, on autorise plusieurs valeurs par message
        # mais on évite les doublons exacts.
        if not _valide(valeur):
            continue
        # Clé unique : pour les goûts/projets on suffixe par la valeur pour
        # pouvoir mémoriser plusieurs préférences distinctes.
        if cle in ("gout_aime", "gout_deteste", "projet", "langage_prefere"):
            cle_finale = f"{cle}:{valeur.lower()[:30]}"
        else:
            cle_finale = cle
        if cle_finale in vus:
            continue
        vus.add(cle_finale)
        faits.append((cle_finale, formateur(valeur), categorie))
    return faits


def extraire_prenom(message: str) -> str | None:
    """Extraction dédiée du prénom (utilisée pour le profil utilisateur)."""
    regex = _REGLES_COMPILEES[0][2]  # règle "prenom"
    m = regex.search(message)
    if m:
        valeur = _nettoyer(m.group(1))
        if _valide(valeur) and valeur.lower() not in _STOP_VALEURS:
            return valeur.capitalize()
    return None
