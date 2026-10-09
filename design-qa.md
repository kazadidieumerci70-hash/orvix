# Design QA — Paiement mobile ORVIX

Source visual truth: `C:\Users\LENOVO~1\AppData\Local\Temp\codex-clipboard-fc119397-30db-478c-93e9-a0839f900ef5.png`.

Implementation: paiement dans `frontend/src/App.tsx` et `frontend/src/styles.css`.

Viewport/state: feuille de paiement mobile, Argent mobile sélectionné.

## Evidence

- Source dimensions: 447 × 774 px (capture fournie par l’utilisateur).
- Implementation screenshot: indisponible.
- Browser verification: bloquée. L’accès à `https://app.orvix.work/` depuis le navigateur automatisé a été refusé par la politique de navigateur de cette session.
- Build: `npm run build` réussi le 2026-10-09.

## Required fidelity surfaces

- Fonts and typography: à vérifier visuellement.
- Spacing and layout rhythm: à vérifier visuellement.
- Colors and visual tokens: à vérifier visuellement.
- Image quality and asset fidelity: l’interface utilise des icônes de la bibliothèque existante; à vérifier visuellement.
- Copy and content: adapté à ORVIX, sans Wave, wallet, PayPal, Apple Pay ni virement.

## Findings

- [P1] Comparaison visuelle bloquée : aucune capture navigateur de l’implémentation n’est disponible dans cette session.

## Implementation checklist

1. Ouvrir le paiement ORVIX sur mobile.
2. Vérifier les états Carte et Argent mobile.
3. Vérifier que le pays détecté peut être modifié.
4. Comparer l’espacement et les tailles au visuel de référence.

final result: blocked
