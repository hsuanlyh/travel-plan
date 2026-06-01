"""
Apply trip suggestions to index.html via AI.
Called by GitHub Actions with env vars:
  TRIP, SUGGESTIONS (JSON array)
  GEMINI_API_KEY   → uses Gemini 2.0 Flash (free tier)  [priority]
  ANTHROPIC_API_KEY → uses Claude Opus (paid)            [fallback]
"""
import os, json

trip        = os.environ["TRIP"]
suggestions = json.loads(os.environ["SUGGESTIONS"])

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
- Never remove the window.TRAVEL_EDIT config block or the shared/main.js script tag
- Preserve all content not mentioned in the suggestions
- For new sights use .tl-item.sight, for restaurants use .tl-item.food with .resto-card
- Google Maps links: https://www.google.com/maps/search/?api=1&query=URL_ENCODED_NAME
- Return only the raw HTML content, starting with <!DOCTYPE html>"""

# ── Call AI (Gemini first, Claude fallback) ────────────────────────
gemini_key    = os.environ.get("GEMINI_API_KEY", "")
anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")

if gemini_key:
    import urllib.request
    print("🤖 Using Gemini 2.0 Flash (free tier)")
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 16000}
    }).encode()
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models"
        f"/gemini-2.0-flash:generateContent?key={gemini_key}"
    )
    req = urllib.request.Request(url, data=payload,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
    updated_html = data["candidates"][0]["content"]["parts"][0]["text"].strip()

elif anthropic_key:
    import anthropic
    print("🤖 Using Claude Opus")
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=16000,
        messages=[{"role": "user", "content": prompt}]
    )
    updated_html = response.content[0].text.strip()

else:
    raise EnvironmentError(
        "No AI key found. Set GEMINI_API_KEY (free) or ANTHROPIC_API_KEY in GitHub Secrets."
    )

# strip ```html fences if model wrapped the output
if updated_html.startswith("```"):
    updated_html = updated_html.split("\n", 1)[1]
    updated_html = updated_html.rsplit("```", 1)[0].strip()

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
