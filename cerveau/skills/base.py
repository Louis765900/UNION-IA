"""Classe de base pour tous les skills UNION IA."""

from abc import ABC, abstractmethod
from pathlib import Path


class SkillBase(ABC):
    """Un skill transforme un fichier (ou autre entrée) en texte injectab dans le contexte LLM."""

    id: str = ""
    nom: str = ""
    description: str = ""
    extensions: list[str] = []

    @abstractmethod
    def peut_traiter(self, chemin: Path) -> bool:
        """Retourne True si ce skill sait traiter le fichier donné."""

    @abstractmethod
    def extraire(self, chemin: Path) -> str:
        """Extrait le contenu textuel du fichier. Lève ValueError en cas d'erreur."""

    def formater(self, chemin: Path, contenu: str) -> str:
        """Formate le contenu extrait pour injection dans le contexte LLM."""
        return f"\n\n**Fichier `{chemin.name}` ({self.nom}) :**\n{contenu}\n"


class SkillPersonnalise(SkillBase):
    """Skill défini par l'utilisateur : exécute une commande shell et capture la sortie."""

    def __init__(self, config: dict):
        self.id = config.get("id", "")
        self.nom = config.get("nom", "Skill personnalisé")
        self.description = config.get("description", "")
        self.extensions = config.get("extensions", [])
        self._commande = config.get("commande", "")

    def peut_traiter(self, chemin: Path) -> bool:
        if not self.extensions:
            return False
        return chemin.suffix.lower().lstrip(".") in [e.lstrip(".") for e in self.extensions]

    def extraire(self, chemin: Path) -> str:
        import subprocess, shlex
        if not self._commande:
            raise ValueError("Commande non définie pour ce skill personnalisé")
        cmd = self._commande.replace("{fichier}", str(chemin))
        try:
            result = subprocess.run(
                shlex.split(cmd),
                capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0 and result.stderr:
                raise ValueError(result.stderr[:500])
            return result.stdout
        except subprocess.TimeoutExpired:
            raise ValueError("Timeout lors de l'exécution du skill")
