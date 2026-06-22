"""
Backend LLM de UNION IA.

Architecture :
  - Plusieurs MOTEURS (DeepSeek API, Gemini API, llama.cpp local) interchangeables.
  - Trois MODES qui forment la gamme UNION IA, à la manière de Gemini :
        • UNION IA 2.1            → réponses complètes, raisonnement approfondi
        • UNION IA 2.1 Flash      → rapide, concis, pour le quotidien
        • UNION IA 2.1 Flashlight → ultra-rapide, réponses très courtes
  - Injection du contexte mémoire (faits sur l'utilisateur) dans le system prompt.

Le moteur est choisi automatiquement selon les clés API disponibles ; le mode
est réglable indépendamment (commande /mode ou sélecteur web).
"""

import os
import re
import importlib.util
from pathlib import Path

# ── Chemins ────────────────────────────────────────────────────────────────────
_BASE_DIR = Path(__file__).parent.parent
_PROMPT_FILE = _BASE_DIR / "system_prompt.md"

_MODELE_DEEPSEEK_LOCAL = Path(r"C:\Users\Louis\.lmstudio\models\matrixportalx\DeepSeek-R1-Distill-Llama-8B-Abliterated-Q4_K_M-GGUF\deepseek-r1-distill-llama-8b-abliterated-q4_k_m.gguf")
_MODELE_KIMI_LOCAL = Path(r"C:\Users\Louis\.lmstudio\models\ubergarm\Kimi-K2-Instruct-GGUF\imatrix-mainline-pr9400-plus-kimi-k2-942c55cd5-Kimi-K2-Instruct-Q8_0.gguf")

# ── Gamme UNION IA : les modes ──────────────────────────────────────────────────
MODES = {
    "2.1": {
        "label": "UNION IA 2.1",
        "max_tokens": 2048,
        "temperature": 0.7,
        "hint": "",
    },
    "flash": {
        "label": "UNION IA 2.1 Flash",
        "max_tokens": 1024,
        "temperature": 0.7,
        "hint": "Réponds de manière concise et directe, sans détour.",
    },
    "flashlight": {
        "label": "UNION IA 2.1 Flashlight",
        "max_tokens": 400,
        "temperature": 0.6,
        "hint": "Réponds en 1 à 3 phrases maximum. Va droit à l'essentiel.",
    },
}
MODE_DEFAUT = "2.1"


def _charger_env():
    """Charge le .env à la racine du projet s'il existe."""
    env_path = _BASE_DIR / ".env"
    if not env_path.exists():
        return
    try:
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                cle, _, valeur = line.partition("=")
                os.environ.setdefault(cle.strip(), valeur.strip())
    except Exception:
        pass


def _lire_system_prompt() -> str:
    try:
        return _PROMPT_FILE.read_text(encoding="utf-8").strip()
    except Exception:
        return (
            "Tu es UNION IA, un assistant IA personnel. "
            "Tu réponds toujours en français. Tu es direct, efficace et naturel."
        )


def construire_systeme(nom: str | None, contexte_memoire: str | None,
                       mode_hint: str) -> str:
    """Assemble le system prompt complet : personnalité + mémoire + mode."""
    parties = [_lire_system_prompt()]
    if nom:
        parties.append(f"L'utilisateur s'appelle {nom}.")
    if contexte_memoire:
        parties.append(
            "Voici ce que tu sais déjà sur l'utilisateur (utilise ces "
            "informations naturellement, sans les répéter mot pour mot) :\n"
            + contexte_memoire
        )
    if mode_hint:
        parties.append(mode_hint)
    return "\n\n".join(parties)


# ── Parser de streaming partagé (gère les balises <think>…</think>) ─────────────

