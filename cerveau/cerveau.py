import re
import random
from datetime import datetime
from pathlib import Path
from typing import Tuple

from cerveau.llm_cerveau import LLMCerveau
from cerveau.stockage import Stockage
from cerveau.memoire_active import extraire_faits, extraire_prenom

BASE_DIR = Path(__file__).parent.parent
DONNEES_DIR = BASE_DIR / "donnees"
SEUIL_CONFIANCE = 0.55

# Regex pour détecter les références @fichier dans le message utilisateur
_RE_FICHIER_QUOTE = re.compile(r'@"([^"]+)"')
_RE_FICHIER_SIMPLE = re.compile(r'@([\w./\\:àâäéèêëîïôùûüÿç-]+\.[\w]+)')

# Intents traités localement (logique spéciale ou réponse rapide).
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
    "/memoire": "Voir ce que UNION IA a mémorisé sur toi",
    "/modele deepseek": "Passer sur DeepSeek (API ou local)",
    "/modele gemini": "Passer sur Gemini API",
    "/mode 2.1|flash|flashlight": "Changer le mode de réponse",
    "/nom [prénom]": "Changer ton prénom mémorisé",
    "/quitter": "Quitter UNION IA",
}


class Cerveau:
    def __init__(self, entraineur, stockage: Stockage | None = None):
        self.entraineur = entraineur
        self.stockage = stockage or Stockage()
        self.llm = LLMCerveau()
        # Branche la mémoire active sur le LLM (contexte injecté à chaque requête)
        self.llm.fournir_memoire = self._contexte_memoire
        self.llm.nom_utilisateur = self.nom_utilisateur
        self.messages_session: list[dict] = []
        self.total_messages_session = 0

    # ── Profil / mémoire (compat dict) ───────────────────────────────────────

    @property
    def memoire(self) -> dict:
        return {
            "nom_utilisateur": self.nom_utilisateur,
            "total_messages": int(self.stockage.profil_get("total_messages", "0") or "0"),
            "total_sessions": int(self.stockage.profil_get("total_sessions", "0") or "0"),
        }

    @property
    def nom_utilisateur(self) -> str | None:
        return self.stockage.profil_get("nom_utilisateur")

    @nom_utilisateur.setter
    def nom_utilisateur(self, valeur: str | None):
        if valeur:
            self.stockage.profil_set("nom_utilisateur", valeur)
            if self.llm:
                self.llm.nom_utilisateur = valeur

    @property
    def apprentissages(self) -> dict:
        return self.stockage.apprentissages_tout()

    # ── Mémoire active ───────────────────────────────────────────────────────

    def _contexte_memoire(self) -> str:
        """Texte des faits mémorisés, injecté dans le system prompt du LLM."""
        return self.stockage.faits_resume()

    def _apprendre_de(self, texte: str):
        """Extrait et mémorise automatiquement les faits durables du message."""
        for cle, valeur, categorie in extraire_faits(texte):
            self.stockage.memoriser_fait(cle, valeur, categorie, source="auto")
        # Prénom → profil utilisateur (prioritaire)
        prenom = extraire_prenom(texte)
        if prenom and not self.nom_utilisateur:
            self.nom_utilisateur = prenom

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
            stats = self.llm.stats() if self.llm.actif else {
                "modele": "réseau neuronal", "mode_label": "—", "gpu_couches": 0}
            total = self.memoire["total_messages"] + self.total_messages_session
            lignes = [
                "**Statistiques UNION IA**",
                f"  Moteur actif    : {stats['modele']}",
                f"  Mode            : {stats.get('mode_label', '—')}",
                f"  GPU (couches)   : {stats['gpu_couches']}",
                f"  Messages session : {self.total_messages_session}",
                f"  Messages total   : {total}",
                f"  Sessions total   : {self.memoire['total_sessions'] + 1}",
                f"  Faits mémorisés  : {len(self.stockage.lister_faits())}",
                f"  Apprentissages   : {len(self.apprentissages)}",
            ]
            if self.nom_utilisateur:
                lignes.append(f"  Utilisateur      : {self.nom_utilisateur}")
            return "\n".join(lignes)

        if cmd == "/memoire":
            faits = self.stockage.lister_faits()
            if not faits:
                return "Je n'ai encore rien mémorisé sur toi. Parle-moi un peu !"
            lignes = ["**Ce que je sais sur toi :**\n"]
            for f in faits:
                lignes.append(f"  • {f['valeur']}  _({f['categorie']})_")
            return "\n".join(lignes)

        if cmd == "/historique":
            if not self.messages_session:
                return "Aucun échange dans cette session."
            lignes = ["**Historique de la session :**\n"]
            for i, msg in enumerate(self.messages_session[-10:], 1):
                lignes.append(f"  [{i}] Toi : {msg['user']}")
                apercu = msg['ia'][:80] + ('...' if len(msg['ia']) > 80 else '')
                lignes.append(f"       IA  : {apercu}\n")
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
                    return f"Moteur changé : {msg} est maintenant actif."
                return f"Erreur de chargement : {msg}"
            return "Moteur inconnu. Essaie `/modele deepseek`, `/modele gemini` ou `/modele kimi`."

        if cmd.startswith("/mode "):
            choix = cmd.split("/mode ")[1].strip()
            ok, msg = self.llm.changer_mode(choix)
            if ok:
                return f"Mode changé : **{msg}** activé."
            return f"{msg}. Choix possibles : 2.1, flash, flashlight."

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
        Supporte @"chemin avec espaces", @chemin_fichier et @dossier/ (récursif léger).
        """
        injections: list[tuple[str, str, str]] = []

        def _lire_fichier(token: str, chemin: Path):
            try:
                contenu = chemin.read_text(encoding="utf-8", errors="replace")
                ext = chemin.suffix.lstrip(".") or "text"
                md = f'\n\n**Fichier `{chemin.name}` :**\n```{ext}\n{contenu}\n```\n'
                injections.append((token, chemin.name, md))
            except Exception:
                pass

        def _lire_dossier(token: str, dossier: Path):
            # Injecte les fichiers texte d'un dossier (non récursif profond, max 25 fichiers)
            fichiers = [
                p for p in sorted(dossier.iterdir())
                if p.is_file() and p.suffix.lower() in _EXT_TEXTE
            ][:25]
            for p in fichiers:
                _lire_fichier(token, p)

        def _traiter(token: str, chemin_str: str):
            chemin = Path(chemin_str.strip())
            if chemin.is_file():
                _lire_fichier(token, chemin)
            elif chemin.is_dir():
                _lire_dossier(token, chemin)

        for m in _RE_FICHIER_QUOTE.finditer(texte):
            _traiter(m.group(0), m.group(1))
        for m in _RE_FICHIER_SIMPLE.finditer(texte):
            if not any(m.group(0) == t for t, _, _ in injections):
                _traiter(m.group(0), m.group(1))

        noms = []
        tokens_traites = set()
        for token, nom, md in injections:
            if token not in tokens_traites:
                texte = texte.replace(token, "", 1) if token in texte else texte
                tokens_traites.add(token)
            texte += md
            noms.append(nom)
        return texte, noms

    def besoin_llm(self, texte: str) -> bool:
        """True si la requête doit aller au LLM plutôt qu'au réseau neuronal."""
        if texte.startswith("/"):
            return False
        if self._detecter_apprentissage(texte):
            return False
        texte_norm = texte.lower().strip()
        for cle in self.apprentissages:
            if cle in texte_norm:
                return False
        tag, confiance = self._predire_intent(texte)
        if tag and confiance >= SEUIL_CONFIANCE:
            return tag not in INTENTS_INSTANTANES
        return True

    def enregistrer_echange_llm(self, texte_user: str, reponse: str):
        self.total_messages_session += 1
        self._apprendre_de(texte_user)
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
        # Insensible à la casse, mais on capture depuis le texte ORIGINAL pour
        # préserver la casse de la réponse (« Hey toi ! » et non « hey toi ! »).
        m = re.search(
            r"quand (?:on dit|je dis|je tape|quelqu.un dit)\s+[\"']?(.+?)[\"']?"
            r"[,\s]+(?:tu r[ée]ponds?|r[ée]ponds?|dis)\s+[\"']?(.+?)[\"']?\.?$",
            texte,
            re.IGNORECASE,
        )
        if m:
            # La clé est normalisée en minuscules (pour la recherche),
            # la réponse garde sa casse d'origine.
            return m.group(1).strip().lower(), m.group(2).strip()
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
            self.stockage.apprentissage_set(cle, reponse)
            return f"Mémorisé ! Maintenant quand tu dis « {cle} », je répondrai « {reponse} ».", False

        # 3. Réponses apprises
        texte_norm = texte.lower().strip()
        for cle, rep in self.apprentissages.items():
            if cle in texte_norm:
                return rep, False

        # 3b. Extraction mémoire active (prénom, faits) sur le chemin non-LLM
        self._apprendre_de(texte)

        # 3c. Détection prénom explicite (réponse dédiée)
        prenom = extraire_prenom(texte)
        if prenom:
            self.nom_utilisateur = prenom
            rep = f"Ravi de te rencontrer, {prenom} ! Je m'en souviendrai pour toujours."
            self._enregistrer(texte, rep)
            return rep, False

        # 4. Réseau neuronal — intents rapides
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

            # Intent "connaissance" → toujours au LLM
            if tag not in INTENTS_INSTANTANES:
                if self.llm.actif:
                    rep = self.llm.repondre(texte, nom_utilisateur=self.nom_utilisateur)
                    if rep:
                        self._enregistrer(texte, rep)
                        return rep, False
                self._enregistrer(texte, reponse_brute)
                return reponse_brute, False

            self._enregistrer(texte, reponse_brute)
            return reponse_brute, False

        # 5. LLM pour tout le reste
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
        self.stockage.incrementer("total_messages", self.total_messages_session)
        self.stockage.incrementer("total_sessions", 1)


# Extensions de fichiers considérées comme du texte (pour @dossier)
_EXT_TEXTE = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".json", ".md",
    ".txt", ".csv", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".xml",
    ".java", ".c", ".cpp", ".h", ".hpp", ".rs", ".go", ".rb", ".php",
    ".sh", ".bat", ".sql", ".vue", ".svelte",
}
