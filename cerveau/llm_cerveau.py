import re
from pathlib import Path

MODELE_DEEPSEEK = Path(r"C:\Users\Louis\.lmstudio\models\matrixportalx\DeepSeek-R1-Distill-Llama-8B-Abliterated-Q4_K_M-GGUF\deepseek-r1-distill-llama-8b-abliterated-q4_k_m.gguf")
MODELE_KIMI = Path(r"C:\Users\Louis\.lmstudio\models\ubergarm\Kimi-K2-Instruct-GGUF\imatrix-mainline-pr9400-plus-kimi-k2-942c55cd5-Kimi-K2-Instruct-Q8_0.gguf")

NOMS_MODELES = {
    "deepseek": "UNION IA",
    "kimi": "UNION IA",
}

# Fichier de personnalité éditable — modifiez ce fichier pour changer le comportement de l'IA
_PROMPT_FILE = Path(__file__).parent.parent / "system_prompt.md"


def _lire_systeme_prompt() -> str:
    """Lit le system prompt depuis system_prompt.md. Relu à chaque requête → changements actifs sans redémarrage."""
    try:
        return _PROMPT_FILE.read_text(encoding="utf-8").strip()
    except Exception:
        return (
            "Tu es UNION IA, l'assistant IA personnel de Louis Têtu. "
            "Tu réponds toujours en français. Tu es direct, efficace, et tu gères le code avec assurance."
        )


class LLMCerveau:
    def __init__(self):
        self.llm = None
        self.historique: list[dict] = []
        self.modele_actif: str | None = None

    def charger(self, modele: str = "deepseek") -> tuple[bool, str]:
        chemin = MODELE_DEEPSEEK if modele == "deepseek" else MODELE_KIMI
        if not chemin.exists():
            return False, f"Fichier introuvable : {chemin.name}"
        try:
            from llama_cpp import Llama
            self.llm = Llama(
                model_path=str(chemin),
                n_ctx=4096,
                n_gpu_layers=16,
                n_threads=8,
                verbose=False,
                chat_format="chatml",
            )
            self.modele_actif = modele
            return True, NOMS_MODELES[modele]
        except ImportError:
            return False, "llama-cpp-python non installé (lance installer.bat)"
        except Exception as e:
            return False, str(e)

    def _construire_messages(self, message: str, nom_utilisateur: str | None = None) -> list[dict]:
        sys_prompt = _lire_systeme_prompt()
        if nom_utilisateur:
            sys_prompt += f"\n\nL'utilisateur s'appelle {nom_utilisateur}."
        messages = [{"role": "system", "content": sys_prompt}]
        for h in self.historique[-8:]:
            messages.append({"role": "user", "content": h["user"]})
            messages.append({"role": "assistant", "content": h["assistant"]})
        messages.append({"role": "user", "content": message})
        return messages

    def repondre(self, message: str, nom_utilisateur: str | None = None) -> str | None:
        if self.llm is None:
            return None
        try:
            res = self.llm.create_chat_completion(
                messages=self._construire_messages(message, nom_utilisateur),
                max_tokens=2048,
                temperature=0.75,
                top_p=0.92,
                repeat_penalty=1.05,
                stop=["<|im_end|>", "</s>", "<|end|>"],
            )
            reponse = res["choices"][0]["message"]["content"].strip()
            reponse = re.sub(r"<think>.*?</think>", "", reponse, flags=re.DOTALL).strip()
            if reponse:
                self.historique.append({"user": message, "assistant": reponse})
            return reponse or None
        except Exception:
            return None

    def repondre_stream(self, message: str, nom_utilisateur: str | None = None):
        """Générateur → yield (phase, contenu).

        Phases :
          'signal'   contenu = 'penser_debut' | 'penser_fin'
          'penser'   contenu = tokens de raisonnement interne (non affichés)
          'repondre' contenu = tokens de la réponse finale
          'done'     contenu = texte complet assemblé
          'erreur'   contenu = message d'erreur
        """
        if self.llm is None:
            yield ("erreur", "LLM non chargé")
            return

        reponse_complete = ""
        try:
            stream = self.llm.create_chat_completion(
                messages=self._construire_messages(message, nom_utilisateur),
                max_tokens=2048,
                temperature=0.75,
                top_p=0.92,
                repeat_penalty=1.05,
                stop=["<|im_end|>", "</s>", "<|end|>"],
                stream=True,
            )

            en_think = False
            tampon = ""

            for chunk in stream:
                delta = chunk["choices"][0]["delta"].get("content", "")
                if not delta:
                    continue
                tampon += delta

                # Drainer le tampon token par token
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

            texte_final = reponse_complete.strip()
            if texte_final:
                self.historique.append({"user": message, "assistant": texte_final})
            yield ("done", texte_final)

        except KeyboardInterrupt:
            yield ("done", reponse_complete.strip())
        except Exception as e:
            yield ("erreur", str(e))

    def vider_historique(self):
        self.historique.clear()

    def stats(self) -> dict:
        return {
            "modele": NOMS_MODELES.get(self.modele_actif, "non chargé"),
            "echanges": len(self.historique),
            "gpu_couches": 16,
        }

    @property
    def actif(self) -> bool:
        return self.llm is not None

    @staticmethod
    def modeles_disponibles() -> dict[str, bool]:
        return {
            "deepseek": MODELE_DEEPSEEK.exists(),
            "kimi": MODELE_KIMI.exists(),
        }
