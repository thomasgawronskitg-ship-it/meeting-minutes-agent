import json
from typing import Dict, Any
from openai import OpenAI
from settings import Settings

client = None
if Settings.DEEPSEEK_API_KEY:
    client = OpenAI(api_key=Settings.DEEPSEEK_API_KEY, base_url=Settings.DEEPSEEK_BASE_URL)

PROMPT_IT = """Agisci come segretario di riunione. Riceverai:
1) transcript completo
2) segmenti con speaker e timestamp (se disponibili)

Produci SOLO JSON valido con questo schema:
{
  "title": "...",
  "date": "YYYY-MM-DD",
  "participants": ["..."],
  "summary": "...",
  "decisions": ["..."],
  "actions": [
    {"description": "...", "owner": "...", "due_date": "YYYY-MM-DD"}
  ],
  "next_steps": ["..."]
}

Linee guida:
- Lingua: italiano.
- Se mancano dati, inferisci con prudenza o lascia array vuoti.
- Date in ISO, nessun testo extra oltre al JSON.
"""

def generate_minutes(transcript_text: str, segments: Any) -> Dict[str, Any]:
    if not client:
        return {"title": "Riunione","date": "","participants": [],"summary": transcript_text[:500],"decisions": [],"actions": [],"next_steps": []}
    messages = [
        {"role":"system", "content":"Sei un assistente che produce verbali di riunione in italiano. Rispondi SOLO in JSON valido."},
        {"role":"user", "content": PROMPT_IT},
        {"role":"user", "content": f"TRANSCRIPT:\n{transcript_text}\n\nSEGMENTS:\n{json.dumps(segments)[:15000]}"},
    ]
    resp = client.chat.completions.create(model=Settings.DEEPSEEK_MODEL, messages=messages, temperature=0.2, response_format={"type":"json_object"})
    txt = resp.choices[0].message.content.strip()
    try:
        return json.loads(txt)
    except Exception:
        txt = txt[txt.find('{'):txt.rfind('}')+1]
        return json.loads(txt)
