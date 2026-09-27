# Vérification visuelle — Header mobile sombre

- Source : `C:/Users/LENOVO~1/AppData/Local/Temp/codex-clipboard-c93458bd-26f9-42d6-ae24-a1a858edc4f4.png`
- Source : 310 × 583 px; cible mobile, thème sombre, conversation active
- Implémentation : `https://orvix-ai.pages.dev`
- Capture d’implémentation : indisponible sans session authentifiée dans le navigateur de contrôle

## Constat et correction

- P1 initial : le header redevenait clair uniquement quand `.orvix-chat-shell.has-messages` était présent.
- Correction : surcharge mobile explicite de l’état conversation active, suppression de toute image de fond et neutralisation des pseudo-éléments du header.
- Portée : règles strictement limitées à `max-width: 900px`; desktop verrouillé et inchangé.

## Vérification technique

- Compilation TypeScript/Vite réussie.
- Feuille générée : `assets/index-CX1fM_ly.css`.
- Production confirmée : la règle sombre ciblant `.chat-main:has(.orvix-chat-shell.has-messages) > .page-actions` est présente dans le bundle publié.
- Comparaison visuelle finale bloquée par l’absence d’une session authentifiée dans le navigateur de contrôle.

## Résultat

`final result: blocked`

Blocage : impossible de capturer le même écran Révision authentifié pour une comparaison visuelle finale.
