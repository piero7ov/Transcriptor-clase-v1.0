# backend/app.py
from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from faster_whisper import WhisperModel
from chunk_buffer import ChunkBuffer
import tempfile, os, subprocess, sys, json, re

app = FastAPI(title="Transcriptor de Clase - Backend (small)")

# ---- CORS (XAMPP) ----
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://127.0.0.1", "*"],  # en prod, quita el "*"
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ======================  MODELO (small por defecto)  ======================
# Puedes sobrescribir con variables de entorno:
#   FW_MODEL   : small | medium | base      (default: small)
#   FW_DEVICE  : cuda | cpu                  (default: cuda)
#   FW_CTYPE   : float16 | int8              (default: float16 en GPU)
FW_MODEL  = os.getenv("FW_MODEL",  "small")
FW_DEVICE = os.getenv("FW_DEVICE", "cuda")
FW_CTYPE  = os.getenv("FW_CTYPE",  "float16")  # para GPU

buffer = ChunkBuffer()

def load_model():
    try:
        return WhisperModel(FW_MODEL, device=FW_DEVICE, compute_type=FW_CTYPE)
    except Exception:
        # Fallback robusto a CPU si no hay GPU/VRAM suficiente
        return WhisperModel("base", device="cpu", compute_type="int8")

model = load_model()

# ---- Glosario / contexto de dominio (ajústalo a tu clase) ----
PROMPT_EXTRA = (
    "informática hardware software placa base placas base buses de datos "
    "procesadores CPU GPU memoria RAM almacenamiento SSD disco duro SATA NVMe "
    "interfaces USB HDMI PCIe chipset BIOS UEFI audio digital analógico "
    "altavoces micrófono periféricos teclado ratón monitor "
)

# ======================  Sesión / archivo acumulado  ======================
TMP_DIR = tempfile.gettempdir()
ACCUM_BASE = os.path.join(TMP_DIR, "transcriptor_sesion")   # sin extensión
ACCUM_PATH = None            # …\transcriptor_sesion.webm | .wav (según 1er chunk)
LAST_END_SEC = 0.0           # último segundo ya procesado en el acumulado

# ---------- Utilidades ----------
def reset_session():
    """Borra archivo acumulado y reinicia estado/tiempos/buffer."""
    global ACCUM_PATH, LAST_END_SEC
    for ext in (".webm", ".wav", "_16k.wav", "_slice.wav"):
        try:
            p = ACCUM_BASE + ext
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass
    ACCUM_PATH = None
    LAST_END_SEC = 0.0
    buffer._segments.clear()

def append_bytes(path: str, data: bytes):
    """Crea/añade bytes al archivo acumulado (mantiene cabecera del 1er chunk)."""
    with open(path, "ab" if os.path.exists(path) else "wb") as f:
        f.write(data)

def run(cmd: list[str]) -> None:
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        stderr = p.stderr.decode(errors="ignore")[:4000]
        raise RuntimeError(stderr)

def ffmpeg_to_wav16(src_path: str) -> str:
    """Convierte acumulado (webm|wav) -> wav 16k mono (estable para Whisper)."""
    dst = ACCUM_BASE + "_16k.wav"
    # 1) intento directo
    try:
        run(["ffmpeg", "-y", "-i", src_path, "-ar", "16000", "-ac", "1", dst])
        return dst
    except Exception:
        pass
    # 2) forzar que la entrada sea WEBM (por si el acumulado es webm)
    run(["ffmpeg", "-y", "-f", "webm", "-i", src_path, "-ar", "16000", "-ac", "1", dst])
    return dst

def ffprobe_duration_sec(path: str) -> float:
    """Duración (segundos) usando ffprobe."""
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "format=duration", "-of", "json", path],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    if p.returncode != 0:
        return 0.0
    try:
        j = json.loads(p.stdout.decode())
        return float(j.get("format", {}).get("duration", 0.0)) or 0.0
    except Exception:
        return 0.0

