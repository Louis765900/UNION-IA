import re
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table
from rich.rule import Rule
from rich.live import Live
from rich.markdown import Markdown
from rich import box
import time

console = Console()

LOGO = r"""
 _   _ _   _ ___ ___  _   _   ___    _
| | | | \ | |_ _/ _ \| \ | | |_ _|  / \
| | | |  \| || | | | |  \| |  | |  / _ \
| |_| | |\  || | |_| | |\  |  | | / ___ \
 \___/|_| \_|___\___/|_| \_| |___/_/   \_\
"""

COULEURS = {
    "primaire": "bright_cyan",
    "secondaire": "bright_blue",
    "accent": "bright_magenta",
    "succes": "bright_green",
    "erreur": "bright_red",
    "avertissement": "yellow",
    "texte": "white",
    "dim": "dim white",
}


def afficher_intro(llm_actif: bool = False, nom_modele: str = "réseau neuronal", nom_utilisateur: str | None = None):
    console.clear()
    console.print(f"[bold {COULEURS['accent']}]{LOGO}[/]", justify="center")
    console.print(Rule(f"[{COULEURS['primaire']}]Ton IA personnelle — 100% locale[/]"))
    console.print()

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    table.add_column("Clé", style=COULEURS["dim"], width=18)
    table.add_column("Valeur", style=COULEURS["texte"])

    if nom_utilisateur:
        table.add_row("Utilisateur", f"[{COULEURS['accent']}]{nom_utilisateur}[/]")
    table.add_row("Modèle IA", f"[{COULEURS['succes' if llm_actif else 'avertissement']}]{nom_modele}[/]")
    table.add_row("GPU", "[bright_cyan]GTX 1650 — Vulkan (16 couches)[/]" if llm_actif else "[dim]CPU[/]")
    table.add_row("Mode", "[bright_green]Hybride (rapide + LLM)[/]" if llm_actif else "[yellow]Réseau neuronal seul[/]")
    table.add_row("Astuce", "[dim]@fichier.py pour inclure un fichier · \\ pour multi-ligne[/]")
    table.add_row("Commandes", "[dim]/aide  /stats  /historique  /oublier[/]")

    console.print(Panel(table, title=f"[bold {COULEURS['primaire']}]UNION IA[/]", border_style=COULEURS["secondaire"]))
    console.print()


