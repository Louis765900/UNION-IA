#!/usr/bin/env python3
"""
Générateur de données d'entraînement UNION IA.
Supporte DeepSeek API et Gemini API comme backends de génération.

Usage :
    1. Configure scripts/.env avec ta clé API
    2. Lance depuis F:\\Union IA\\ :  python scripts/generer_donnees.py

Le script détecte automatiquement quelle clé est disponible et choisit le backend.
DeepSeek API est prioritaire (plus rapide, pas de rate limit strict).
"""

import json
import os
import re
import sys
import time
from pathlib import Path

import requests

# ── Chemins ───────────────────────────────────────────────────────────────────
ROOT        = Path(__file__).parent.parent
INTENTS_SRC = ROOT / "donnees" / "intents.json"
SORTIE      = ROOT / "donnees" / "base_complete.json"
PROGRES     = ROOT / "donnees" / "_progres_generation.json"
ENV_FILE    = Path(__file__).parent / ".env"

# ── Paramètres ────────────────────────────────────────────────────────────────
PATTERNS_PAR_INTENT  = 80    # Patterns générés pour chaque intent existant
DELAI_DEEPSEEK       = 0.5   # Secondes entre appels DeepSeek (pas de rate limit strict)
DELAI_GEMINI         = 4.5   # Secondes entre appels Gemini (15 req/min)

MODELE_DEEPSEEK = "deepseek-chat"
MODELE_GEMINI   = "gemini-1.5-flash"

# Nouveaux intents à créer (tag, description pour le prompt)
NOUVEAUX_INTENTS = [
    ("mathematiques",  "questions de mathématiques, algèbre, géométrie, probabilités, équations"),
    ("sciences",       "physique, chimie, biologie, expériences scientifiques"),
    ("geographie",     "pays, capitales, continents, océans, géographie mondiale"),
    ("histoire",       "événements historiques, dates, personnages, guerres, révolutions"),
    ("cuisine",        "recettes, ingrédients, techniques culinaires, plats, gastronomie"),
    ("sport",          "sports, règles du jeu, équipes, performances, athlètes"),
    ("finance",        "argent, budget, économies, investissement, bourse, crypto"),
    ("education",      "études, école, université, cours, apprentissage, diplômes"),
    ("traduction",     "demandes de traduction de mots ou phrases d'une langue à une autre"),
    ("voyages",        "destinations, tourisme, vacances, hôtels, transports, passeport"),
    ("emploi",         "travail, CV, entretien d'embauche, métiers, salaire, reconversion"),
    ("psychologie",    "émotions, confiance en soi, anxiété, bien-être mental, motivation"),
    ("environnement",  "écologie, réchauffement climatique, recyclage, nature, pollution"),
    ("animaux",        "animaux de compagnie, espèces, comportement animal, vétérinaire"),
    ("actualites",     "nouvelles, presse, médias, actualité politique, événements récents"),
    ("creativite",     "écriture créative, storytelling, brainstorming, idées, imagination"),
    ("relations",      "amitié, famille, amour, communication, conflits, relations sociales"),
    ("astronomie",     "espace, planètes, étoiles, galaxies, trous noirs, exploration spatiale"),
    ("droit",          "lois, droits des citoyens, contrats, juridique, procédures légales"),
    ("langues",        "apprentissage des langues étrangères, grammaire, vocabulaire, conjugaison"),
]

# ── Chargement des clés API ───────────────────────────────────────────────────

def charger_env() -> dict:
    """Lit les variables du fichier .env."""
    vars_env = {}
    if ENV_FILE.exists():
        for ligne in ENV_FILE.read_text(encoding="utf-8").splitlines():
            ligne = ligne.strip()
            if ligne and not ligne.startswith("#") and "=" in ligne:
                cle, val = ligne.split("=", 1)
                vars_env[cle.strip()] = val.strip()
    # Variables d'environnement système en priorité
    for k in ("DEEPSEEK_API_KEY", "GEMINI_API_KEY"):
        if os.environ.get(k):
            vars_env[k] = os.environ[k]
    return vars_env


def choisir_backend(env: dict) -> tuple[str, str]:
    """Retourne (backend, clé) — DeepSeek prioritaire sur Gemini."""
    if env.get("DEEPSEEK_API_KEY"):
        return "deepseek", env["DEEPSEEK_API_KEY"]
    if env.get("GEMINI_API_KEY"):
        return "gemini", env["GEMINI_API_KEY"]
    print()
    print("  ❌  Aucune clé API trouvée.")
    print(f"     Crée le fichier : {ENV_FILE}")
    print("     Avec :  DEEPSEEK_API_KEY=sk-...   (prioritaire)")
    print("       ou :  GEMINI_API_KEY=AIzaSy...")
    print()
    sys.exit(1)

# ── Appels API ────────────────────────────────────────────────────────────────

