import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

from cerveau.entraineur import Entraineur
from cerveau.cerveau import Cerveau
from cerveau.llm_cerveau import LLMCerveau
from interface.terminal import (
    afficher_intro,
    afficher_entrainement,
    afficher_entrainement_ok,
    afficher_chargement_llm,
    afficher_chargement_llm_ok,
    afficher_chargement_llm_echec,
    afficher_message_ia,
    afficher_reponse_stream,
    afficher_fichiers_injectes,
    obtenir_input,
    afficher_au_revoir,
)


def main():
    # ── 1. Entraînement / chargement du réseau neuronal ──────────────────────
    entraineur = Entraineur()

    if not entraineur._modele_existe():
        afficher_entrainement()
        entraineur.entrainer(force=True)
        afficher_entrainement_ok()
    else:
        entraineur.entrainer(force=False)

    # ── 2. Cerveau principal ──────────────────────────────────────────────────
    cerveau = Cerveau(entraineur)

    # ── 3. Chargement du LLM ─────────────────────────────────────────────────
    modeles_dispo = LLMCerveau.modeles_disponibles()
    llm_ok = False
    nom_modele = "Réseau neuronal seul"

    # Le backend est auto-détecté dans LLMCerveau.__init__ via .env
    if cerveau.llm.actif:
        llm_ok = True
        nom_modele = cerveau.llm.stats().get("modele", "UNION IA")
    elif modeles_dispo.get("deepseek-local"):
        afficher_chargement_llm("DeepSeek R1 local")
        ok, msg = cerveau.charger_llm("deepseek")
        if ok:
            llm_ok, nom_modele = True, msg
            afficher_chargement_llm_ok(msg)
        else:
            afficher_chargement_llm_echec(msg)
    elif modeles_dispo.get("kimi-local"):
        afficher_chargement_llm("Kimi K2 local")
        ok, msg = cerveau.charger_llm("kimi")
        if ok:
            llm_ok, nom_modele = True, msg
            afficher_chargement_llm_ok(msg)
        else:
            afficher_chargement_llm_echec(msg)

    # ── 4. Interface d'accueil ────────────────────────────────────────────────
    afficher_intro(
        llm_actif=llm_ok,
        nom_modele=nom_modele,
        nom_utilisateur=cerveau.nom_utilisateur,
    )

    # ── 5. Boucle principale ──────────────────────────────────────────────────
    while True:
        try:
            texte = obtenir_input(nom=cerveau.nom_utilisateur)
        except (KeyboardInterrupt, EOFError):
            break

        if not texte.strip():
            continue

        # Injecter les @fichiers avant tout traitement
        texte_llm, fichiers_injectes = cerveau.injecter_fichiers(texte)
        if fichiers_injectes:
            afficher_fichiers_injectes(fichiers_injectes)

        # Chemin streaming : LLM actif + requête de connaissance
        if cerveau.llm.actif and cerveau.besoin_llm(texte):
            reponse = afficher_reponse_stream(
                cerveau.llm.repondre_stream(texte_llm, nom_utilisateur=cerveau.nom_utilisateur),
                source="llm",
            )
            if reponse:
                cerveau.enregistrer_echange_llm(texte, reponse)
            continue

        # Chemin instantané : réseau neuronal / commandes / apprentissage
        reponse, quitter = cerveau.repondre(texte)
        afficher_message_ia(reponse, source="ia")

        if quitter:
            afficher_au_revoir(nom=cerveau.nom_utilisateur)
            break


if __name__ == "__main__":
    main()