def slice_tail(wav16_path: str, start_sec: float) -> str:
    """Genera un WAV 16k con SOLO la cola a partir de start_sec."""
    dst = ACCUM_BASE + "_slice.wav"
    run(["ffmpeg", "-y", "-ss", f"{start_sec:.3f}", "-i", wav16_path, "-ar", "16000", "-ac", "1", dst])
    return dst

def clean_text(t: str) -> str:
    """Pequeño post-procesado: quita repeticiones tipo 'vale vale', dobles espacios, trim."""
    if not t:
        return t
    t = t.strip()
    t = re.sub(r'\b(\w+)(\s+\1){1,}\b', r'\1', t, flags=re.IGNORECASE)  # repeticiones
    t = re.sub(r'\s{2,}', ' ', t)                                      # espacios
    return t.strip()

# ---------- Endpoints ----------
@app.get("/ping")
def ping():
    return {
        "ok": True, "msg": "pong", "py": sys.version.split()[0],
        "model": FW_MODEL, "device": FW_DEVICE, "ctype": FW_CTYPE
    }

@app.get("/api/reset")
def api_reset():
    reset_session()
    return {"ok": True}

@app.post("/api/chunk")
async def api_chunk(file: UploadFile, offset: float = Form(0.0)):
    """
    1) Acumula bytes (webm|wav) en un único archivo (cabecera válida).
    2) Convierte a WAV 16k mono.
    3) Transcribe SOLO la 'cola' nueva desde LAST_END_SEC - margin,
       con VAD + beam search + temperature + prompt de dominio + contexto corto.
    4) Actualiza LAST_END_SEC al total actual.
    """
    global ACCUM_PATH, LAST_END_SEC

    try:
        raw = await file.read()
        fname = (file.filename or "").lower()
        ext = ".wav" if fname.endswith(".wav") else ".webm"

        # Primer chunk define la extensión del acumulado
        if ACCUM_PATH is None:
            ACCUM_PATH = ACCUM_BASE + ext
            try:
                os.remove(ACCUM_PATH)
            except Exception:
                pass

        # Acumular bytes
        append_bytes(ACCUM_PATH, raw)

        # Convertir acumulado -> WAV 16k mono
        wav16 = ffmpeg_to_wav16(ACCUM_PATH)

        # Duración total del acumulado (en wav16)
        total_sec = ffprobe_duration_sec(wav16)

        # Si no hay avance, salimos
        if total_sec <= LAST_END_SEC + 0.05:
            return {"ok": True, "added": 0, "last_end": LAST_END_SEC, "total": total_sec}

        # Transcribir SOLO la cola (desde LAST_END_SEC - margin)
        margin = 0.35  # ~350 ms para no cortar palabras
        slice_start = max(LAST_END_SEC - margin, 0.0)
        tail_wav = slice_tail(wav16, slice_start)

        # Prompt con glosario + un poco de contexto reciente
        context_tail = buffer.to_txt()[-200:]
        initial_prompt = (PROMPT_EXTRA + " " + context_tail).strip()

        # Transcripción con parámetros que mejoran estabilidad
        segments, _ = model.transcribe(
            tail_wav,
            language="es",
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 300},
            beam_size=5,
            temperature=0.2,
            initial_prompt=initial_prompt,
        )

        added = 0
        for seg in segments:
            seg_start = slice_start + float(seg.start)
            seg_end = slice_start + float(seg.end)
            if seg_end <= LAST_END_SEC - 0.05:
                continue  # evita solapes ya procesados
            text = clean_text(seg.text)
            if text:
                buffer.add(seg_start, seg_end, text)
                added += 1

        # Avanza el puntero al final actual del audio total
        LAST_END_SEC = max(LAST_END_SEC, total_sec)

        # Limpieza de slice
        try:
            os.remove(tail_wav)
        except Exception:
            pass

        return {"ok": True, "added": added, "last_end": LAST_END_SEC, "total": total_sec}

    except Exception as e:
        return {"ok": False, "error": str(e)}

# ----- Descargas -----
@app.get("/api/transcript.txt", response_class=PlainTextResponse)
def api_txt():
    return buffer.to_txt()

@app.get("/api/transcript.srt", response_class=PlainTextResponse)
def api_srt():
    return buffer.to_srt()



