Minimalistic async template for tasks like "parse → download → upload → save".
--

## Run
```bash
cp .env.template .env
uvicorn app.main:app --reload
celery -A app.infra.worker worker --loglevel=info
```