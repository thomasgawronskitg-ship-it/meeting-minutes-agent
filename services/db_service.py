from typing import Any, Dict, List, Optional
from supabase import create_client, Client
from settings import Settings
from services.embedding_service import embeddings

def _chunks(text: str, size: int, overlap: int) -> List[str]:
    if not text: return []
    res, i, n = [], 0, len(text)
    while i < n:
        res.append(text[i:i+size])
        i += max(1, size - overlap)
    return res

class DB:
    def __init__(self):
        self.enabled = bool(Settings.SUPABASE_URL and Settings.SUPABASE_ANON_KEY)
        self.client: Optional[Client] = None
        if self.enabled:
            self.client = create_client(Settings.SUPABASE_URL, Settings.SUPABASE_ANON_KEY)

    def insert_meeting_full(self, minutes: Dict[str, Any], transcript_text: str, segments: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not self.enabled: return None
        summary_emb = embeddings.embed_one(minutes.get('summary',''))
        meeting_payload = {
            'title': minutes.get('title') or 'Riunione',
            'date': minutes.get('date') or None,
            'participants': minutes.get('participants') or [],
            'summary': minutes.get('summary') or '',
            'decisions': minutes.get('decisions') or [],
            'actions': minutes.get('actions') or [],
            'next_steps': minutes.get('next_steps') or [],
            'transcript_text': transcript_text or '',
            'summary_embedding': summary_emb,
        }
        m = self.client.table('meetings').insert(meeting_payload).execute().data[0]
        chunks = _chunks(transcript_text, Settings.CHUNK_SIZE, Settings.CHUNK_OVERLAP)
        if chunks:
            chunk_embs = embeddings.embed(chunks)
            rows = [{'meeting_id': m['id'], 'chunk_text': txt, 'embedding': emb if not Settings.USE_VECTOR_JSON else {'v': emb}} for txt, emb in zip(chunks, chunk_embs)]
            self.client.table('transcript_chunks').insert(rows).execute()
        return m

    def search_chunks(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        if not self.enabled: return []
        q_emb = embeddings.embed_one(query)
        try:
            rows = self.client.rpc('match_transcript_chunks', {'query_embedding': q_emb, 'match_count': top_k}).execute().data
            return rows or []
        except Exception:
            import math
            rows = self.client.table('transcript_chunks').select('*').order('id', desc=True).limit(500).execute().data
            def cosine(a, b):
                if not a or not b: return 0.0
                s = sum(x*y for x,y in zip(a,b))
                na = math.sqrt(sum(x*x for x in a)); nb = math.sqrt(sum(y*y for y in b))
                return s/(na*nb+1e-9)
            scored = []
            for r in rows:
                emb = r.get('embedding', [])
                if isinstance(emb, dict): emb = emb.get('v', [])
                scored.append((cosine(q_emb, emb), r))
            scored.sort(key=lambda x: x[0], reverse=True)
            return [r for _, r in scored[:top_k]]

db = DB()
