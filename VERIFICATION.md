# Verifica milestone 1

Python 3.12.14. Compilazione sintattica riuscita.
`pytest -q`: 10 passed, 1 warning in 0.88s.
Warning: Starlette segnala la futura dismissione di httpx per TestClient in favore di httpx2. L'adapter runtime usa httpx e i test passano; nessuna migrazione non verificata introdotta.
requirements-lock.txt registra tutte le versioni dell'ambiente testato. Per riprodurlo: pip install -r backend/requirements-lock.txt. Docker usa gli intervalli di requirements.txt; per build riproducibili sostituire nel Dockerfile il file installato con requirements-lock.txt (include anche pytest).
Non eseguiti: build Docker, connessione reale PostgreSQL, generazione reale Ollama. I servizi non sono disponibili nell'ambiente di sviluppo. I test usano mock espliciti, non connessioni reali.
Milestone 2 non iniziata.
