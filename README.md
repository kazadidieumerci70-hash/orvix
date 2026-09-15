# Orvix

Orvix est désormais organisé en deux applications indépendantes :

- `frontend/` : React, TypeScript et Vite, destiné à Cloudflare Pages ;
- `backend/` : FastAPI et Gemini, destiné à un serveur séparé.

L'ancien prototype de bureau reste disponible dans `main.py` pendant la migration.

## Développement local

### API

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
# Ajouter la clé Gemini dans backend/.env
.\.venv\Scripts\python run.py
```

L'API répond sur `http://127.0.0.1:8000` en local et sa santé sur `http://127.0.0.1:8000/health`.

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Le site répond sur `http://localhost:5173`. En développement, Vite transfère `/api` à FastAPI.

## Cloudflare Pages

Connecter le dépôt Git et sélectionner `frontend` comme dossier racine :

- commande de build : `npm run build` ;
- dossier de sortie : `dist` ;
- variable `VITE_API_URL` : URL HTTPS publique du serveur FastAPI, par exemple `https://api.orvix.com`.

Cloudflare Pages héberge uniquement les fichiers statiques du frontend. Aucune Function ni aucun Worker n'est utilisé.

## Backend FastAPI sur VPS

Dans `backend/.env` :

```env
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-3.6-flash
FRONTEND_ORIGINS=https://orvix.pages.dev,https://orvix.com
MAX_UPLOAD_MB=10
```

Le serveur FastAPI doit être placé derrière HTTPS. La clé Gemini ne doit jamais être ajoutée à une variable `VITE_*` ni au frontend.

Commande simple pour lancer sur un VPS :

```bash
cd backend
python -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
./.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Routes utiles pour le frontend :

- `GET /health`
- `GET /api/v1/status`
- `GET /api/v1/documents`
- `POST /api/v1/documents` avec un champ fichier `files`
- `DELETE /api/v1/documents/{document_id}`
- `POST /api/v1/chat`
- `POST /api/v1/revision`
- `POST /api/v1/quiz`
