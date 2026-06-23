"""Skill Excel/CSV — extrait les données d'un fichier tableur."""

from pathlib import Path
from cerveau.skills.base import SkillBase


class SkillExcel(SkillBase):
    id = "excel"
    nom = "Excel/CSV"
    description = "Extrait les données d'un fichier Excel (.xlsx, .xls) ou CSV"
    extensions = ["xlsx", "xls", "csv", "tsv", "ods"]

    def peut_traiter(self, chemin: Path) -> bool:
        return chemin.suffix.lower().lstrip(".") in self.extensions

    def extraire(self, chemin: Path) -> str:
        ext = chemin.suffix.lower()
        if ext in (".csv", ".tsv"):
            return self._extraire_csv(chemin)
        return self._extraire_excel(chemin)

    def _extraire_csv(self, chemin: Path) -> str:
        import csv
        sep = "\t" if chemin.suffix.lower() == ".tsv" else None
        try:
            with open(chemin, encoding="utf-8-sig", errors="replace") as f:
                sample = f.read(4096)
                f.seek(0)
                if sep is None:
                    sep = csv.Sniffer().sniff(sample).delimiter
                reader = csv.reader(f, delimiter=sep)
                rows = list(reader)
        except Exception as e:
            raise ValueError(f"Erreur lecture CSV : {e}")

        if not rows:
            return "Fichier CSV vide."

        # Affiche en tableau Markdown
        lignes = []
        entete = rows[0]
        lignes.append(" | ".join(str(c) for c in entete))
        lignes.append(" | ".join(["---"] * len(entete)))
        for row in rows[1:101]:  # max 100 lignes
            lignes.append(" | ".join(str(c) for c in row))
        if len(rows) > 102:
            lignes.append(f"\n_(… {len(rows) - 101} lignes supplémentaires non affichées)_")
        return "\n".join(lignes)

    def _extraire_excel(self, chemin: Path) -> str:
        try:
            import openpyxl
            wb = openpyxl.load_workbook(str(chemin), read_only=True, data_only=True)
            blocs = []
            for sheet_name in wb.sheetnames[:5]:  # max 5 feuilles
                ws = wb[sheet_name]
                rows = list(ws.iter_rows(max_row=101, values_only=True))
                if not rows:
                    continue
                entete = [str(c) if c is not None else "" for c in rows[0]]
                lignes = [f"### Feuille : {sheet_name}"]
                lignes.append(" | ".join(entete))
                lignes.append(" | ".join(["---"] * len(entete)))
                for row in rows[1:101]:
                    lignes.append(" | ".join(str(c) if c is not None else "" for c in row))
                blocs.append("\n".join(lignes))
            wb.close()
            return "\n\n".join(blocs) if blocs else "Fichier Excel vide."
        except ImportError:
            raise ValueError("openpyxl non installé. Lance : pip install openpyxl")
        except Exception as e:
            raise ValueError(f"Erreur lecture Excel : {e}")

    def formater(self, chemin: Path, contenu: str) -> str:
        return f"\n\n**Fichier `{chemin.name}` :**\n{contenu}\n"
