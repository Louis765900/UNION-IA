# Journal des nouveautés — UNION IA

## 2.2.0 — Skills, Auth, VS Code, Mobile

### Skills système (PDF, Excel, Access, Word)
- Nouveau module `cerveau/skills/` : architecture plugin extensible.
- Skills intégrés : **PDF** (pypdf/pdfplumber), **Excel/CSV** (openpyxl), **Access/SQLite**
  (pyodbc/sqlite3), **Word** (python-docx/odfpy).
- Quand tu glisses un fichier dans le chat, UNION IA choisit automatiquement
  le skill adapté et extrait le contenu pour l'analyser.
- **Skills personnalisés** : dans *Paramètres → Skills*, tu peux définir
  ta propre commande (`{fichier}` est remplacé par le chemin) pour n'importe
  quelle extension.

### Authentification & comptes utilisateurs
- Nouveau module `cerveau/auth.py` : comptes SQLite, hachage PBKDF2-SHA256,
  tokens de session (30 jours), compte admin automatique.
- Nouvelle page `/login` : connexion + création de compte.
- Nouvelle page `/admin` : liste des utilisateurs, changement de rôle, suppression.
- Routes API : `POST /api/auth/login`, `POST /api/auth/register`,
  `POST /api/auth/logout`, `GET /api/auth/me`.
- Routes admin protégées par décorateur `@admin_requis`.

### Extension VS Code
- Nouveau dossier `vscode-extension/` (TypeScript + Manifest).
- Commandes : **Ouvrir le chat**, **Expliquer le code**, **Revoir le code**,
  **Générer la documentation**, **Poser une question**.
- Menu contextuel dans l'éditeur (clic droit sur sélection).
- Panel WebView avec chat SSE natif.
- Configuration : URL serveur, token, mode.

### Application mobile (Expo React Native)
- Nouveau dossier `mobile/` : projet Expo avec expo-router.
- 3 onglets : **Chat** (streaming SSE), **Historique** des conversations,
  **Paramètres** (URL serveur, connexion, profil).
- Client API partagé (`src/api/client.ts`) : auth token, streaming.

### Déploiement Vercel
- `vercel.json` : configuration pour déployer le serveur Flask comme
  fonction serverless.

### Tests (20 nouveaux → 61 au total)
- `tests/test_skills.py` : 9 tests (skills CSV, custom, persistance, détection).
- `tests/test_auth.py` : 11 tests (comptes, hash, tokens, rôles).

## 2.1.0 — Refonte majeure

### Le grand changement
UNION IA passe d'un outil local Windows à une vraie plateforme d'assistant IA,
propulsée par des moteurs cloud, avec mémoire et conversations persistantes.

### Réponses naturelles (le problème « robotique » réglé)
- Les réponses passent désormais par un vrai moteur de langage (DeepSeek ou
  Gemini via API), au lieu du réseau neuronal qui renvoyait des phrases figées.
- `system_prompt.md` réécrit pour un ton fluide et direct.
- Identité « UNION IA » maintenue partout (le moteur sous-jacent n'est jamais
  révélé).

### Démarrage instantané
- L'ancien démarrage prenait jusqu'à 10 minutes. Désormais : moins de 2 secondes.
- Initialisation en arrière-plan, imports cloud différés, chargement du réseau
  neuronal depuis le cache (au lieu de retokeniser 2743 motifs).

### Mémoire active
- UNION IA retient automatiquement ce qui compte (prénom, projets, préférences)
  et s'en souvient d'une conversation à l'autre, sans qu'on ait à répéter.
- Visible et modifiable dans *Paramètres → Mémoire active*.

### Conversations persistantes
- Chaque discussion est sauvegardée (base SQLite locale), listée dans la barre
  latérale, rouvrable. Recherche plein-texte dans tout l'historique.

### Gamme UNION IA 2.1
- Trois modes réglables à la volée : **2.1** (complet), **2.1 Flash** (rapide),
  **2.1 Flashlight** (ultra-court).

### Interface web
- Liste des conversations + recherche, thème clair/sombre, sélecteur de gamme
  et de moteur, glisser-déposer de fichiers, rendu Markdown, bouton copier.

### Robustesse
- Bascule automatique sur le réseau neuronal si le moteur LLM échoue.
- Parser de streaming qui gère les balises `<think>` coupées entre deux
  fragments réseau (bug corrigé).
- 41 tests automatisés (`python tests/lancer_tests.py`).

### Portabilité
- Chemins relatifs (plus de `F:\Union IA` codé en dur).
- Installeur simplifié, dépendances cloud légères par défaut.
