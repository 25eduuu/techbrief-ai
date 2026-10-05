# TECHBRIEF AI — Milestone 1

Core backend locale: FastAPI, Pydantic Settings, SQLAlchemy async + asyncpg, PostgreSQL, adapter Ollama.
Nessun generatore di script/video, frontend, Redis, n8n o publisher in questa milestone.

## Avvio con Docker (PowerShell)

Installa Docker Desktop e Ollama. Dalla cartella techbrief-ai:

```powershell
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Inserisci il valore generato in API_KEY dentro .env. Sostituisci POSTGRES_PASSWORD e la stessa password nei due DATABASE_URL. Per caratteri speciali usa URL encoding nelle URL.

```powershell
ollama pull qwen2.5:3b
docker compose up -d --build
docker compose logs backend
Invoke-RestMethod http://localhost:8000/health
$key = (Get-Content .env | Where-Object { $_ -match '^API_KEY=' }) -replace '^API_KEY=', ''
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/ai/test -Headers @{ 'X-API-Key' = $key } -ContentType 'application/json' -Body '{"prompt":"Give me 3 AI tools for developers"}'
```

Health deve restituire status=ok e database=ok. Il test AI deve restituire model, response, prompt_tokens e completion_tokens. Senza chiave: 401; input non valido: 422; limite: 429; Ollama irraggiungibile: 503; timeout: 504; modello mancante o risposta invalida: 502.

Il modello è solo un esempio: usa un modello installato con `ollama list` e modifica OLLAMA_MODEL. Non è hardcodato nel codice.

### Ollama raggiungibile dai container

OLLAMA_BASE_URL_DOCKER usa host.docker.internal. Se Ollama ascolta solo su 127.0.0.1, il container potrebbe non raggiungerlo. Configura OLLAMA_HOST=0.0.0.0:11434 nel processo Ollama e riavvialo, consentendo con il firewall solo il traffico locale/Docker. Non esporre la porta Ollama a Internet. Alternativa: avvia il backend sul computer seguendo la sezione sotto.

## Backend sul computer (PowerShell)

```powershell
docker compose up -d postgres
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend/requirements-dev.txt
.\.venv\Scripts\python -m uvicorn app.main:create_app --factory --app-dir backend --host 127.0.0.1 --port 8000 --no-proxy-headers
```

Eseguire dalla root: Settings legge .env, DATABASE_URL punta a localhost e OLLAMA_BASE_URL punta a localhost. Il processo backend Docker deve essere fermato se usa già la porta 8000.

## Test

Dopo l'installazione:

```powershell
Push-Location backend
..\.venv\Scripts\python -m pytest -q
Pop-Location
```

I test isolati simulano DB e Ollama; non dimostrano un collegamento reale. La verifica reale è quella con i comandi health e test AI sopra. Nel workspace di creazione non sono presenti Docker, PostgreSQL o Ollama; l'esito pytest è documentato in VERIFICATION.md.

## Sicurezza e limiti

API key richiesta solo per operazioni AI. Prompt massimo 2000 caratteri, body massimo 16 KiB, output massimo 512 token; una generazione per volta. CORS esplicito. Rate limit per chiave condivisa in memoria: usare un solo worker e una sola replica. Riavviare il processo azzera il limite; un sistema distribuito richiederà storage condiviso. Non registriamo prompt, chiavi o risposte. I conteggi token sono restituiti ma api_usage persistente è rinviato allo schema dati. Costi monetari non stimati in questa fase locale.

La health pubblica verifica solo PostgreSQL; non avvia il modello. /docs e /openapi.json descrivono l'API senza bypassare l'autenticazione. Non ci sono upload o comandi shell.

Il database viene verificato con SELECT 1. Nessuna tabella viene ancora creata; introdurremo modelli UUID e migrazioni Alembic nella milestone che persiste contenuti. Per Supabase usare una connessione PostgreSQL compatibile asyncpg configurando TLS correttamente, mai disabilitando la verifica certificati.

Le dipendenze hanno intervalli compatibili, non un lock riproducibile verificato; prima del deployment definitivo produrre un lock dopo aver eseguito i test nell'ambiente target.

Nessuna LICENSE assegnata: la scelta della licenza resta al proprietario.

## Arresto

`docker compose down` ferma i servizi conservando i dati. Evita `down -v` se vuoi conservare PostgreSQL.
