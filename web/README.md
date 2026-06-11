# Frontend — Garmin AI Coach

## Dev (hot reload)
Dois terminais:
```
uvicorn api.main:app --port 8000 --reload   # backend
cd web && npm run dev                        # frontend (5173, proxy /api)
```
Abrir http://localhost:5173

## Produção local
```
cd web && npm run build      # gera web/dist/
uvicorn api.main:app --port 8000
```
Abrir http://localhost:8000 (FastAPI serve API + React).

Ou usar `iniciar.bat` / `iniciar.vbs` na raiz.
