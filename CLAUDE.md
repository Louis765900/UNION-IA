# Notes de développement — UNION IA

Repère rapide pour travailler sur le projet.

## Vue d'ensemble
UNION IA 2.1 est un assistant IA personnel. L'identité "UNION IA" est maintenue
partout : ne jamais exposer le moteur sous-jacent (DeepSeek, Gemini, etc.) dans
les réponses utilisateur. Les moteurs cloud ne servent qu'à *propulser* UNION IA.

## Lancer
- Web : `python web/server.py` → http://127.0.0.1:5000
- Terminal : `python union_ia.py`
- Tests : `python tests/lancer_tests.py` (aucune dépendance externe requise)

## Dépendances
- Cœur : `numpy`, `rich`, `flask`
- Cloud : `openai` (DeepSeek), `google-generativeai` (Gemini)
- Local (optionnel) : `llama-cpp-python`

## Architecture des modules

### cerveau/llm_cerveau.py
- `LLMCerveau` : façade. Choisit le moteur au démarrage (`_auto_charger`)
  selon les clés `.env` : DeepSeek → Gemini → local.
- Moteurs : `_MoteurOpenAI` (DeepSeek), `_MoteurGemini`, `_MoteurLocal`.
  Chacun expose `completer()` et `stream_deltas()`.
- `_parser_think()` : parser de streaming partagé qui gère les balises
  `<think>…</think>` **même coupées entre deux fragments réseau**.
- `MODES` : la gamme (`2.1`, `flash`, `flashlight`) = paramètres de génération
  + indication de concision. Indépendant du moteur.
- Le contexte mémoire est injecté via `fournir_memoire` (callback branché
  par le Cerveau) dans `construire_systeme()`.

### cerveau/stockage.py
- `Stockage` : SQLite thread-safe. Tables : conversations, messages,
  faits_memoire, profil, apprentissages.
- `DB_PATH` est résolu dynamiquement dans `__init__` → on peut le surcharger
  dans les tests (`cerveau.stockage.DB_PATH = ...`).
- Migration automatique des anciens JSON (memoire.json, apprentissage.json).

### cerveau/memoire_active.py
- `extraire_faits(message)` : extraction par regex de faits durables.
  Renvoie `[(cle, valeur_formatee, categorie), ...]`.
- Règles dans `_REGLES`. Le `_VAL` est la classe de caractères des valeurs
  (inclut apostrophes). `_nettoyer()` retire articles de tête et coupe aux
  conjonctions. Attention aux espaces littéraux dans les regex (bug historique).

### cerveau/cerveau.py
- `Cerveau` : routage. Ordre dans `repondre()` : commandes → apprentissage live
  → réponses apprises → mémoire active → prénom → réseau neuronal → LLM.
- Garde une compat dict via la propriété `memoire`.

### web/server.py
- Init en arrière-plan (thread) → démarrage instantané. `_attendre_init()`
  bloque les routes qui ont besoin du cerveau.
- `_conv_active` : conversation courante côté serveur ; l'historique LLM est
  rechargé via `_charger_conversation()` au changement.

## Conventions
- Tout en français (code, commentaires, UI).
- Ne pas committer : `.env`, `donnees/union_ia.db*`, `.venv*`, `*.gguf`.
- Après une modif de logique, lancer `python tests/lancer_tests.py`.

## Pièges connus
- Le réseau neuronal a une confiance très basse (~0.03) : quasi tout part au
  LLM, c'est voulu pour la gamme 2.1. Ne pas s'y fier comme classifieur fiable.
- Les modèles GGUF locaux (Kimi K2 surtout) peuvent échouer à charger faute de
  RAM → `besoin_llm` + fallback réseau neuronal gèrent le cas.
- `modele.npz` / `metadata.json` se régénèrent au 1er lancement si le hash des
  intents change (≈ 1 min une seule fois, puis chargement instantané).
