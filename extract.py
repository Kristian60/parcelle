"""
Extract producers and wines from a PDF wine list using OpenAI GPT-4o.
Processes page-by-page for thoroughness.
"""
import json
import os
import pdfplumber
from openai import OpenAI

OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "REDACTED_OPENAI_KEY")
MODEL = "gpt-4o"

SYSTEM_PROMPT = """You are a wine expert extracting data from a restaurant wine list.

Extract EVERY wine producer mentioned, no matter the style or region.

Return a JSON array of producer objects with:
- name: producer/domaine name (required)
- region: wine region if identifiable (optional)
- country: country if identifiable (optional)
- styles: array of matching areas (only include if confident):
  ["Champagne", "Pet-nat", "Orange", "Jura", "Loire", "Burgundy", "Beaujolais",
   "Rhone", "Bordeaux", "Germany/Austria", "Spain", "California", "Piedmont"]
- wines: array of individual wines, each with:
  - name: wine name/cuvee
  - vintage: year as string e.g. "2021" (optional)
  - format: e.g. "MAGNUM" (optional)
  - price: numeric price as string e.g. "1200" (optional)

Return ONLY valid JSON array, no commentary."""


def extract_text_pages(pdf_path: str) -> list[str]:
    """Extract text per page from PDF."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text and text.strip():
                pages.append(text)
    return pages


def extract_producers(pdf_path: str) -> list[dict]:
    print(f"[*] Reading PDF: {pdf_path}")
    pages = extract_text_pages(pdf_path)

    if not pages:
        print("[ERROR] No text extracted from PDF")
        return []

    print(f"[*] {len(pages)} pages extracted, processing in batches...")
    client = OpenAI(api_key=OPENAI_KEY)

    # Batch pages: ~4 pages per API call to stay focused
    batch_size = 4
    batches = [pages[i:i+batch_size] for i in range(0, len(pages), batch_size)]
    all_producers = {}

    for i, batch in enumerate(batches):
        print(f"[*] Batch {i+1}/{len(batches)} (pages {i*batch_size+1}-{min((i+1)*batch_size, len(pages))})")
        chunk = "\n\n---PAGE BREAK---\n\n".join(batch)

        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Wine list pages:\n\n{chunk}"}
                ],
                temperature=0.1
            )

            raw = response.choices[0].message.content.strip()  # type: ignore

            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()

            producers = json.loads(raw)
            for p in producers:
                name = p.get("name", "").strip()
                if not name:
                    continue
                if name not in all_producers:
                    all_producers[name] = p
                else:
                    # Merge styles and wines
                    existing_styles = set(all_producers[name].get("styles", []))
                    new_styles = set(p.get("styles", []))
                    all_producers[name]["styles"] = list(existing_styles | new_styles)
                    existing_wines = {w["name"]: w for w in all_producers[name].get("wines", [])}
                    for w in p.get("wines", []):
                        existing_wines[w.get("name", "")] = w
                    all_producers[name]["wines"] = list(existing_wines.values())

        except json.JSONDecodeError as e:
            print(f"[WARNING] JSON parse error on batch {i+1}: {e}")
        except Exception as e:
            print(f"[ERROR] Batch {i+1}: {e}")

    producers = list(all_producers.values())
    print(f"[OK] Found {len(producers)} producers")
    return producers
