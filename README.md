# Animal News Dashboard

Dashboard di notizie dal mondo animale (feed RSS / Google News), utile per individuare trend per memecoin.

- Sito live: https://satorisync-byte.github.io/animal-news-dashboard/
- Aggiornamento automatico ogni 30 minuti tramite GitHub Actions (`.github/workflows/update.yml`).
- Uso locale: `pip install -r requirements.txt && python3 aggregate.py` (genera `index.html` e `data.json`).
