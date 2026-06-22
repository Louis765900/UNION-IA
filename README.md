# UNION IA 2.1

Assistant IA personnel — interface web moderne + terminal pour le code.
Propulsé par des moteurs cloud (DeepSeek, Gemini) avec mémoire active et
conversations persistantes.

---

## Démarrage rapide

### 1. Installer
```bat
installer.bat
```
Installe les dépendances et crée le fichier `.env`.

### 2. Configurer ta clé API
Ouvre `.env` et colle ta clé DeepSeek :
```
DEEPSEEK_API_KEY=sk-ta-vraie-cle
```
> Clé gratuite sur https://platform.deepseek.com → *API Keys*
> (Optionnel : `GEMINI_API_KEY` pour le moteur Gemini, sur https://aistudio.google.com)

### 3. Lancer
- **Interface web** (questions, dissertations, usage général) :
  ```bat
  lancer_web.bat
  ```
  puis ouvre http://127.0.0.1:5000
- **Terminal** (code, scripts) :
  ```bat
  lancer.bat
  ```

---

## La gamme UNION IA 2.1

Comme Gemini, UNION IA se décline en trois modes, réglables à la volée
(sélecteur en haut de l'interface web ou commande `/mode`) :

| Mode | Pour quoi | Vitesse |
|------|-----------|---------|
| **UNION IA 2.1** | Raisonnement complet, qualité maximale | Standard |
| **UNION IA 2.1 Flash** | Réponses concises du quotidien | Rapide |
| **UNION IA 2.1 Flashlight** | Réponses très courtes, directes | Ultra-rapide |

---

## Fonctionnalités

- **Mémoire active** — UNION IA retient automatiquement ce qui compte (ton
  prénom, tes projets, tes préférences) et s'en sert dans ses réponses.
  Tout est visible et modifiable dans *Paramètres → Mémoire active*.
- **Conversations persistantes** — chaque discussion est sauvegardée, listée
  dans la barre latérale, et rouvrable. Recherche plein-texte intégrée.
- **Plusieurs moteurs** — DeepSeek ou Gemini en cloud, modèles GGUF en local
  (si `llama-cpp-python` est installé). Changement sans redémarrage.
- **Thème clair / sombre**, rendu Markdown, blocs de code avec bouton copier,
  affichage du raisonnement (`<think>`), injection de fichiers (`@fichier`) et
  de dossiers entiers (`@dossier/`).

---

## Commandes (terminal et web)

| Commande | Effet |
|----------|-------|
| `/aide` | Liste les commandes |
| `/stats` | Statistiques de session |
| `/memoire` | Ce que UNION IA a mémorisé sur toi |
| `/historique` | Derniers échanges |
| `/oublier` | Efface l'historique de la session |
| `/mode 2.1\|flash\|flashlight` | Change la gamme |
| `/modele deepseek\|gemini\|kimi` | Change le moteur |
| `/nom [prénom]` | Définit ton prénom |
| `/quitter` | Quitte (terminal) |

---

## Architecture

```
UNION-IA/
├── cerveau/
│   ├── cerveau.py        Orchestration : routage, commandes, mémoire
│   ├── llm_cerveau.py    Moteurs (DeepSeek/Gemini/local) + gamme de modes
│   ├── stockage.py       Base SQLite : conversations, mémoire, profil
│   ├── memoire_active.py Extraction automatique de faits
│   ├── entraineur.py     Réseau neuronal (chemin rapide hors-ligne)
│   ├── reseau.py         Réseau de neurones 2 couches
│   └── langage.py        Tokenisation / vectorisation
├── web/
│   ├── server.py         API Flask (chat SSE, conversations, mémoire)
│   ├── index.html        Interface de chat
│   └── settings.html     Paramètres (mémoire, moteur, gamme, thème)
├── interface/terminal.py Interface terminal (Rich)
├── tests/                Suite de tests (python tests/lancer_tests.py)
├── donnees/              Données d'intents + base SQLite locale
├── union_ia.py           Point d'entrée terminal
└── system_prompt.md      Personnalité de UNION IA (éditable)
```

Le moteur est choisi automatiquement au démarrage selon les clés présentes :
**DeepSeek API → Gemini API → modèle local**. Tout est privé : la base de
données reste sur ta machine.

---

## Tests

```bat
python tests\lancer_tests.py
```
Suite sans dépendance externe (pas besoin de pytest), exécutable hors-ligne.

---

## Personnaliser UNION IA

Le caractère et le style de UNION IA se modifient dans `system_prompt.md`.
Les changements sont pris en compte immédiatement, sans redémarrage.
