"""
Couche de stockage persistant de UNION IA (SQLite).

Remplace les anciens fichiers JSON (memoire.json, apprentissage.json) par une
base de données unique et thread-safe. Gère :
  - les conversations et leurs messages (historique inter-sessions)
  - les faits mémorisés sur l'utilisateur (mémoire active)
  - le profil et les préférences (nom, réglages d'interface)
  - les apprentissages personnalisés (« quand on dit X, tu réponds Y »)

La base est créée automatiquement dans donnees/union_ia.db.
"""

import json
import sqlite3
import threading
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DONNEES_DIR = BASE_DIR / "donnees"
DB_PATH = DONNEES_DIR / "union_ia.db"

# Anciens fichiers JSON — migrés automatiquement à la première ouverture
_ANCIEN_MEMOIRE = DONNEES_DIR / "memoire.json"
_ANCIEN_APPRENTISSAGE = DONNEES_DIR / "apprentissage.json"


def _maintenant() -> float:
    return time.time()


class Stockage:
    """Accès thread-safe à la base SQLite de UNION IA."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._creer_schema()
        self._migrer_json()

    # ── Schéma ───────────────────────────────────────────────────────────────

    def _creer_schema(self):
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    titre       TEXT NOT NULL DEFAULT 'Nouvelle conversation',
                    cree_le     REAL NOT NULL,
                    maj_le      REAL NOT NULL,
                    archive     INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER NOT NULL,
                    role            TEXT NOT NULL,
                    contenu         TEXT NOT NULL,
                    modele          TEXT,
                    cree_le         REAL NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id);

                CREATE TABLE IF NOT EXISTS faits_memoire (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    cle         TEXT NOT NULL UNIQUE,
                    valeur      TEXT NOT NULL,
                    categorie   TEXT NOT NULL DEFAULT 'general',
                    source      TEXT,
                    cree_le     REAL NOT NULL,
                    maj_le      REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS profil (
                    cle     TEXT PRIMARY KEY,
                    valeur  TEXT
                );

                CREATE TABLE IF NOT EXISTS apprentissages (
                    cle      TEXT PRIMARY KEY,
                    reponse  TEXT NOT NULL,
                    cree_le  REAL NOT NULL
                );
                """
            )
            self._conn.commit()

    # ── Migration depuis les anciens JSON ────────────────────────────────────

    def _migrer_json(self):
        # Mémoire (nom, compteurs)
        if _ANCIEN_MEMOIRE.exists() and not self.profil_get("_migre_memoire"):
            try:
                data = json.loads(_ANCIEN_MEMOIRE.read_text(encoding="utf-8"))
                if data.get("nom_utilisateur"):
                    self.profil_set("nom_utilisateur", data["nom_utilisateur"])
                self.profil_set("total_messages", str(data.get("total_messages", 0)))
                self.profil_set("total_sessions", str(data.get("total_sessions", 0)))
                self.profil_set("_migre_memoire", "1")
            except Exception:
                pass

        # Apprentissages
        if _ANCIEN_APPRENTISSAGE.exists() and not self.profil_get("_migre_appr"):
            try:
                data = json.loads(_ANCIEN_APPRENTISSAGE.read_text(encoding="utf-8"))
                for cle, reponse in data.items():
                    self.apprentissage_set(cle, reponse)
                self.profil_set("_migre_appr", "1")
            except Exception:
                pass

    # ── Profil (clé-valeur) ──────────────────────────────────────────────────

    def profil_get(self, cle: str, defaut=None):
        with self._lock:
            row = self._conn.execute(
                "SELECT valeur FROM profil WHERE cle = ?", (cle,)
            ).fetchone()
        return row["valeur"] if row else defaut

    def profil_set(self, cle: str, valeur: str):
        with self._lock:
            self._conn.execute(
                "INSERT INTO profil (cle, valeur) VALUES (?, ?) "
                "ON CONFLICT(cle) DO UPDATE SET valeur = excluded.valeur",
                (cle, str(valeur)),
            )
            self._conn.commit()

    def profil_tout(self) -> dict:
        with self._lock:
            rows = self._conn.execute("SELECT cle, valeur FROM profil").fetchall()
        return {r["cle"]: r["valeur"] for r in rows if not r["cle"].startswith("_")}

    def incrementer(self, cle: str, n: int = 1) -> int:
        actuel = int(self.profil_get(cle, "0") or "0")
        nouveau = actuel + n
        self.profil_set(cle, str(nouveau))
        return nouveau

    # ── Conversations ────────────────────────────────────────────────────────

    def creer_conversation(self, titre: str = "Nouvelle conversation") -> int:
        t = _maintenant()
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO conversations (titre, cree_le, maj_le) VALUES (?, ?, ?)",
                (titre[:120], t, t),
            )
            self._conn.commit()
            return cur.lastrowid

    def renommer_conversation(self, conv_id: int, titre: str):
        with self._lock:
            self._conn.execute(
                "UPDATE conversations SET titre = ?, maj_le = ? WHERE id = ?",
                (titre[:120], _maintenant(), conv_id),
            )
            self._conn.commit()

    def supprimer_conversation(self, conv_id: int):
        with self._lock:
            self._conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
            self._conn.commit()

    def lister_conversations(self, limite: int = 100) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT c.id, c.titre, c.cree_le, c.maj_le, "
                "(SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) AS nb "
                "FROM conversations c WHERE c.archive = 0 "
                "ORDER BY c.maj_le DESC LIMIT ?",
                (limite,),
            ).fetchall()
        return [dict(r) for r in rows]

    def conversation_existe(self, conv_id: int) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM conversations WHERE id = ?", (conv_id,)
            ).fetchone()
        return row is not None

    # ── Messages ─────────────────────────────────────────────────────────────

    def ajouter_message(self, conv_id: int, role: str, contenu: str,
                        modele: str | None = None) -> int:
        t = _maintenant()
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO messages (conversation_id, role, contenu, modele, cree_le) "
                "VALUES (?, ?, ?, ?, ?)",
                (conv_id, role, contenu, modele, t),
            )
            self._conn.execute(
                "UPDATE conversations SET maj_le = ? WHERE id = ?", (t, conv_id)
            )
            self._conn.commit()
            return cur.lastrowid

    def lister_messages(self, conv_id: int, limite: int = 500) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, role, contenu, modele, cree_le FROM messages "
                "WHERE conversation_id = ? ORDER BY id ASC LIMIT ?",
                (conv_id, limite),
            ).fetchall()
        return [dict(r) for r in rows]

    def rechercher_messages(self, requete: str, limite: int = 40) -> list[dict]:
        """Recherche plein-texte simple dans tous les messages."""
        motif = f"%{requete.strip()}%"
        with self._lock:
            rows = self._conn.execute(
                "SELECT m.conversation_id, c.titre, m.role, m.contenu, m.cree_le "
                "FROM messages m JOIN conversations c ON c.id = m.conversation_id "
                "WHERE m.contenu LIKE ? ORDER BY m.cree_le DESC LIMIT ?",
                (motif, limite),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Faits mémorisés (mémoire active) ─────────────────────────────────────

    def memoriser_fait(self, cle: str, valeur: str, categorie: str = "general",
                      source: str | None = None):
        t = _maintenant()
        with self._lock:
            self._conn.execute(
                "INSERT INTO faits_memoire (cle, valeur, categorie, source, cree_le, maj_le) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(cle) DO UPDATE SET valeur = excluded.valeur, "
                "categorie = excluded.categorie, maj_le = excluded.maj_le",
                (cle, valeur, categorie, source, t, t),
            )
            self._conn.commit()

    def lister_faits(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, cle, valeur, categorie, source, cree_le, maj_le "
                "FROM faits_memoire ORDER BY maj_le DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def oublier_fait(self, cle: str):
        with self._lock:
            self._conn.execute("DELETE FROM faits_memoire WHERE cle = ?", (cle,))
            self._conn.commit()

    def vider_faits(self):
        with self._lock:
            self._conn.execute("DELETE FROM faits_memoire")
            self._conn.commit()

    def faits_resume(self, limite: int = 30) -> str:
        """Retourne les faits mémorisés sous forme de texte pour le contexte LLM."""
        faits = self.lister_faits()[:limite]
        if not faits:
            return ""
        lignes = [f"- {f['valeur']}" for f in faits]
        return "\n".join(lignes)

    # ── Apprentissages ───────────────────────────────────────────────────────

    def apprentissage_set(self, cle: str, reponse: str):
        with self._lock:
            self._conn.execute(
                "INSERT INTO apprentissages (cle, reponse, cree_le) VALUES (?, ?, ?) "
                "ON CONFLICT(cle) DO UPDATE SET reponse = excluded.reponse",
                (cle.lower().strip(), reponse, _maintenant()),
            )
            self._conn.commit()

    def apprentissages_tout(self) -> dict:
        with self._lock:
            rows = self._conn.execute(
                "SELECT cle, reponse FROM apprentissages"
            ).fetchall()
        return {r["cle"]: r["reponse"] for r in rows}

    def oublier_apprentissage(self, cle: str):
        with self._lock:
            self._conn.execute(
                "DELETE FROM apprentissages WHERE cle = ?", (cle.lower().strip(),)
            )
            self._conn.commit()

    # ── Maintenance ──────────────────────────────────────────────────────────

    def fermer(self):
        with self._lock:
            self._conn.close()