def _parser_think(deltas):
    """Transforme un flux de fragments de texte en évènements UNION IA.

    Prend un itérable qui yield des chaînes (fragments du LLM).
    Yield des tuples (phase, contenu) :
        'signal'   → 'penser_debut' | 'penser_fin'
        'penser'   → fragment de raisonnement interne
        'repondre' → fragment de la réponse finale
        'done'     → texte complet de la réponse (sans le raisonnement)
    """
    reponse_complete = ""
    en_think = False
    tampon = ""

    for delta in deltas:
        if not delta:
            continue
        tampon += delta
        while tampon:
            if not en_think:
                idx = tampon.find("<think>")
                if idx == -1:
                    # Garde un éventuel début de balise partielle en fin de tampon
                    garde = _suffixe_partiel(tampon, "<think>")
                    a_emettre = tampon[: len(tampon) - garde] if garde else tampon
                    if a_emettre:
                        reponse_complete += a_emettre
                        yield ("repondre", a_emettre)
                    tampon = tampon[len(tampon) - garde:] if garde else ""
                    break
                elif idx == 0:
                    en_think = True
                    tampon = tampon[7:]
                    yield ("signal", "penser_debut")
                else:
                    avant = tampon[:idx]
                    reponse_complete += avant
                    yield ("repondre", avant)
                    tampon = tampon[idx:]
            else:
                idx = tampon.find("</think>")
                if idx == -1:
                    garde = _suffixe_partiel(tampon, "</think>")
                    a_emettre = tampon[: len(tampon) - garde] if garde else tampon
                    if a_emettre:
                        yield ("penser", a_emettre)
                    tampon = tampon[len(tampon) - garde:] if garde else ""
                    break
                else:
                    if idx > 0:
                        yield ("penser", tampon[:idx])
                    tampon = tampon[idx + 8:]
                    en_think = False
                    yield ("signal", "penser_fin")

    if tampon and not en_think:
        reponse_complete += tampon
        yield ("repondre", tampon)

    yield ("done", reponse_complete.strip())


def _suffixe_partiel(texte: str, balise: str) -> int:
    """Longueur du suffixe de `texte` qui pourrait être un début de `balise`.
    Évite de couper une balise <think> à cheval sur deux fragments."""
    maxi = min(len(texte), len(balise) - 1)
    for n in range(maxi, 0, -1):
        if balise.startswith(texte[-n:]):
            return n
    return 0


# ── Moteur DeepSeek API (compatible OpenAI) ─────────────────────────────────────

class _MoteurOpenAI:
    """Moteur générique pour toute API compatible OpenAI (DeepSeek inclus)."""

    def __init__(self, api_key: str, base_url: str, modele: str):
        self._api_key = api_key
        self._base_url = base_url
        self._modele = modele
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=self._api_key, base_url=self._base_url)
        return self._client

    def _messages(self, systeme: str, historique: list, message: str) -> list:
        msgs = [{"role": "system", "content": systeme}]
        for h in historique[-10:]:
            msgs.append({"role": "user", "content": h["user"]})
            msgs.append({"role": "assistant", "content": h["assistant"]})
        msgs.append({"role": "user", "content": message})
        return msgs

    def completer(self, systeme, historique, message, params) -> str | None:
        try:
            res = self._get_client().chat.completions.create(
                model=self._modele,
                messages=self._messages(systeme, historique, message),
                max_tokens=params["max_tokens"],
                temperature=params["temperature"],
            )
            rep = res.choices[0].message.content or ""
            rep = re.sub(r"<think>.*?</think>", "", rep, flags=re.DOTALL).strip()
            return rep or None
        except Exception:
            return None

    def stream_deltas(self, systeme, historique, message, params):
        stream = self._get_client().chat.completions.create(
            model=self._modele,
            messages=self._messages(systeme, historique, message),
            max_tokens=params["max_tokens"],
            temperature=params["temperature"],
            stream=True,
        )
        for chunk in stream:
            yield chunk.choices[0].delta.content or ""


# ── Moteur Gemini API ───────────────────────────────────────────────────────────

class _MoteurGemini:
    def __init__(self, api_key: str, modele: str = "gemini-2.0-flash"):
        self._api_key = api_key
        self._modele = modele

    def _get_model(self, systeme: str):
        import google.generativeai as genai
        genai.configure(api_key=self._api_key)
        return genai.GenerativeModel(model_name=self._modele, system_instruction=systeme)

    def _historique(self, historique: list) -> list:
        msgs = []
        for h in historique[-10:]:
            msgs.append({"role": "user", "parts": [h["user"]]})
            msgs.append({"role": "model", "parts": [h["assistant"]]})
        return msgs

    def completer(self, systeme, historique, message, params) -> str | None:
        try:
            import google.generativeai as genai
            model = self._get_model(systeme)
            chat = model.start_chat(history=self._historique(historique))
            res = chat.send_message(
                message,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=params["max_tokens"],
                    temperature=params["temperature"],
                ),
            )
            return res.text.strip() or None
        except Exception:
            return None

    def stream_deltas(self, systeme, historique, message, params):
        import google.generativeai as genai
        model = self._get_model(systeme)
        chat = model.start_chat(history=self._historique(historique))
        stream = chat.send_message(
            message,
            stream=True,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=params["max_tokens"],
                temperature=params["temperature"],
            ),
        )
        for chunk in stream:
            yield chunk.text or ""


# ── Moteur local llama.cpp ──────────────────────────────────────────────────────

