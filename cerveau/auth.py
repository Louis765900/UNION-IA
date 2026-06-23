"""
Authentification UNION IA.

Gestion des comptes utilisateurs, hachage de mots de passe (PBKDF2-SHA256),
tokens de session. Pas de dépendances externes (bibliothèque standard Python).

Le compte admin est créé automatiquement depuis les variables d'environnement
ADMIN_EMAIL / ADMIN_PASSWORD (ou les valeurs par défaut si absentes).
"""

import hashlib
import os
import secrets
import sqlite3
import threading
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DONNEES_DIR = BASE_DIR / "donnees"
AUTH_DB_PATH = DONNEES_DIR / "auth.db"

# Durée de vie d'un token (30 jours)
TOKEN_TTL = 60 * 60 * 24 * 30

ADMIN_EMAIL_DEFAULT = "admin@union-ia.local"
ADMIN_PASSWORD_DEFAULT = "union-ia-admin-2025"


def _hasher(mdp: str, sel: str | None = None) -> tuple[str, str]:
    """Retourne (sel, hash). Si sel=None, en génère un nouveau."""
    if sel is None:
        sel = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", mdp.encode(), sel.encode(), 260_000)
    return sel, h.hex()


def _verifier_mdp(mdp: str, sel: str, hash_stocke: str) -> bool:
    _, h = _hasher(mdp, sel)
    return secrets.compare_digest(h, hash_stocke)


class Auth:
    """Couche d'authentification SQLite."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = Path(db_path) if db_path else AUTH_DB_PATH
        self.db_path.parent.mkdir(exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._creer_schema()
        self._creer_admin()

    def _creer_schema(self):
        with self._lock:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS utilisateurs (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    email       TEXT NOT NULL UNIQUE,
                    sel         TEXT NOT NULL,
                    hash_mdp    TEXT NOT NULL,
                    role        TEXT NOT NULL DEFAULT 'user',
                    nom         TEXT,
                    actif       INTEGER NOT NULL DEFAULT 1,
                    cree_le     REAL NOT NULL,
                    connexion_le REAL
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    token       TEXT PRIMARY KEY,
                    user_id     INTEGER NOT NULL,
                    expire_le   REAL NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES utilisateurs(id) ON DELETE CASCADE
                );
            """)
            self._conn.commit()

    def _creer_admin(self):
        email = os.environ.get("ADMIN_EMAIL", ADMIN_EMAIL_DEFAULT)
        mdp = os.environ.get("ADMIN_PASSWORD", ADMIN_PASSWORD_DEFAULT)
        # Crée le compte admin seulement s'il n'existe pas encore
        with self._lock:
            existe = self._conn.execute(
                "SELECT id FROM utilisateurs WHERE email = ?", (email,)
            ).fetchone()
        if not existe:
            sel, h = _hasher(mdp)
            with self._lock:
                self._conn.execute(
                    "INSERT INTO utilisateurs (email, sel, hash_mdp, role, nom, cree_le) "
                    "VALUES (?, ?, ?, 'admin', 'Admin', ?)",
                    (email, sel, h, time.time()),
                )
                self._conn.commit()

    # ── Gestion des utilisateurs ─────────────────────────────────────────────

    def creer_compte(self, email: str, mdp: str, nom: str = "") -> dict:
        """Crée un compte utilisateur. Lève ValueError si email déjà pris."""
        email = email.strip().lower()
        if not email or "@" not in email:
            raise ValueError("Email invalide")
        if len(mdp) < 6:
            raise ValueError("Mot de passe trop court (6 caractères minimum)")
        sel, h = _hasher(mdp)
        try:
            with self._lock:
                cur = self._conn.execute(
                    "INSERT INTO utilisateurs (email, sel, hash_mdp, nom, cree_le) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (email, sel, h, nom.strip()[:80], time.time()),
                )
                self._conn.commit()
                return {"id": cur.lastrowid, "email": email, "role": "user"}
        except sqlite3.IntegrityError:
            raise ValueError("Cet email est déjà utilisé")

    def connecter(self, email: str, mdp: str) -> str | None:
        """Vérifie les identifiants et retourne un token de session, ou None."""
        email = email.strip().lower()
        with self._lock:
            row = self._conn.execute(
                "SELECT id, sel, hash_mdp, actif FROM utilisateurs WHERE email = ?",
                (email,)
            ).fetchone()
        if not row or not row["actif"]:
            return None
        if not _verifier_mdp(mdp, row["sel"], row["hash_mdp"]):
            return None
        token = secrets.token_urlsafe(32)
        expire = time.time() + TOKEN_TTL
        with self._lock:
            self._conn.execute(
                "INSERT INTO sessions (token, user_id, expire_le) VALUES (?, ?, ?)",
                (token, row["id"], expire),
            )
            self._conn.execute(
                "UPDATE utilisateurs SET connexion_le = ? WHERE id = ?",
                (time.time(), row["id"]),
            )
            self._conn.commit()
        return token

    def valider_token(self, token: str) -> dict | None:
        """Retourne le profil utilisateur si le token est valide, sinon None."""
        if not token:
            return None
        with self._lock:
            row = self._conn.execute(
                "SELECT s.user_id, s.expire_le, u.email, u.role, u.nom, u.actif "
                "FROM sessions s JOIN utilisateurs u ON u.id = s.user_id "
                "WHERE s.token = ?",
                (token,),
            ).fetchone()
        if not row:
            return None
        if time.time() > row["expire_le"]:
            self.deconnecter(token)
            return None
        if not row["actif"]:
            return None
        return {
            "id": row["user_id"],
            "email": row["email"],
            "role": row["role"],
            "nom": row["nom"] or "",
        }

    def deconnecter(self, token: str):
        with self._lock:
            self._conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
            self._conn.commit()

    def lister_utilisateurs(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, email, role, nom, actif, cree_le, connexion_le "
                "FROM utilisateurs ORDER BY cree_le DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def supprimer_utilisateur(self, user_id: int):
        with self._lock:
            self._conn.execute("DELETE FROM utilisateurs WHERE id = ?", (user_id,))
            self._conn.commit()

    def changer_role(self, user_id: int, role: str):
        if role not in ("user", "admin"):
            raise ValueError("Rôle invalide")
        with self._lock:
            self._conn.execute(
                "UPDATE utilisateurs SET role = ? WHERE id = ?", (role, user_id)
            )
            self._conn.commit()

    def changer_mot_de_passe(self, user_id: int, ancien: str, nouveau: str):
        """Vérifie l'ancien mot de passe et remplace par le nouveau."""
        with self._lock:
            row = self._conn.execute(
                "SELECT sel, hash_mdp FROM utilisateurs WHERE id = ?", (user_id,)
            ).fetchone()
        if not row:
            raise ValueError("Utilisateur introuvable")
        if not _verifier_mdp(ancien, row["sel"], row["hash_mdp"]):
            raise ValueError("Mot de passe actuel incorrect")
        if len(nouveau) < 8:
            raise ValueError("Le nouveau mot de passe doit faire au moins 8 caractères")
        sel, h = _hasher(nouveau)
        with self._lock:
            self._conn.execute(
                "UPDATE utilisateurs SET sel = ?, hash_mdp = ? WHERE id = ?",
                (sel, h, user_id),
            )
            # Invalide toutes les sessions existantes (force reconnexion)
            self._conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            self._conn.commit()

    def nettoyer_sessions_expirees(self):
        with self._lock:
            self._conn.execute(
                "DELETE FROM sessions WHERE expire_le < ?", (time.time(),)
            )
            self._conn.commit()

    def fermer(self):
        with self._lock:
            self._conn.close()
