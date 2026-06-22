"""
Backend LLM de UNION IA.

Priorité de chargement :
  1. DeepSeek API (cloud, clé DEEPSEEK_API_KEY dans .env)
  2. Gemini API   (cloud, clé GEMINI_API_KEY dans .env)
  3. Modèle local llama.cpp (GGUF, Windows uniquement)
"""

import os
import re
import json
from pathlib import Path

# ── Chemins ────────────────────────────────────────────────────────────────────
_BASE_DIR = Path(__file__).parent.parent
_PROMPT_FILE = _BASE_DIR / "system_prompt.md"

# Chemins locaux (fallback Windows)
_MODELE_DEEPSEEK_LOCAL = Path(r"C:\Users\Louis\.lmstudio\models\matrixportalx\DeepSeek-R1-Distill-Llama-8B-Abliterated-Q4_K_M-GGUF\deepseek-r1-distill-llama-8b-abliterated-q4_k_m.gguf")
_MODELE_KIMI_LOCAL = Path(r"C:\Users\Louis\.lmstudio\models\ubergarm\Kimi-K2-Instruct-GGUF\imatrix-mainline-pr9400-plus-kimi-k2-942c55cd5-Kimi-K2-Instruct-Q8_0.gguf")


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


# ── Backend DeepSeek API ────────────────────────────────────────────────────────

class _BackendDeepSeek:
    NOM = "UNION IA"
    ID = "deepseek"
    ENDPOINT = "https://api.deepseek.com"
    MODELE = "deepseek-chat"

    def __init__(self, api_key: str):
        # Import différé — ne bloque pas le démarrage
        self._api_key = api_key
        self._client = None
        self._modele = self.MODELE

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=self._api_key, base_url=self.ENDPOINT)
        return self._client

    def _messages(self, message: str, historique: list, nom: str | None) -> list:
        sys = _lire_system_prompt()
        if nom:
            sys += f"\n\nL'utilisateur s'appelle {nom}."
        msgs = [{"role": "system", "content": sys}]
        for h in historique[-10:]:
            msgs.append({"role": "user", "content": h["user"]})
            msgs.append({"role": "assistant", "content": h["assistant"]})
        msgs.append({"role": "user", "content": message})
        return msgs

    def repondre(self, message: str, historique: list, nom: str | None = None) -> str | None:
        try:
            res = self._get_client().chat.completions.create(
                model=self._modele,
                messages=self._messages(message, historique, nom),
                max_tokens=2048,
                temperature=0.75,
            )
            reponse = res.choices[0].message.content or ""
            reponse = re.sub(r"<think>.*?</think>", "", reponse, flags=re.DOTALL).strip()
            return reponse or None
        except Exception:
            return None

    def repondre_stream(self, message: str, historique: list, nom: str | None = None):
        try:
            stream = self._get_client().chat.completions.create(
                model=self._modele,
                messages=self._messages(message, historique, nom),
                max_tokens=2048,
                temperature=0.75,
                stream=True,
            )
            reponse_complete = ""
            en_think = False
            tampon = ""

            for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                if not delta:
                    continue
                tampon += delta

                while tampon:
                    if not en_think:
                        idx = tampon.find("<think>")
                        if idx == -1:
                            reponse_complete += tampon
                            yield ("repondre", tampon)
                            tampon = ""
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
                            yield ("penser", tampon)
                            tampon = ""
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

        except KeyboardInterrupt:
            yield ("done", "")
        except Exception as e:
            yield ("erreur", str(e))


# ── Backend Gemini API ──────────────────────────────────────────────────────────

class _BackendGemini:
    NOM = "UNION IA"
    ID = "gemini"
    MODELE = "gemini-2.0-flash"

    def __init__(self, api_key: str):
        # Import différé — ne bloque pas le démarrage
        self._api_key = api_key

    def _construire_historique_gemini(self, historique: list) -> list:
        msgs = []
        for h in historique[-10:]:
            msgs.append({"role": "user", "parts": [h["user"]]})
            msgs.append({"role": "model", "parts": [h["assistant"]]})
        return msgs

    def _get_model(self, nom: str | None = None):
        import google.generativeai as genai
        genai.configure(api_key=self._api_key)
        sys_prompt = _lire_system_prompt()
        if nom:
            sys_prompt += f"\n\nL'utilisateur s'appelle {nom}."
        return genai.GenerativeModel(model_name=self.MODELE, system_instruction=sys_prompt)

    def repondre(self, message: str, historique: list, nom: str | None = None) -> str | None:
        try:
            model = self._get_model(nom)
            chat = model.start_chat(history=self._construire_historique_gemini(historique))
            res = chat.send_message(message)
            return res.text.strip() or None
        except Exception:
            return None

    def repondre_stream(self, message: str, historique: list, nom: str | None = None):
        try:
            model = self._get_model(nom)
            chat = model.start_chat(history=self._construire_historique_gemini(historique))
            stream = chat.send_message(message, stream=True)
            reponse_complete = ""
            for chunk in stream:
                texte = chunk.text or ""
                if texte:
                    reponse_complete += texte
                    yield ("repondre", texte)
            yield ("done", reponse_complete.strip())
        except KeyboardInterrupt:
            yield ("done", "")
        except Exception as e:
            yield ("erreur", str(e))


