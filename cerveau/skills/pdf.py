"""Skill PDF — extrait le texte d'un fichier PDF."""

from pathlib import Path
from cerveau.skills.base import SkillBase


class SkillPDF(SkillBase):
    id = "pdf"
    nom = "PDF"
    description = "Extrait le texte d'un fichier PDF"
    extensions = ["pdf"]

    def peut_traiter(self, chemin: Path) -> bool:
        return chemin.suffix.lower() == ".pdf"

    def extraire(self, chemin: Path) -> str:
        # Essaie pypdf d'abord (léger), puis pdfplumber (plus robuste)
        texte = self._via_pypdf(chemin)
        if not texte or len(texte) < 20:
            texte = self._via_pdfplumber(chemin)
        if not texte:
            raise ValueError("Impossible d'extraire le texte de ce PDF")
        return texte

    def _via_pypdf(self, chemin: Path) -> str:
        try:
            import pypdf
            reader = pypdf.PdfReader(str(chemin))
            pages = []
            for i, page in enumerate(reader.pages[:50]):  # max 50 pages
                t = page.extract_text() or ""
                if t.strip():
                    pages.append(f"[Page {i+1}]\n{t.strip()}")
            return "\n\n".join(pages)
        except ImportError:
            return ""
        except Exception as e:
            return ""

    def _via_pdfplumber(self, chemin: Path) -> str:
        try:
            import pdfplumber
            pages = []
            with pdfplumber.open(str(chemin)) as pdf:
                for i, page in enumerate(pdf.pages[:50]):
                    t = page.extract_text() or ""
                    if t.strip():
                        pages.append(f"[Page {i+1}]\n{t.strip()}")
            return "\n\n".join(pages)
        except ImportError:
            return ""
        except Exception:
            return ""

    def formater(self, chemin: Path, contenu: str) -> str:
        nb_cars = len(contenu)
        return (
            f"\n\n**Fichier PDF `{chemin.name}` ({nb_cars} caractères extraits) :**\n"
            f"```\n{contenu[:8000]}\n```\n"
            + (f"\n_(contenu tronqué — {nb_cars} caractères au total)_\n" if nb_cars > 8000 else "")
        )