class _MoteurLocal:
    def __init__(self, chemin: Path):
        self._chemin = chemin
        self._llm = None

    def _get_llm(self):
        if self._llm is None:
            from llama_cpp import Llama
            self._llm = Llama(
                model_path=str(self._chemin),
                n_ctx=8192,
                n_gpu_layers=16,
                n_threads=8,
                verbose=False,
                chat_format="chatml",
            )
        return self._llm

    def _messages(self, systeme: str, historique: list, message: str) -> list:
        msgs = [{"role": "system", "content": systeme}]
        for h in historique[-8:]:
            msgs.append({"role": "user", "content": h["user"]})
            msgs.append({"role": "assistant", "content": h["assistant"]})
        msgs.append({"role": "user", "content": message})
        return msgs

    def completer(self, systeme, historique, message, params) -> str | None:
        try:
            res = self._get_llm().create_chat_completion(
                messages=self._messages(systeme, historique, message),
                max_tokens=params["max_tokens"],
                temperature=params["temperature"],
                top_p=0.92,
                repeat_penalty=1.05,
                stop=["<|im_end|>", "</s>", "<|end|>"],
            )
            rep = res["choices"][0]["message"]["content"].strip()
            rep = re.sub(r"<think>.*?</think>", "", rep, flags=re.DOTALL).strip()
            return rep or None
        except Exception:
            return None

    def stream_deltas(self, systeme, historique, message, params):
        stream = self._get_llm().create_chat_completion(
            messages=self._messages(systeme, historique, message),
            max_tokens=params["max_tokens"],
            temperature=params["temperature"],
            top_p=0.92,
            repeat_penalty=1.05,
            stop=["<|im_end|>", "</s>", "<|end|>"],
            stream=True,
        )
        for chunk in stream:
            yield chunk["choices"][0]["delta"].get("content", "")


# ── Façade publique ─────────────────────────────────────────────────────────────

