import torch, whisperx
from typing import Dict, Any
from settings import Settings

def transcribe_and_diarize(audio_path: str, language: str = 'it') -> Dict[str, Any]:
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    compute_type = Settings.CPU_COMPUTE_TYPE if device == 'cpu' else 'float16'
    model = whisperx.load_model(Settings.WHISPER_MODEL, device, compute_type=compute_type)
    asr_result = model.transcribe(audio_path, language=language)
    result = {'text': (asr_result.get('text') or '').strip(), 'segments': asr_result.get('segments') or [], 'language': asr_result.get('language') or language}
    if Settings.HF_TOKEN:
        diarize_model = whisperx.DiarizationPipeline(use_auth_token=Settings.HF_TOKEN, device=device)
        diarize_segments = diarize_model(audio_path)
        result['diarization_segments'] = diarize_segments
        result['segments'] = whisperx.assign_word_speakers(diarize_segments, result['segments'])
    return result
