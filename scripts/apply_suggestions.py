"""
Apply trip suggestions to index.html via Claude API.
Called by GitHub Actions with env vars:
  ANTHROPIC_API_KEY, SUGGESTIONS (JSON array), TRIP
"""
import os, json
import anthropic

trip    = os.environ["TRIP"]           # e.g. "2026-kansai"
raw     = os.environ["SUGGESTIONS"]    # JSON array of suggestion strings
suggestions = json.loads(raw)

# ── Read source files ──────────────────────────────────────────────
with open(f"{trip}/index.html", encoding="utf-8") as f:
    source_html = f.read()

with open("shared/style.css", encoding="utf-8") as f:
    css = f.read()

with open("shared/main.js", encoding="utf-8") as f:
    js = f.read()

# ── Build prompt ───────────────────────────────────────────────────
suggestions_text = "\n".join(f"- {s}" for s in suggestions)

prompt = f"""You are editing a travel itinerary HTML file. Apply ALL of the following suggestions and return ONLY the complete updated HTML, no explanations.

SUGGESTIONS TO APPLY:
{suggestions_text}

CURRENT HTML:
{source_html}

RULES:
- Apply every suggestion above
- Never add inline style= attributes — only use existing CSS classes
- Never remove the .suggest-bar / .suggest-btn block
- Preserve all content not mentioned in the suggestions
- For new sights use .tl-item.sight, for restaurants use .tl-item.food with .resto-card
- Google Maps links: https://www.google.com/maps/search/?api=1&query=URL_ENCODED_NAME
- Return only the raw HTML content, starting with <!DOCTYPE html>"""

# ── Call Claude ────────────────────────────────────────────────────
client = anthropic.Anthropic()
response = client.messages.create(
    model="claude-opus-4-5",
    max_tokens=16000,
    messages=[{"role": "user", "content": prompt}]
)
updated_html = response.content[0].text.strip()

# ── Save updated source ────────────────────────────────────────────
with open(f"{trip}/index.html", "w", encoding="utf-8") as f:
    f.write(updated_html)
print(f"✅ {trip}/index.html updated")

# ── Inline CSS/JS for staticrypt ───────────────────────────────────
inline = updated_html \
    .replace('<link rel="stylesheet" href="../shared/style.css">',
             f"<style>\n{css}\n</style>") \
    .replace('<script src="../shared/main.js"></script>',
             f"<script>\n{js}\n</script>")

with open(f"{trip}/_inline_tmp.html", "w", encoding="utf-8") as f:
    f.write(inline)
print(f"✅ {trip}/_inline_tmp.html ready for staticrypt")
