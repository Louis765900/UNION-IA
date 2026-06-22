import json
import re
import random
from datetime import datetime
from pathlib import Path
from typing import Tuple

import numpy as np

from cerveau.langage import normaliser, tokeniser, supprimer_stopwords, vectoriser
from cerveau.llm_cerveau import LLMCerveau

BASE_DIR = Path(__file__).parent.parent
DONNEES_DIR = BASE_DIR / "donnees"
APPRENTISSAGE_JSON = DONNEES_DIR / "apprentissage.json"
MEMOIRE_JSON = DONNEES_DIR / "memoire.json"
SEUIL_CONFIANCE = 0.55

# Regex pour détecter les références @fichier dans le message utilisateur
_RE_FICHIER_QUOTE = re.compile(r'@"([^"]+)"')
_RE_FICHIER_SIMPLE = re.compile(r'@([\w./\\:àâäéèêëîïôùûüÿç-]+\.[\w]+)')

# Intents traités localement (logique spéciale ou réponse rapide).
# Tout autre intent reconnu par le NN est redirigé vers le LLM pour une vraie réponse.
INTENTS_INSTANTANES = {
    "salutation", "au_revoir", "merci", "remerciement_special",
    "heure", "date", "calcul", "presentation", "nom_utilisateur",
    "apprendre", "aide", "insulte",
}

COMMANDES = {
    "/aide": "Afficher les commandes disponibles",
    "/stats": "Statistiques de la session",
    "/historique": "Voir les derniers échanges",
    "/oublier": "Effacer l'historique de conversation",
    "/modele deepseek": "Passer sur DeepSeek (API ou local)",
    "/modele gemini": "Passer sur Gemini API",
    "/modele kimi": "Passer sur Kimi (local)",
    "/nom [prénom]": "Changer ton prénom mémorisé",
    "/quitter": "Quitter UNION IA",
}


