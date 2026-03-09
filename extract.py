"""
Extract producers from a PDF wine list using Mistral.
"""
import json
import os
import pdfplumber
from mistralai import Mistral

MISTRAL_KEY = os.environ.get("MISTRAL_API_KEY", "REDACTED_MISTRAL_KEY")
MODEL = "mistral-large-latest"

SYSTEM_PROMPT = """You are a wine expert. Given raw text extracted from a restaurant wine list,
identify all wine producers/domaines/estates mentioned.

Return a JSON array of objects with these fields:
- name: producer/domaine name (required)
- region: wine region if identifiable (optional)
- country: country if identifiable (optional)
- styles: array of wine styles from this list that this producer fits:
  ["Champagne", "Pet-nat", "Orange", "German/Austrian Riesling", "German/Austrian Weissburgunder",
   "Jura Chardonnay", "Loire Chenin", "Burgundy Chardonnay", "North Rhone Syrah",
   "Spanish Tempranillo", "American Cabernet", "Loire Cabernet Franc", "German Spatburgunder",
   "Structured Burgundy/Beaujolais", "Light Beaujolais", "Piedmont Nebbiolo"]

Only include styles you are confident about. Return ONLY valid JSON, no commentary."""


def extract_text_from_pdf(pdf_path: str) -> str:
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
    return "\n\n".join(pages)


def extract_producers(pdf_path: str) -> list[dict]:
    print(f"[*] Reading PDF: {pdf_path}")
    text = extract_text_from_pdf(pdf_path)

    if not text.strip():
        print("[ERROR] No text extracted from PDF")
        return []

    print(f"[*] Extracted {len(text)} chars, sending to Mistral...")
    client = Mistral(api_key=MISTRAL_KEY)

    # Chunk text if very long (Mistral context limit)
    chunk_size = 30000  # mistral-large handles 32k context, use bigger chunks = fewer API calls
    chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
    all_producers = {}

    for i, chunk in enumerate(chunks):
        if len(chunks) > 1:
            print(f"[*] Processing chunk {i+1}/{len(chunks)}")

        response = client.chat.complete(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Wine list text:\n\n{chunk}"}
            ],
            temperature=0.1
        )

        raw = response.choices[0].message.content.strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        try:
            producers = json.loads(raw)
            for p in producers:
                name = p.get("name", "").strip()
                if name:
                    if name not in all_producers:
                        all_producers[name] = p
                    else:
                        # Merge styles
                        existing = set(all_producers[name].get("styles", []))
                        new = set(p.get("styles", []))
                        all_producers[name]["styles"] = list(existing | new)
        except json.JSONDecodeError as e:
            print(f"[WARNING] JSON parse error on chunk {i+1}: {e}")
            continue

    producers = list(all_producers.values())
    print(f"[OK] Found {len(producers)} producers")
    return producers