def appeler_deepseek(cle: str, prompt: str, tentatives: int = 3) -> str:
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {cle}", "Content-Type": "application/json"}
    payload = {
        "model": MODELE_DEEPSEEK,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.92,
        "max_tokens": 2048,
    }
    for tentative in range(tentatives):
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=30)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except requests.exceptions.HTTPError as e:
            if r.status_code == 429:
                time.sleep(10 * (tentative + 1))
            elif tentative < tentatives - 1:
                time.sleep(3)
            else:
                raise
    raise RuntimeError("Echec DeepSeek après plusieurs tentatives.")


def appeler_gemini(cle: str, prompt: str, tentatives: int = 3) -> str:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta"
        f"/models/{MODELE_GEMINI}:generateContent"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.92, "maxOutputTokens": 2048},
        "safetySettings": [
            {"category": c, "threshold": "BLOCK_NONE"}
            for c in [
                "HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH",
                "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT",
            ]
        ],
    }
    for tentative in range(tentatives):
        try:
            r = requests.post(url, json=payload, params={"key": cle}, timeout=30)
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        except requests.exceptions.HTTPError as e:
            if r.status_code == 429:
                attente = 60 * (tentative + 1)
                print(f"\n     ⏳ Rate limit Gemini — attente {attente}s...", end=" ")
                time.sleep(attente)
            elif tentative < tentatives - 1:
                time.sleep(3)
            else:
                raise
    raise RuntimeError("Echec Gemini après plusieurs tentatives.")


def appeler(backend: str, cle: str, prompt: str) -> str:
    if backend == "deepseek":
        return appeler_deepseek(cle, prompt)
    return appeler_gemini(cle, prompt)

# ── Génération de patterns ────────────────────────────────────────────────────

def generer_patterns(backend: str, cle: str, tag: str, patterns_existants: list, n: int) -> list:
    exemples = "\n".join(f"- {p}" for p in patterns_existants[:12])
    prompt = f"""Génère {n} nouvelles phrases courtes en français pour l'intent "{tag}" d'un chatbot IA.

Phrases existantes (exemples du même intent) :
{exemples}

Règles strictes :
- Exactement {n} phrases, une par ligne
- 2 à 9 mots max par phrase
- Français uniquement
- Varie les registres : familier, formel, argot, SMS, oral, écrit, régional
- Pas de numérotation, tiret, explication — uniquement les phrases en minuscules"""

    texte = appeler(backend, cle, prompt)
    existants = {p.lower().strip() for p in patterns_existants}
    nouvelles = []
    for ligne in texte.strip().splitlines():
        phrase = re.sub(r'^[-•*·\d\.\)]+\s*', '', ligne).strip().lower()
        if phrase and len(phrase) > 2 and phrase not in existants:
            nouvelles.append(phrase)
            existants.add(phrase)
    return nouvelles[:n]


def generer_intent(backend: str, cle: str, tag: str, sujet: str) -> dict | None:
    prompt = f"""Crée un intent de chatbot pour le sujet : "{sujet}".

Génère un objet JSON avec :
- "patterns" : 35 formulations d'utilisateur en français (2-9 mots, minuscules, registres variés)
- "responses" : 5 réponses du chatbot en français (directes, naturelles, utiles)

Réponds UNIQUEMENT avec le JSON, rien d'autre :
{{
  "patterns": ["formulation 1", "formulation 2", ...],
  "responses": ["réponse 1", "réponse 2", ...]
}}"""

    texte = appeler(backend, cle, prompt)
    match = re.search(r'\{[\s\S]*\}', texte)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        patterns  = [str(p).lower().strip() for p in data.get("patterns", []) if p]
        responses = [str(r).strip() for r in data.get("responses", []) if r]
        if not patterns or not responses:
            return None
        return {"tag": tag, "patterns": patterns, "responses": responses}
    except json.JSONDecodeError:
        return None

# ── Progression ───────────────────────────────────────────────────────────────

def charger_progres() -> dict:
    if PROGRES.exists():
        try:
            return json.loads(PROGRES.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"enrichis": {}, "nouveaux": {}}


def sauvegarder_progres(p: dict):
    PROGRES.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")

# ── Assemblage ────────────────────────────────────────────────────────────────

