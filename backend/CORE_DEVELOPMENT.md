# Développement du Core

Le moteur est implémenté dans `app/core_engine.py` sans dépendance cloud. Ajoutez une
intention dans `_intent`, puis un orchestrateur dédié et des outils avec validation et
permissions explicites. Toute nouvelle mémoire doit être isolée par `user_id`.

Vérification locale : `backend/.venv/Scripts/python.exe -m compileall -q backend/app`.
