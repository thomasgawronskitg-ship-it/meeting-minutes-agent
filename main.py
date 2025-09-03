import os, logging
from flask import Flask, jsonify, request, render_template_string
from flask_cors import CORS
from settings import Settings
from services.google_drive_service import find_latest_audio_and_download
from services.asr_service import transcribe_and_diarize
from services.llm_service import generate_minutes
from services.db_service import db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = Settings.MAX_CONTENT_LENGTH_MB * 1024 * 1024
CORS(app, resources={r"/*": {"origins": Settings.CORS_ORIGINS}})

INDEX_HTML = "<!doctype html><html lang='it'><head><meta charset='utf-8'/><title>Meeting Agent</title></head><body style='font-family:system-ui;margin:2rem;max-width:880px'><h2>Dashboard</h2><ul><li><a href='/health'>System Health</a></li><li><a href='/process'>Process Latest Meeting (API)</a></li><li><a href='/meetings'>View Meetings</a></li><li><a href='/chat'>Chat Q&A</a></li></ul></body></html>"
CHAT_HTML = "<!doctype html><html lang='it'><head><meta charset='utf-8'/><title>Chat</title></head><body style='font-family:system-ui;margin:2rem;max-width:880px'><h2>Chat Q&A</h2><form id='f'><input name='q' placeholder='Domanda in italiano' style='width:70%'/><button>Invia</button></form><pre id='o' style='background:#f7f7f7;padding:1rem;border:1px solid #eee;border-radius:8px'></pre><script>const f=document.getElementById('f'), o=document.getElementById('o');f.addEventListener('submit', async e=>{e.preventDefault();o.textContent='...';const q=new FormData(f).get('q');const r=await fetch('/api/chat',{method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({q})});o.textContent=JSON.stringify(await r.json(), null, 2);});</script></body></html>"

@app.get("/")
def index(): return render_template_string(INDEX_HTML)

@app.get("/health")
def health():
    checks = {
        "drive_configured": bool(Settings.GOOGLE_FOLDER_ID and (Settings.GDRIVE_SA_JSON_BASE64 or Settings.GOOGLE_APPLICATION_CREDENTIALS)),
        "supabase_enabled": db.enabled,
        "deepseek_configured": bool(Settings.DEEPSEEK_API_KEY),
        "hf_token_for_diarization": bool(Settings.HF_TOKEN),
    }
    return jsonify({"status":"ok", "checks":checks})

@app.get("/process")
def process_page(): return jsonify({"hint": "POST /api/process per eseguire la pipeline", "folder": Settings.GOOGLE_FOLDER_ID})

@app.post("/api/process")
def process_api():
    if not Settings.GOOGLE_FOLDER_ID:
        return jsonify({"error":"GOOGLE_FOLDER_ID non configurato"}), 400
    try:
        _, local_path = find_latest_audio_and_download(Settings.GOOGLE_FOLDER_ID, "/tmp",
                                                       Settings.GDRIVE_SA_JSON_BASE64,
                                                       Settings.GOOGLE_APPLICATION_CREDENTIALS)
    except Exception as e:
        return jsonify({"error": f"Drive download failed: {e}"}), 500
    try:
        asr = transcribe_and_diarize(local_path, language="it")
    except Exception as e:
        return jsonify({"error": f"ASR failed: {e}"}), 500
    try:
        minutes = generate_minutes(asr.get("text",""), asr.get("segments", []))
    except Exception as e:
        return jsonify({"error": f"LLM minutes failed: {e}"}), 500
    meeting_row = None
    if db.enabled:
        try:
            meeting_row = db.insert_meeting_full(minutes, asr.get("text",""), asr.get("segments", []))
        except Exception as e:
            return jsonify({"error": f"DB insert failed: {e}", "minutes": minutes, "asr": {"len_text": len(asr.get('text',''))}}), 500
    try: os.remove(local_path)
    except Exception: pass
    return jsonify({"status": "ok","meeting": meeting_row,"minutes": minutes,"language": asr.get("language"),"diarization": bool(asr.get("diarization_segments"))})

@app.get("/meetings")
def meetings_page():
    if not db.enabled: return jsonify({"error": "Supabase non configurato"}), 400
    data = db.client.table("meetings").select("*").order("id", desc=True).limit(50).execute().data
    return jsonify(data)

@app.get("/chat")
def chat_page(): return render_template_string(CHAT_HTML)

@app.post("/api/chat")
def chat_api():
    body = request.get_json(force=True) or {}
    q = (body.get("q") or "").strip()
    if not q: return jsonify({"error":"manca la domanda"}), 400
    hits = db.search_chunks(q, top_k=6) if db.enabled else []
    if not hits: return jsonify({"answer": "non ho trovato informazioni rilevanti.", "hits": []})
    ctx_lines = [f"[meeting_id={h.get('meeting_id')}] {h.get('chunk_text','').strip()}" for h in hits]
    context_block = "\n---\n".join(ctx_lines)
    from services.llm_service import client, Settings as _S
    if not client: return jsonify({"answer": ctx_lines[0] if ctx_lines else "non ho trovato informazioni rilevanti.", "hits": hits})
    prompt = f"Rispondi in italiano SOLO usando il contesto seguente. Se l'informazione non è nel contesto, rispondi 'non ho trovato informazioni rilevanti.'\n\nContesto:\n{context_block}\n\nDomanda: {q}"
    resp = client.chat.completions.create(model=_S.DEEPSEEK_MODEL, messages=[{"role":"system","content":"Rispondi conciso e formale in italiano."},{"role":"user","content":prompt}], temperature=0.1)
    answer = resp.choices[0].message.content.strip()
    return jsonify({"answer": answer, "hits": hits})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=Settings.PORT)
