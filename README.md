# Wine Cellar — Producer Whitelist

Deterministic approach to building a 120-bottle wine cellar.

## Concept

Good restaurants curate good producers. Good producers make good wine at all price levels.
→ Use restaurant wine lists as a producer whitelist.
→ Monitor wine sites for when whitelisted producers appear.

## Phase 1 — Producer Whitelist (current)

### Setup

```bash
pip install -r requirements.txt
```

### Ingest a wine list PDF

```bash
python ingest.py winelist.pdf --restaurant "Glassalen"
```

This will:
1. Extract text from the PDF
2. Send it to Mistral to identify producers + styles
3. Store producers in `cellar.db`

### View your whitelist

```bash
python list.py
python list.py --style "Burgundy Chardonnay"
python list.py --country France
```

## Roadmap

- **Phase 2** — Cellar model: target allocation per style/tier across ~120 bottles
- **Phase 3** — Scraper: monitor Danish wine sites, alert on whitelist hits
