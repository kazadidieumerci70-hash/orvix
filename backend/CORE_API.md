# API Core

`POST /core/process` (authentification Bearer requise)

Entrée : `{ "session_id": "…", "message": "…", "language": "Français" }`

Sortie : `requestId`, `status`, `intent`, `response`, `actions`, `metadata`.
Le moteur ne donne pas d’accès direct aux composants internes et refuse les messages vides.
