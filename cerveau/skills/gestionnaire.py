"""
Gestionnaire de skills UNION IA.

Registre des skills intégrés + skills personnalisés (stockés en JSON).
Utilisé par Cerveau.injecter_fichiers() pour transformer les fichiers
attachés en contexte injectab dans le prompt LLM.
"""

import json
from pathlib import Path
from typing import Optional

from cerveau.skills.base import SkillBase, SkillPersonnalise
from cerveau.skills.pdf import SkillPDF
from cerveau.skills.excel import SkillExcel
from cerveau.skills.access import SkillAccess
from cerveau.skills.word import SkillWord

BASE_DIR = Path(__file__).parent.parent.parent
_SKILLS_CUSTOM_PATH = BASE_DIR / "donnees" / "skills_custom.json"

# Skills intégrés, dans l'ordre de priorité
_SKILLS_INTEGRES: list[SkillBase] = [
    SkillPDF(),
    SkillExcel(),
    SkillAccess(),
    SkillWord(),
]


class GestionnaireSkills:
    """Registre et point d'entrée pour tous les skills."""

    def __init__(self, custom_path: Path | None = None):
        self._custom_path = custom_path or _SKILLS_CUSTOM_PATH
        self._skills_custom: list[SkillPersonnalise] = []
        self._charger_custom()

    # ── Chargement skills personnalisés ─────────────────────────────────────

    def _charger_custom(self):
        if not self._custom_path.exists():
            return
        try:
            data = json.loads(self._custom_path.read_text(encoding="utf-8"))
            self._skills_custom = [SkillPersonnalise(cfg) for cfg in data]
        except Exception:
            self._skills_custom = []

    def _sauver_custom(self):
        self._custom_path.parent.mkdir(exist_ok=True)
        configs = [
            {
                "id": s.id, "nom": s.nom, "description": s.description,
                "extensions": s.extensions, "commande": s._commande,
            }
            for s in self._skills_custom
        ]
        self._custom_path.write_text(json.dumps(configs, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── API publique ─────────────────────────────────────────────────────────

    def lister(self) -> list[dict]:
        """Retourne la liste complète des skills disponibles."""
        integres = [
            {
                "id": s.id, "nom": s.nom, "description": s.description,
                "extensions": s.extensions, "type": "integre",
            }
            for s in _SKILLS_INTEGRES
        ]
        custom = [
            {
                "id": s.id, "nom": s.nom, "description": s.description,
                "extensions": s.extensions, "commande": s._commande, "type": "custom",
            }
            for s in self._skills_custom
        ]
        return integres + custom

    def ajouter_custom(self, config: dict) -> dict:
        """Ajoute ou met à jour un skill personnalisé."""
        import uuid
        sid = config.get("id") or f"custom_{uuid.uuid4().hex[:8]}"
        # Mise à jour si l'id existe déjà
        for i, s in enumerate(self._skills_custom):
            if s.id == sid:
                config["id"] = sid
                self._skills_custom[i] = SkillPersonnalise(config)
                self._sauver_custom()
                return {"id": sid}
        config["id"] = sid
        self._skills_custom.append(SkillPersonnalise(config))
        self._sauver_custom()
        return {"id": sid}

    def supprimer_custom(self, skill_id: str) -> bool:
        avant = len(self._skills_custom)
        self._skills_custom = [s for s in self._skills_custom if s.id != skill_id]
        if len(self._skills_custom) < avant:
            self._sauver_custom()
            return True
        return False

    def traiter_fichier(self, chemin: Path) -> Optional[str]:
        """
        Essaie tous les skills sur le fichier.
        Retourne le texte formaté prêt à être injecté, ou None si aucun skill ne sait traiter.
        """
        chemin = Path(chemin)
        if not chemin.exists():
            return None

        tous = list(_SKILLS_INTEGRES) + self._skills_custom
        for skill in tous:
            if skill.peut_traiter(chemin):
                try:
                    contenu = skill.extraire(chemin)
                    return skill.formater(chemin, contenu)
                except Exception as e:
                    return f"\n\n_(Skill {skill.nom} — erreur : {e})_\n"
        return None
