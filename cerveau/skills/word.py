"""Skill Word — extrait le texte d'un fichier .docx / .odt."""

from pathlib import Path
from cerveau.skills.base import SkillBase


class SkillWord(SkillBase):
    id = "word"
    nom = "Word/Document"
    description = "Extrait le texte d'un document Word (.docx) ou LibreOffice (.odt)"
    extensions = ["docx", "odt", "doc"]

    def peut_traiter(self, chemin: Path) -> bool:
        return chemin.suffix.lower().lstrip(".") in self.extensions

    def extraire(self, chemin: Path) -> str:
        ext = chemin.suffix.lower()
        if ext in (".docx",):
            return self._extraire_docx(chemin)
        if ext in (".odt",):
            return self._extraire_odt(chemin)
        raise ValueError(f"Format {ext} non supporté (utilise .docx ou .odt)")

    def _extraire_docx(self, chemin: Path) -> str:
        try:
            import docx
            doc = docx.Document(str(chemin))
            paragraphes = [p.text for p in doc.paragraphs if p.text.strip()]
            return "\n\n".join(paragraphes[:300])
        except ImportError:
            raise ValueError("python-docx non installé. Lance : pip install python-docx")
        except Exception as e:
            raise ValueError(f"Erreur lecture DOCX : {e}")

    def _extraire_odt(self, chemin: Path) -> str:
        try:
            from odf import text as odf_text, teletype
            from odf.opendocument import load
            doc = load(str(chemin))
            paragraphes = []
            for el in doc.body.getElementsByType(odf_text.P):
                t = teletype.extractText(el)
                if t.strip():
                    paragraphes.append(t)
            return "\n\n".join(paragraphes[:300])
        except ImportError:
            raise ValueError("odfpy non installé. Lance : pip install odfpy")
        except Exception as e:
            raise ValueError(f"Erreur lecture ODT : {e}")

    def formater(self, chemin: Path, contenu: str) -> str:
        return f"\n\n**Document `{chemin.name}` :**\n```\n{contenu[:6000]}\n```\n"