def assembler_et_sauvegarder(intents_originaux: list, progres: dict):
    intents_enrichis = []

    for intent in intents_originaux:
        tag = intent["tag"]
        nouveaux = progres["enrichis"].get(tag, [])
        if nouveaux:
            intents_enrichis.append({
                "tag": tag,
                "patterns": nouveaux,
                "responses": intent["responses"],
            })

    for tag, data in progres["nouveaux"].items():
        if data:
            intents_enrichis.append(data)

    if not intents_enrichis:
        print("  ⚠  Aucune donnée à sauvegarder.")
        return

    SORTIE.parent.mkdir(exist_ok=True)
    SORTIE.write_text(
        json.dumps({"intents": intents_enrichis}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    total = sum(len(i["patterns"]) for i in intents_enrichis)
    print(f"  ✅  {len(intents_enrichis)} intents · {total} patterns → {SORTIE.name}")

# ── Réentraînement ────────────────────────────────────────────────────────────

def reentrainer():
    sys.path.insert(0, str(ROOT))
    from cerveau.entraineur import Entraineur
    print("\n  🔄  Réentraînement du réseau neuronal...")
    e = Entraineur()
    e.charger_intents()
    total = sum(len(i["patterns"]) for i in e.intents)
    print(f"     {len(e.intents)} intents · {total} patterns au total")
    e.entrainer(force=True)
    print("  ✅  Modèle réentraîné et sauvegardé.")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print()
    print("╔══════════════════════════════════════════════════════╗")
    print("║     UNION IA — Génération de données d'entraînement  ║")
    print("╚══════════════════════════════════════════════════════╝")
    print()

    env     = charger_env()
    backend, cle = choisir_backend(env)
    delai   = DELAI_DEEPSEEK if backend == "deepseek" else DELAI_GEMINI

    print(f"  ✔  Backend : {backend.upper()} ({cle[:8]}...)")

    with open(INTENTS_SRC, encoding="utf-8") as f:
        intents_originaux = json.load(f)["intents"]
    print(f"  ✔  {len(intents_originaux)} intents existants chargés")

    progres = charger_progres()
    deja    = len(progres["enrichis"]) + len(progres["nouveaux"])
    if deja > 0:
        print(f"  ⏩  Reprise : {deja} intents déjà traités")

    restants = (
        (len(intents_originaux) - len(progres["enrichis"]))
        + (len(NOUVEAUX_INTENTS) - len(progres["nouveaux"]))
    )
    print(f"  📋  {restants} appels API restants (≈ {restants * delai / 60:.1f} min)\n")

    # Phase 1 — Enrichir les intents existants
    print("━" * 56)
    print("  Phase 1/2 — Enrichissement des intents existants")
    print("━" * 56)

    for i, intent in enumerate(intents_originaux, 1):
        tag = intent["tag"]
        if tag in progres["enrichis"]:
            print(f"  [{i:02d}/{len(intents_originaux)}] {tag} — déjà fait ✓")
            continue
        print(f"  [{i:02d}/{len(intents_originaux)}] {tag}...", end=" ", flush=True)
        try:
            patterns = generer_patterns(backend, cle, tag, intent["patterns"], PATTERNS_PAR_INTENT)
            progres["enrichis"][tag] = patterns
            sauvegarder_progres(progres)
            print(f"+{len(patterns)} patterns ✓")
        except Exception as e:
            print(f"⚠ {e}")
        if i < len(intents_originaux):
            time.sleep(delai)

    # Phase 2 — Créer de nouveaux intents
    print()
    print("━" * 56)
    print("  Phase 2/2 — Création de nouveaux intents")
    print("━" * 56)

    for j, (tag, sujet) in enumerate(NOUVEAUX_INTENTS, 1):
        if tag in progres["nouveaux"]:
            print(f"  [{j:02d}/{len(NOUVEAUX_INTENTS)}] {tag} — déjà fait ✓")
            continue
        print(f"  [{j:02d}/{len(NOUVEAUX_INTENTS)}] {tag}...", end=" ", flush=True)
        try:
            intent = generer_intent(backend, cle, tag, sujet)
            progres["nouveaux"][tag] = intent
            sauvegarder_progres(progres)
            if intent:
                print(f"+{len(intent['patterns'])} patterns ✓")
            else:
                print("⚠ JSON invalide")
        except Exception as e:
            print(f"⚠ {e}")
        if j < len(NOUVEAUX_INTENTS):
            time.sleep(delai)

    # Finalisation
    print()
    print("━" * 56)
    assembler_et_sauvegarder(intents_originaux, progres)
    reentrainer()

    if PROGRES.exists():
        PROGRES.unlink()

    patterns_gen = sum(
        len(v) for v in progres["enrichis"].values() if isinstance(v, list)
    ) + sum(
        len(v.get("patterns", [])) for v in progres["nouveaux"].values()
        if isinstance(v, dict) and v
    )
    originaux = sum(len(i["patterns"]) for i in intents_originaux)

    print()
    print("╔══════════════════════════════════════════════════════╗")
    print(f"║  Terminé !  {originaux:>5} patterns originaux               ║")
    print(f"║             {patterns_gen:>5} patterns générés               ║")
    print(f"║             {len(NOUVEAUX_INTENTS):>5} nouveaux intents créés              ║")
    print("║                                                      ║")
    print("║  Redémarre le serveur pour profiter du nouveau modèle║")
    print("╚══════════════════════════════════════════════════════╝")
    print()


if __name__ == "__main__":
    main()
