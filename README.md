## Run
```bash
cp .env.template .env
uvicorn app.main:app --reload
celery -A app.infra.worker worker --loglevel=info
```