def afficher_chargement_llm(nom_modele: str):
    console.print(f"[{COULEURS['avertissement']}]Chargement de {nom_modele}...[/]")
    with Progress(
        SpinnerColumn(style=COULEURS["accent"]),
        TextColumn(f"[{COULEURS['texte']}]{{task.description}}"),
        BarColumn(complete_style=COULEURS["succes"], finished_style=COULEURS["succes"]),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        t = progress.add_task(f"Initialisation {nom_modele}", total=100)
        for i in range(100):
            time.sleep(0.03)
            progress.update(t, advance=1)


def afficher_chargement_llm_ok(nom_modele: str):
    console.print(f"[{COULEURS['succes']}]✓ {nom_modele} chargé — GTX 1650 Vulkan (16 couches)[/]")
    console.print()


def afficher_chargement_llm_echec(raison: str):
    console.print(Panel(
        f"[{COULEURS['erreur']}]Impossible de charger le LLM :[/]\n{raison}\n\n"
        f"[{COULEURS['dim']}]UNION IA fonctionne en mode réseau neuronal.[/]",
        border_style=COULEURS["erreur"],
        title="[bold red]LLM non disponible[/]"
    ))
    console.print()


def afficher_entrainement():
    console.print(f"[{COULEURS['avertissement']}]Premier lancement — entraînement du réseau neuronal...[/]")
    with Progress(
        SpinnerColumn(style=COULEURS["accent"]),
        TextColumn(f"[{COULEURS['texte']}]{{task.description}}"),
        BarColumn(complete_style=COULEURS["succes"]),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        t = progress.add_task("Entraînement en cours...", total=100)
        for i in range(100):
            time.sleep(0.04)
            progress.update(t, advance=1)


def afficher_entrainement_ok():
    console.print(f"[{COULEURS['succes']}]✓ Réseau neuronal entraîné et prêt.[/]")
    console.print()


def _label_source(source: str) -> str:
    return {
        "ia":  f"[bold {COULEURS['accent']}]UNION IA[/]",
        "llm": f"[bold {COULEURS['accent']}]UNION IA[/] [dim](DeepSeek R1)[/]",
        "kimi": f"[bold {COULEURS['accent']}]UNION IA[/] [dim](Kimi K2)[/]",
        "sys": f"[{COULEURS['avertissement']}]Système[/]",
    }.get(source, f"[bold {COULEURS['accent']}]UNION IA[/]")


def afficher_message_ia(message: str, source: str = "ia", confiance: float | None = None):
    try:
        contenu = Markdown(message)
    except Exception:
        contenu = Text(message)

    subtitle = None
    if confiance is not None:
        barre = "█" * int(confiance * 10) + "░" * (10 - int(confiance * 10))
        subtitle = f"[dim]confiance {barre} {confiance:.0%}[/dim]"

    console.print(Panel(
        contenu,
        title=_label_source(source),
        subtitle=subtitle,
        border_style=COULEURS["secondaire"],
        padding=(0, 1),
    ))


def afficher_reponse_stream(generateur, source: str = "llm") -> str:
    """Affiche la réponse LLM en streaming avec rendu markdown final.
    Retourne le texte complet généré.
    """
    label = _label_source(source)
    texte_complet = ""
    nb_penser = [0]
    en_reflexion = [False]

    def _panneau_courant() -> Panel:
        if en_reflexion[0]:
            return Panel(
                Text(f"  Réflexion... ({nb_penser[0]} tokens traités)", style="dim italic"),
                title=label,
                border_style="dim",
                padding=(0, 1),
            )
        if texte_complet:
            return Panel(
                Text(texte_complet, overflow="fold"),
                title=label,
                border_style=COULEURS["secondaire"],
                padding=(0, 1),
            )
        return Panel(
            Text("  Génération...", style="dim italic"),
            title=label,
            border_style="dim",
            padding=(0, 1),
        )

    try:
        with Live(console=console, refresh_per_second=20, transient=True) as live:
            live.update(_panneau_courant())
            for phase, contenu in generateur:
                if phase == "signal":
                    if contenu == "penser_debut":
                        en_reflexion[0] = True
                    elif contenu == "penser_fin":
                        en_reflexion[0] = False
                elif phase == "penser":
                    nb_penser[0] += len(contenu)
                elif phase == "repondre":
                    texte_complet += contenu
                elif phase in ("done", "erreur"):
                    break
                live.update(_panneau_courant())
    except KeyboardInterrupt:
        console.print(f"\n[{COULEURS['dim']}]Génération interrompue.[/]")

    # Rendu final markdown
    if texte_complet.strip():
        try:
            rendu = Markdown(texte_complet.strip())
        except Exception:
            rendu = Text(texte_complet.strip())
        console.print(Panel(
            rendu,
            title=label,
            border_style=COULEURS["secondaire"],
            padding=(0, 1),
        ))
    elif not texte_complet:
        console.print(Panel(
            Text("Aucune réponse générée.", style=COULEURS["dim"]),
            title=label,
            border_style=COULEURS["erreur"],
            padding=(0, 1),
        ))

    return texte_complet.strip()


def afficher_fichiers_injectes(fichiers: list[str]):
    """Affiche un indicateur des fichiers injectés dans le contexte."""
    if not fichiers:
        return
    noms = ", ".join(f"[{COULEURS['accent']}]{f}[/]" for f in fichiers)
    console.print(f"[{COULEURS['dim']}]  @[/] Contexte enrichi : {noms}")


def obtenir_input(nom: str | None = None) -> str:
    """Saisie avec support multi-ligne (backslash en fin de ligne) et @fichier."""
    label = f"[bold {COULEURS['succes']}]{nom or 'Toi'}[/]"
    console.print(f"\n{label} › ", end="")
    try:
        ligne = input()
    except (EOFError, KeyboardInterrupt):
        return "/quitter"

    # Multi-ligne : \ en fin de ligne = continuation
    lignes = [ligne.rstrip("\\") if ligne.endswith("\\") else ligne]
    while ligne.endswith("\\"):
        console.print(f"[{COULEURS['dim']}]  ... › [/]", end="")
        try:
            ligne = input()
        except (EOFError, KeyboardInterrupt):
            break
        lignes.append(ligne.rstrip("\\") if ligne.endswith("\\") else ligne)

    return "\n".join(lignes)


def afficher_au_revoir(nom: str | None = None):
    msg = f"À bientôt{', ' + nom + ' !' if nom else ' !'}"
    console.print()
    console.print(Panel(
        f"[bold {COULEURS['accent']}]{msg}[/]",
        border_style=COULEURS["primaire"],
    ))