# ── Backend local llama.cpp ─────────────────────────────────────────────────────

class _BackendLocal:
    NOM = "UNION IA"
    ID = "local"

    def __init__(self, chemin: Path, nom_modele: str):
        # Import différé — le chargement GGUF est lourd, on attend le premier message
        self._chemin = chemin
        self._nom = nom_modele
        self._llm = None

    def _get_llm(self):
        if self._llm is None:
            from llama_cpp import Llama
            self._llm = Llama(
                model_path=str(self._chemin),
                n_ctx=4096,
                n_gpu_layers=16,
                n_threads=8,
                verbose=False,
                chat_format="chatml",
            )
        return self._llm

    def _messages(self, message: str, historique: list, nom: str | None) -> list:
        sys = _lire_system_prompt()
        if nom:
            sys += f"\n\nL'utilisateur s'appelle {nom}."
        msgs = [{"role": "system", "content": sys}]
        for h in historique[-8:]:
            msgs.append({"role": "user", "content": h["user"]})
            msgs.append({"role": "assistant", "content": h["assistant"]})
        msgs.append({"role": "user", "content": message})
        return msgs

    def repondre(self, message: str, historique: list, nom: str | None = None) -> str | None:
        try:
            res = self._get_llm().create_chat_completion(
                messages=self._messages(message, historique, nom),
                max_tokens=2048,
                temperature=0.75,
                top_p=0.92,
                repeat_penalty=1.05,
                stop=["<|im_end|>", "</s>", "<|end|>"],
            )
            reponse = res["choices"][0]["message"]["content"].strip()
            reponse = re.sub(r"<think>.*?</think>", "", reponse, flags=re.DOTALL).strip()
            return reponse or None
        except Exception:
            return None

    def repondre_stream(self, message: str, historique: list, nom: str | None = None):
        try:
            stream = self._get_llm().create_chat_completion(
                messages=self._messages(message, historique, nom),
                max_tokens=2048,
                temperature=0.75,
                top_p=0.92,
                repeat_penalty=1.05,
                stop=["<|im_end|>", "</s>", "<|end|>"],
                stream=True,
            )
            reponse_complete = ""
            en_think = False
            tampon = ""

            for chunk in stream:
                delta = chunk["choices"][0]["delta"].get("content", "")
                if not delta:
                    continue
                tampon += delta

                while tampon:
                    if not en_think:
                        idx = tampon.find("<think>")
                        if idx == -1:
                            reponse_complete += tampon
                            yield ("repondre", tampon)
                            tampon = ""
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
                            yield ("penser", tampon)
                            tampon = ""
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

        except KeyboardInterrupt:
            yield ("done", "")
        except Exception as e:
            yield ("erreur", str(e))


# ── Façade publique ─────────────────────────────────────────────────────────────