class LLMCerveau:
    """Point d'entrée unique pour le LLM de UNION IA.

    Détection automatique du moteur au démarrage :
      1. DeepSeek API   (DEEPSEEK_API_KEY)
      2. Gemini API     (GEMINI_API_KEY)
      3. llama.cpp local (GGUF, si llama-cpp installé)
    """

    def __init__(self, mode: str = MODE_DEFAUT):
        _charger_env()
        self._moteur = None
        self.moteur_id: str | None = None
        self.mode = mode if mode in MODES else MODE_DEFAUT
        self.historique: list[dict] = []
        # Fournisseur de contexte mémoire (callable -> str), branché par le Cerveau
        self.fournir_memoire = None
        self.nom_utilisateur = None
        self._auto_charger()

    # ── Sélection du moteur ──────────────────────────────────────────────────

    def _auto_charger(self):
        cle_ds = os.environ.get("DEEPSEEK_API_KEY", "")
        if cle_ds and not cle_ds.startswith("sk-REMPLACE"):
            self._moteur = _MoteurOpenAI(cle_ds, "https://api.deepseek.com", "deepseek-chat")
            self.moteur_id = "deepseek-api"
            return

        cle_gem = os.environ.get("GEMINI_API_KEY", "")
        if cle_gem and not cle_gem.startswith("AIzaSy_REMPLACE"):
            self._moteur = _MoteurGemini(cle_gem)
            self.moteur_id = "gemini-api"
            return

        if self._llama_cpp_disponible():
            if _MODELE_DEEPSEEK_LOCAL.exists():
                self._moteur = _MoteurLocal(_MODELE_DEEPSEEK_LOCAL)
                self.moteur_id = "deepseek-local"
                return
            if _MODELE_KIMI_LOCAL.exists():
                self._moteur = _MoteurLocal(_MODELE_KIMI_LOCAL)
                self.moteur_id = "kimi-local"

    def charger(self, moteur: str) -> tuple[bool, str]:
        """Change de moteur manuellement (commande /modele ou sélecteur web)."""
        _charger_env()

        if moteur in ("deepseek", "deepseek-api"):
            cle = os.environ.get("DEEPSEEK_API_KEY", "")
            if cle and not cle.startswith("sk-REMPLACE"):
                self._moteur = _MoteurOpenAI(cle, "https://api.deepseek.com", "deepseek-chat")
                self.moteur_id = "deepseek-api"
                return True, "UNION IA · DeepSeek"
            if self._llama_cpp_disponible() and _MODELE_DEEPSEEK_LOCAL.exists():
                self._moteur = _MoteurLocal(_MODELE_DEEPSEEK_LOCAL)
                self.moteur_id = "deepseek-local"
                return True, "UNION IA · DeepSeek local"
            return False, "DeepSeek indisponible (ni clé API ni modèle local)"

        if moteur in ("gemini", "gemini-api"):
            cle = os.environ.get("GEMINI_API_KEY", "")
            if cle and not cle.startswith("AIzaSy_REMPLACE"):
                self._moteur = _MoteurGemini(cle)
                self.moteur_id = "gemini-api"
                return True, "UNION IA · Gemini"
            return False, "Gemini indisponible (clé GEMINI_API_KEY absente)"

        if moteur in ("kimi", "kimi-local"):
            if self._llama_cpp_disponible() and _MODELE_KIMI_LOCAL.exists():
                self._moteur = _MoteurLocal(_MODELE_KIMI_LOCAL)
                self.moteur_id = "kimi-local"
                return True, "UNION IA · Kimi local"
            return False, "Kimi indisponible (llama-cpp ou fichier GGUF manquant)"

        return False, f"Moteur inconnu : {moteur}"

    def changer_mode(self, mode: str) -> tuple[bool, str]:
        if mode not in MODES:
            return False, f"Mode inconnu : {mode}"
        self.mode = mode
        return True, MODES[mode]["label"]

    # ── Génération ───────────────────────────────────────────────────────────

    def _systeme(self) -> str:
        contexte = None
        if callable(self.fournir_memoire):
            try:
                contexte = self.fournir_memoire()
            except Exception:
                contexte = None
        return construire_systeme(self.nom_utilisateur, contexte, MODES[self.mode]["hint"])

    def repondre(self, message: str, nom_utilisateur: str | None = None) -> str | None:
        if not self._moteur:
            return None
        if nom_utilisateur is not None:
            self.nom_utilisateur = nom_utilisateur
        rep = self._moteur.completer(
            self._systeme(), self.historique, message, MODES[self.mode]
        )
        if rep:
            self.historique.append({"user": message, "assistant": rep})
        return rep

    def repondre_stream(self, message: str, nom_utilisateur: str | None = None):
        if not self._moteur:
            yield ("erreur", "Aucun moteur LLM disponible — configure DEEPSEEK_API_KEY dans .env")
            return
        if nom_utilisateur is not None:
            self.nom_utilisateur = nom_utilisateur

        systeme = self._systeme()
        params = MODES[self.mode]

        try:
            deltas = self._moteur.stream_deltas(systeme, self.historique, message, params)
            reponse_complete = ""
            for phase, contenu in _parser_think(deltas):
                if phase == "done":
                    texte_final = contenu or reponse_complete.strip()
                    if texte_final:
                        self.historique.append({"user": message, "assistant": texte_final})
                    yield ("done", texte_final)
                    return
                if phase == "repondre":
                    reponse_complete += contenu
                yield (phase, contenu)
        except Exception as e:
            yield ("erreur", str(e))

    # ── Divers ───────────────────────────────────────────────────────────────

    def vider_historique(self):
        self.historique.clear()

    def charger_historique(self, messages: list[dict]):
        """Restaure l'historique LLM depuis une liste {user, assistant}."""
        self.historique = list(messages)

    @property
    def modele_actif(self) -> str | None:
        """Compat : identifiant du moteur courant."""
        return self.moteur_id

    def stats(self) -> dict:
        noms = {
            "deepseek-api":   "UNION IA · DeepSeek",
            "gemini-api":     "UNION IA · Gemini",
            "deepseek-local": "UNION IA · DeepSeek local",
            "kimi-local":     "UNION IA · Kimi local",
        }
        return {
            "modele": noms.get(self.moteur_id or "", "non chargé"),
            "mode": self.mode,
            "mode_label": MODES[self.mode]["label"],
            "echanges": len(self.historique),
            "gpu_couches": 16 if "local" in (self.moteur_id or "") else 0,
            "backend": self.moteur_id or "aucun",
        }

    @property
    def actif(self) -> bool:
        return self._moteur is not None

    def desactiver(self):
        """Désactive le moteur courant (ex : après un échec de chargement)."""
        self._moteur = None
        self.moteur_id = None

    @staticmethod
    def _llama_cpp_disponible() -> bool:
        try:
            return importlib.util.find_spec("llama_cpp") is not None
        except Exception:
            return False

    @staticmethod
    def modeles_disponibles() -> dict[str, bool]:
        _charger_env()
        cle_ds = os.environ.get("DEEPSEEK_API_KEY", "")
        cle_gem = os.environ.get("GEMINI_API_KEY", "")
        llama_ok = LLMCerveau._llama_cpp_disponible()
        return {
            "deepseek-api":   bool(cle_ds and not cle_ds.startswith("sk-REMPLACE")),
            "gemini-api":     bool(cle_gem and not cle_gem.startswith("AIzaSy_REMPLACE")),
            "deepseek-local": llama_ok and _MODELE_DEEPSEEK_LOCAL.exists(),
            "kimi-local":     llama_ok and _MODELE_KIMI_LOCAL.exists(),
        }
