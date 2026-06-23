"""Skill Access/base de données — lit les tables d'un fichier .accdb/.mdb ou SQLite."""

from pathlib import Path
from cerveau.skills.base import SkillBase


class SkillAccess(SkillBase):
    id = "access"
    nom = "Base de données"
    description = "Lit les tables d'un fichier Access (.accdb, .mdb) ou SQLite (.db, .sqlite)"
    extensions = ["accdb", "mdb", "db", "sqlite", "sqlite3"]

    def peut_traiter(self, chemin: Path) -> bool:
        return chemin.suffix.lower().lstrip(".") in self.extensions

    def extraire(self, chemin: Path) -> str:
        ext = chemin.suffix.lower()
        if ext in (".db", ".sqlite", ".sqlite3"):
            return self._extraire_sqlite(chemin)
        return self._extraire_access(chemin)

    def _extraire_sqlite(self, chemin: Path) -> str:
        import sqlite3
        try:
            conn = sqlite3.connect(str(chemin))
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            blocs = []
            for (table,) in tables[:10]:
                rows = conn.execute(f"SELECT * FROM \"{table}\" LIMIT 20").fetchall()
                desc = conn.execute(f"PRAGMA table_info(\"{table}\")").fetchall()
                colonnes = [d[1] for d in desc]
                lignes = [f"### Table : {table}"]
                lignes.append(" | ".join(colonnes))
                lignes.append(" | ".join(["---"] * len(colonnes)))
                for row in rows:
                    lignes.append(" | ".join(str(v) if v is not None else "" for v in row))
                blocs.append("\n".join(lignes))
            conn.close()
            return "\n\n".join(blocs) if blocs else "Base de données vide."
        except Exception as e:
            raise ValueError(f"Erreur lecture SQLite : {e}")

    def _extraire_access(self, chemin: Path) -> str:
        try:
            import pyodbc
            conn_str = (
                f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};"
                f"DBQ={chemin};"
            )
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()
            tables = [row.table_name for row in cursor.tables(tableType="TABLE")]
            blocs = []
            for table in tables[:10]:
                lignes_md = [f"### Table : {table}"]
                try:
                    rows = cursor.execute(f"SELECT TOP 20 * FROM [{table}]").fetchall()
                    colonnes = [d[0] for d in cursor.description]
                    lignes_md.append(" | ".join(colonnes))
                    lignes_md.append(" | ".join(["---"] * len(colonnes)))
                    for row in rows:
                        lignes_md.append(" | ".join(str(v) if v is not None else "" for v in row))
                except Exception:
                    lignes_md.append("_(table inaccessible)_")
                blocs.append("\n".join(lignes_md))
            conn.close()
            return "\n\n".join(blocs) if blocs else "Base Access vide."
        except ImportError:
            raise ValueError(
                "pyodbc non installé ou pilote Access absent.\n"
                "Installe : pip install pyodbc\n"
                "Et le pilote Microsoft Access Database Engine."
            )
        except Exception as e:
            raise ValueError(f"Erreur lecture Access : {e}")

    def formater(self, chemin: Path, contenu: str) -> str:
        return f"\n\n**Base de données `{chemin.name}` :**\n{contenu}\n"