class LLMCerveau:
    """Point d'entrée unique pour le backend LLM.

    Détection automatique au démarrage :
      1. DeepSeek API (DEEPSEEK_API_KEY dans .env ou env)
      2. Gemini API   (GEMINI_API_KEY dans .env ou env)
      3. Modèle local llama.cpp (GGUF)
    """

    def __init__(self):
        _charger_env()
        self._backend = None
        self.historique: list[dict] = []
        self.modele_actif: str | None = None
        self._auto_charger()

    def _auto_charger(self):
        """Sélectionne le meilleur backend disponible — sans aucun import réseau.
        Les librairies sont importées paresseusement au premier message."""

        # 1. DeepSeek API
        cle_ds = os.environ.get("DEEPSEEK_API_KEY", "")
        if cle_ds and not cle_ds.startswith("sk-REMPLACE"):
            self._backend = _BackendDeepSeek(cle_ds)
            self.modele_actif = "deepseek-api"
            return

        # 2. Gemini API
        cle_gem = os.environ.get("GEMINI_API_KEY", "")
        if cle_gem and not cle_gem.startswith("AIzaSy_REMPLACE"):
            self._backend = _BackendGemini(cle_gem)
            self.modele_actif = "gemini-api"
            return

        # 3. Modèle local — uniquement si llama-cpp est installé
        if self._llama_cpp_disponible():
            if _MODELE_DEEPSEEK_LOCAL.exists():
                self._backend = _BackendLocal(_MODELE_DEEPSEEK_LOCAL, "deepseek")
                self.modele_actif = "deepseek-local"
                return
            if _MODELE_KIMI_LOCAL.exists():
                self._backend = _BackendLocal(_MODELE_KIMI_LOCAL, "kimi")
                self.modele_actif = "kimi-local"

    def charger(self, modele: str = "deepseek") -> tuple[bool, str]:
        """Charge manuellement un backend spécifique (commande /modele)."""
        _charger_env()

        if modele in ("deepseek", "deepseek-api"):
            cle = os.environ.get("DEEPSEEK_API_KEY", "")
            if cle and not cle.startswith("sk-REMPLACE"):
                try:
                    self._backend = _BackendDeepSeek(cle)
                    self.modele_actif = "deepseek-api"
                    self.historique.clear()
                    return True, "UNION IA (DeepSeek API)"
                except Exception as e:
                    return False, str(e)
            if _MODELE_DEEPSEEK_LOCAL.exists():
                try:
                    self._backend = _BackendLocal(_MODELE_DEEPSEEK_LOCAL, "deepseek")
                    self.modele_actif = "deepseek-local"
                    self.historique.clear()
                    return True, "UNION IA (local DeepSeek)"
                except Exception as e:
                    return False, str(e)
            return False, "DeepSeek non disponible (ni API ni fichier local)"

        if modele in ("gemini", "gemini-api"):
            cle = os.environ.get("GEMINI_API_KEY", "")
            if cle and not cle.startswith("AIzaSy_REMPLACE"):
                try:
                    self._backend = _BackendGemini(cle)
                    self.modele_actif = "gemini-api"
                    self.historique.clear()
                    return True, "UNION IA (Gemini API)"
                except Exception as e:
                    return False, str(e)
            return False, "Gemini non disponible (clé GEMINI_API_KEY absente)"

        if modele in ("kimi", "kimi-local"):
            if _MODELE_KIMI_LOCAL.exists():
                try:
                    self._backend = _BackendLocal(_MODELE_KIMI_LOCAL, "kimi")
                    self.modele_actif = "kimi-local"
                    self.historique.clear()
                    return True, "UNION IA (local Kimi)"
                except Exception as e:
                    return False, str(e)
            return False, "Kimi non disponible (fichier GGUF introuvable)"

        return False, f"Modèle inconnu : {modele}"

    def repondre(self, message: str, nom_utilisateur: str | None = None) -> str | None:
        if not self._backend:
            return None
        rep = self._backend.repondre(message, self.historique, nom_utilisateur)
        if rep:
            self.historique.append({"user": message, "assistant": rep})
        return rep

    def repondre_stream(self, message: str, nom_utilisateur: str | None = None):
        if not self._backend:
            yield ("erreur", "Aucun backend LLM disponible — configure DEEPSEEK_API_KEY dans .env")
            return
        reponse_complete = ""
        for phase, contenu in self._backend.repondre_stream(message, self.historique, nom_utilisateur):
            yield (phase, contenu)
            if phase == "repondre":
                reponse_complete += contenu
            elif phase == "done":
                texte_final = contenu or reponse_complete.strip()
                if texte_final:
                    self.historique.append({"user": message, "assistant": texte_final})
                return

    def vider_historique(self):
        self.historique.clear()

    def stats(self) -> dict:
        noms = {
            "deepseek-api":   "UNION IA · DeepSeek API",
            "gemini-api":     "UNION IA · Gemini API",
            "deepseek-local": "UNION IA · DeepSeek local",
            "kimi-local":     "UNION IA · Kimi local",
        }
        return {
            "modele": noms.get(self.modele_actif or "", "non chargé"),
            "echanges": len(self.historique),
            "gpu_couches": 16 if "local" in (self.modele_actif or "") else 0,
            "backend": self.modele_actif or "aucun",
        }

    @property
    def actif(self) -> bool:
        return self._backend is not None

    @staticmethod
    def _llama_cpp_disponible() -> bool:
        try:
            import importlib.util
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