class Cerveau:
    def __init__(self, entraineur):
        self.entraineur = entraineur
        self.llm = LLMCerveau()
        self.memoire = self._charger_memoire()
        self.apprentissages = self._charger_apprentissages()
        self.messages_session: list[dict] = []
        self.total_messages_session = 0

    # ── Mémoire persistante ──────────────────────────────────────────────────

    def _charger_memoire(self) -> dict:
        if MEMOIRE_JSON.exists():
            try:
                with open(MEMOIRE_JSON, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"nom_utilisateur": None, "total_messages": 0, "total_sessions": 0}

    def _sauvegarder_memoire(self):
        DONNEES_DIR.mkdir(exist_ok=True)
        with open(MEMOIRE_JSON, "w", encoding="utf-8") as f:
            json.dump(self.memoire, f, ensure_ascii=False, indent=2)

    @property
    def nom_utilisateur(self) -> str | None:
        return self.memoire.get("nom_utilisateur")

    @nom_utilisateur.setter
    def nom_utilisateur(self, valeur: str | None):
        self.memoire["nom_utilisateur"] = valeur
        self._sauvegarder_memoire()

    # ── Apprentissages ───────────────────────────────────────────────────────

    def _charger_apprentissages(self) -> dict:
        if APPRENTISSAGE_JSON.exists():
            try:
                with open(APPRENTISSAGE_JSON, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _sauvegarder_apprentissage(self, cle: str, reponse: str):
        self.apprentissages[cle] = reponse
        DONNEES_DIR.mkdir(exist_ok=True)
        with open(APPRENTISSAGE_JSON, "w", encoding="utf-8") as f:
            json.dump(self.apprentissages, f, ensure_ascii=False, indent=2)

    # ── Chargement LLM ───────────────────────────────────────────────────────

    def charger_llm(self, modele: str = "deepseek") -> tuple[bool, str]:
        return self.llm.charger(modele)

    # ── Commandes spéciales ──────────────────────────────────────────────────

    def _traiter_commande(self, texte: str) -> str | None:
        cmd = texte.strip().lower()

        if cmd == "/aide":
            lignes = ["**Commandes UNION IA :**\n"]
            for c, desc in COMMANDES.items():
                lignes.append(f"  {c} — {desc}")
            return "\n".join(lignes)

        if cmd == "/stats":
            llm_stats = self.llm.stats() if self.llm.actif else {"modele": "réseau neuronal", "echanges": 0, "gpu_couches": 0}
            total = self.memoire.get("total_messages", 0) + self.total_messages_session
            lignes = [
                "**Statistiques UNION IA**",
                f"  Modèle actif    : {llm_stats['modele']}",
                f"  GPU (couches)   : {llm_stats['gpu_couches']}",
                f"  Messages session : {self.total_messages_session}",
                f"  Messages total   : {total}",
                f"  Sessions total   : {self.memoire.get('total_sessions', 0) + 1}",
                f"  Apprentissages   : {len(self.apprentissages)}",
            ]
            if self.nom_utilisateur:
                lignes.append(f"  Utilisateur      : {self.nom_utilisateur}")
            return "\n".join(lignes)

        if cmd == "/historique":
            if not self.messages_session:
                return "Aucun échange dans cette session."
            lignes = ["**Historique de la session :**\n"]
            for i, msg in enumerate(self.messages_session[-10:], 1):
                lignes.append(f"  [{i}] Toi : {msg['user']}")
                lignes.append(f"       IA  : {msg['ia'][:80]}{'...' if len(msg['ia']) > 80 else ''}\n")
            return "\n".join(lignes)

        if cmd == "/oublier":
            self.messages_session.clear()
            self.llm.vider_historique()
            return "Historique effacé. Je repars de zéro !"

        if cmd.startswith("/modele "):
            choix = cmd.split("/modele ")[1].strip()
            if choix in ("deepseek", "gemini", "kimi", "deepseek-api", "gemini-api", "kimi-local"):
                ok, msg = self.llm.charger(choix)
                if ok:
                    return f"Backend changé : {msg} est maintenant actif."
                return f"Erreur de chargement : {msg}"
            return "Backend inconnu. Essaie `/modele deepseek`, `/modele gemini` ou `/modele kimi`."

        if cmd.startswith("/nom "):
            nouveau = texte.strip()[5:].strip()
            if nouveau:
                self.nom_utilisateur = nouveau
                return f"Compris ! Je me souviendrai de toi en tant que **{nouveau}** pour toujours."
            return "Donne-moi un prénom après `/nom`."

        if cmd in ("/quitter", "/quit", "/exit"):
            return "QUITTER"

        return None

    # ── Prédiction réseau neuronal ───────────────────────────────────────────

    def _predire_intent(self, texte: str) -> tuple[str | None, float]:
        try:
            indice, confiance = self.entraineur.predire(texte)
            tag = self.entraineur.get_intent(indice)["tag"]
            return tag, confiance
        except Exception:
            return None, 0.0

    def _reponse_intent(self, tag: str) -> str:
        for intent in self.entraineur.intents:
            if intent["tag"] == tag:
                return random.choice(intent["responses"])
        return ""

    # ── Injection de fichiers (@chemin) ─────────────────────────────────────

    def injecter_fichiers(self, texte: str) -> tuple[str, list[str]]:
        """Remplace les @chemin par le contenu du fichier dans le texte.
        Retourne (texte_enrichi, liste_noms_fichiers_injectés).
        Supporte @"chemin avec espaces" et @chemin_sans_espaces.
        """
        injections: list[tuple[str, str, str]] = []  # (token_original, nom, contenu_md)

        def _lire(token: str, chemin_str: str):
            chemin = Path(chemin_str.strip())
            if chemin.exists() and chemin.is_file():
                try:
                    contenu = chemin.read_text(encoding="utf-8", errors="replace")
                    ext = chemin.suffix.lstrip(".") or "text"
                    md = f'\n\n**Fichier `{chemin.name}` :**\n```{ext}\n{contenu}\n```\n'
                    injections.append((token, chemin.name, md))
                except Exception:
                    pass

        for m in _RE_FICHIER_QUOTE.finditer(texte):
            _lire(m.group(0), m.group(1))
        for m in _RE_FICHIER_SIMPLE.finditer(texte):
            if not any(m.group(0) == t for t, _, _ in injections):
                _lire(m.group(0), m.group(1))

        noms = []
        for token, nom, md in injections:
            texte = texte.replace(token, md, 1)
            noms.append(nom)
        return texte, noms

    def besoin_llm(self, texte: str) -> bool:
        """Retourne True si cette requête doit aller au LLM plutôt qu'au réseau neuronal."""
        if texte.startswith("/"):
            return False
        if self._detecter_apprentissage(texte):
            return False
        texte_norm = texte.lower().strip()
        for cle in self.apprentissages:
            if cle in texte_norm:
                return False
        m_nom = re.search(
            r"(?:m[' ]?appelle?|je suis|mon nom est|appelle moi|mon prénom est)\s+([A-ZÀ-Ÿa-zà-ÿ]+)",
            texte, re.IGNORECASE
        )
        if m_nom:
            return False
        tag, confiance = self._predire_intent(texte)
        if tag and confiance >= SEUIL_CONFIANCE:
            return tag not in INTENTS_INSTANTANES
        return True  # confiance trop basse → LLM

    def enregistrer_echange_llm(self, texte_user: str, reponse: str):
        """Enregistre un échange LLM dans l'historique de session."""
        self.total_messages_session += 1
        self._enregistrer(texte_user, reponse)

    # ── Calcul mathématique ──────────────────────────────────────────────────

    def _calculer(self, expression: str) -> str:
        safe = re.sub(r"[^\d\s\+\-\*\/\.\(\)%]", "", expression).strip()
        if not safe:
            return "Expression invalide."
        try:
            resultat = eval(safe, {"__builtins__": {}}, {})
            return f"Résultat : {expression.strip()} = {resultat}"
        except Exception:
            return "Je n'arrive pas à calculer ça."

    # ── Apprentissage live ───────────────────────────────────────────────────

    def _detecter_apprentissage(self, texte: str) -> tuple[str, str] | None:
        m = re.search(
            r"quand (?:on dit|je dis|je tape|quelqu.un dit)\s+[\"']?(.+?)[\"']?"
            r"[,\s]+(?:tu r[ée]ponds?|r[ée]ponds?|dis)\s+[\"']?(.+?)[\"']?\.?$",
            texte.lower(),
        )
        if m:
            return m.group(1).strip(), m.group(2).strip()
        return None

    # ── Point d'entrée principal ─────────────────────────────────────────────

    def repondre(self, texte: str) -> Tuple[str, bool]:
        texte = texte.strip()
        if not texte:
            return "Dis-moi quelque chose !", False

        self.total_messages_session += 1

        # 1. Commandes /
        if texte.startswith("/"):
            res = self._traiter_commande(texte)
            if res == "QUITTER":
                return "À bientôt !", True
            if res:
                return res, False

        # 2. Apprentissage live
        appr = self._detecter_apprentissage(texte)
        if appr:
            cle, reponse = appr
            self._sauvegarder_apprentissage(cle, reponse)
            return f"Mémorisé ! Maintenant quand tu dis « {cle} », je répondrai « {reponse} ».", False

        # 3. Réponses apprises
        texte_norm = texte.lower().strip()
        for cle, rep in self.apprentissages.items():
            if cle in texte_norm:
                return rep, False

        # 3b. Détection prénom (prioritaire, avant le réseau)
        m_nom = re.search(
            r"(?:m[' ]?appelle?|je suis|mon nom est|appelle moi|mon prénom est)\s+([A-ZÀ-Ÿa-zà-ÿ]+)",
            texte, re.IGNORECASE
        )
        if m_nom:
            prenom = m_nom.group(1).capitalize()
            if prenom.lower() not in ("une", "un", "le", "la", "les", "de", "du"):
                self.nom_utilisateur = prenom
                rep = f"Ravi de te rencontrer, {prenom} ! Je m'en souviendrai pour toujours."
                self._enregistrer(texte, rep)
                return rep, False

        # 4. Réseau neuronal — intents rapides (heure, date, calcul, etc.)
        tag, confiance = self._predire_intent(texte)

        if tag and confiance >= SEUIL_CONFIANCE:
            reponse_brute = self._reponse_intent(tag)

            if tag == "au_revoir":
                self._fin_session()
                return reponse_brute, True

            if tag == "heure" or "SPECIAL:heure" in reponse_brute:
                rep = f"Il est {datetime.now().strftime('%H:%M')}."
                self._enregistrer(texte, rep)
                return rep, False

            if tag == "date" or "SPECIAL:date" in reponse_brute:
                jours = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
                mois = ["janvier", "février", "mars", "avril", "mai", "juin",
                        "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
                now = datetime.now()
                rep = f"Nous sommes le {jours[now.weekday()]} {now.day} {mois[now.month - 1]} {now.year}."
                self._enregistrer(texte, rep)
                return rep, False

            if tag == "calcul" or "SPECIAL:calcul" in reponse_brute:
                expr = re.sub(r"(calcule?|fais?|combien|vaut|fait)\s*", "", texte, flags=re.IGNORECASE).strip()
                rep = self._calculer(expr)
                self._enregistrer(texte, rep)
                return rep, False

            if tag == "presentation" or "SPECIAL:nom" in reponse_brute:
                m = re.search(
                    r"(?:m[' ]?appelle?|je suis|mon nom est|appelle moi)\s+([A-ZÀ-Ÿa-zà-ÿ]+)",
                    texte, re.IGNORECASE
                )
                if m:
                    self.nom_utilisateur = m.group(1).capitalize()
                    rep = f"Ravi de te rencontrer, {self.nom_utilisateur} ! Je m'en souviendrai."
                    self._enregistrer(texte, rep)
                    return rep, False

            if "SPECIAL:get_nom" in reponse_brute:
                if self.nom_utilisateur:
                    rep = f"Tu t'appelles {self.nom_utilisateur} !"
                else:
                    rep = "Tu ne m'as pas encore dit ton prénom. Dis-moi `/nom [prénom]` ou « je m'appelle … »."
                self._enregistrer(texte, rep)
                return rep, False

            if tag == "apprendre" or "SPECIAL:apprendre" in reponse_brute:
                rep = "Pour m'apprendre quelque chose, dis : « Quand on dit X, tu réponds Y »."
                self._enregistrer(texte, rep)
                return rep, False

            # Intent "connaissance" → toujours au LLM pour une vraie réponse
            if tag not in INTENTS_INSTANTANES:
                if self.llm.actif:
                    rep = self.llm.repondre(texte, nom_utilisateur=self.nom_utilisateur)
                    if rep:
                        self._enregistrer(texte, rep)
                        return rep, False
                # LLM inactif → fallback réponse NN
                self._enregistrer(texte, reponse_brute)
                return reponse_brute, False

            # Intent instantané reconnu → réponse directe du réseau
            self._enregistrer(texte, reponse_brute)
            return reponse_brute, False

        # 5. LLM (DeepSeek R1 / Kimi K2) pour tout le reste
        if self.llm.actif:
            rep = self.llm.repondre(texte, nom_utilisateur=self.nom_utilisateur)
            if rep:
                self._enregistrer(texte, rep)
                return rep, False

        # 6. Fallback réseau neuronal basse confiance
        if tag and confiance > 0.3:
            rep = self._reponse_intent(tag)
            self._enregistrer(texte, rep)
            return rep, False

        return "Je ne suis pas sûr de comprendre. Reformule ou tape `/aide`.", False

    def _enregistrer(self, user: str, ia: str):
        self.messages_session.append({"user": user, "ia": ia})

    def _fin_session(self):
        self.memoire["total_messages"] = self.memoire.get("total_messages", 0) + self.total_messages_session
        self.memoire["total_sessions"] = self.memoire.get("total_sessions", 0) + 1
        self._sauvegarder_memoire()
