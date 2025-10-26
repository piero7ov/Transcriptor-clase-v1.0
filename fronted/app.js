// ======= Config =======
const API_BASE = "http://127.0.0.1:8000";

// ======= UI refs =======
const startBtn = document.getElementById("startBtn");
const stopBtn  = document.getElementById("stopBtn");
const pauseBtn = document.getElementById("pauseBtn");
const copyBtn  = document.getElementById("copyBtn");
const clearBtn = document.getElementById("clearBtn");

const statusEl = document.getElementById("status");
const transcriptBox = document.getElementById("transcriptBox");
const autoscroll = document.getElementById("autoscroll");
const chunkTime = document.getElementById("chunkTime");

const srcSystem = document.getElementById("srcSystem");
const srcMic    = document.getElementById("srcMic");

// Tema
const themeBtn = document.getElementById("themeBtn");
const htmlEl = document.documentElement;

// ======= State =======
let rawStream = null;        // stream original (puede traer vídeo)
let mediaStream = null;      // solo audio
let mediaRecorder = null;
let recorderMime = "";
let isPaused = false;
let pollId = null;
let lastTranscript = "";

// ======= Tema (modo oscuro/claro) =======
function applyTheme(theme) {
  htmlEl.setAttribute("data-theme", theme);
  localStorage.setItem("theme", theme);
  themeBtn.textContent = theme === "dark" ? "☀️ Modo claro" : "🌙 Modo oscuro";
}

(function initTheme() {
  const saved = localStorage.getItem("theme");
  if (saved === "light" || saved === "dark") {
    applyTheme(saved);
  } else {
    // si no hay preferencia, usa preferencia del sistema
    const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
    applyTheme(prefersDark ? "dark" : "light");
  }
})();

themeBtn.addEventListener("click", () => {
  const current = htmlEl.getAttribute("data-theme") || "light";
  applyTheme(current === "dark" ? "light" : "dark");
});

// ======= Helpers =======
function updateStatus(text) {
  statusEl.textContent = text;
}
function pickFilenameExtByMime(mime) {
  if (!mime) return "chunk.webm";
  if (mime.includes("webm")) return "chunk.webm";
  if (mime.includes("mp4"))  return "chunk.mp4";
  if (mime.includes("ogg"))  return "chunk.ogg";
  return "chunk.webm";
}
function updateTextareaIfChanged(text) {
  if (text !== lastTranscript) {
    const atBottom = (transcriptBox.scrollTop + transcriptBox.clientHeight + 10) >= transcriptBox.scrollHeight;
    lastTranscript = text;
    transcriptBox.value = text;
    if (autoscroll.checked || atBottom) {
      transcriptBox.scrollTop = transcriptBox.scrollHeight;
    }
  }
}
async function fetchTranscriptOnce() {
  try {
    const res = await fetch(`${API_BASE}/api/transcript.txt`, { cache: "no-store" });
    if (!res.ok) return;
    const text = await res.text();
    updateTextareaIfChanged(text);
  } catch (_) {}
}
function startPolling() {
  if (pollId) clearInterval(pollId);
  fetchTranscriptOnce(); // immediate
  pollId = setInterval(fetchTranscriptOnce, 1000);
}
function stopPolling() {
  if (pollId) clearInterval(pollId);
  pollId = null;
}

// ======= Capture =======
async function getSystemStream() {
  return await navigator.mediaDevices.getDisplayMedia({
    video: true,
    audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false }
  });
}
async function getMicStream() {
  return await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
  });
}

// ======= Upload chunks =======
async function sendChunk(blob) {
  const form = new FormData();
  const fname = pickFilenameExtByMime(recorderMime);
  form.append("file", blob, fname);
  form.append("offset", "0");

  try {
    const res = await fetch(`${API_BASE}/api/chunk`, { method: "POST", body: form });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (data && !data.ok && data.error) {
      console.warn("Backend error:", data.error);
    }
    // La UI se sincroniza por polling
  } catch (e) {
    console.error("Error al enviar chunk:", e);
    updateStatus("Estado: Error enviando");
  }
}

// ======= Start/Stop/Pause =======
async function start() {
  try {
    const ms = parseInt(chunkTime.value, 10) || 4000;

    // 1) stream según fuente
    rawStream = srcMic.checked ? await getMicStream() : await getSystemStream();

    // 2) quedarnos solo con audio
    const audioTracks = rawStream.getAudioTracks();
    if (audioTracks.length === 0) {
      throw new Error("La fuente seleccionada no tiene audio. Si compartes pantalla/pestaña, marca 'Compartir audio'.");
    }
    mediaStream = new MediaStream(audioTracks);

    // 3) mimeType soportado
    let options = {};
    if (window.MediaRecorder && typeof MediaRecorder.isTypeSupported === "function") {
      if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
        options.mimeType = 'audio/webm;codecs=opus';
      } else if (MediaRecorder.isTypeSupported('audio/webm')) {
        options.mimeType = 'audio/webm';
      } else if (MediaRecorder.isTypeSupported('audio/mp4')) {
        options.mimeType = 'audio/mp4';
      } else if (MediaRecorder.isTypeSupported('audio/ogg;codecs=opus')) {
        options.mimeType = 'audio/ogg;codecs=opus';
      } else if (MediaRecorder.isTypeSupported('audio/ogg')) {
        options.mimeType = 'audio/ogg';
      } else {
        options = {};
      }
    }

    mediaRecorder = new MediaRecorder(mediaStream, options);
    recorderMime = mediaRecorder.mimeType || options.mimeType || "";

    mediaRecorder.ondataavailable = async (ev) => {
      if (!ev.data || ev.data.size === 0) return;
      if (isPaused) return;
      await sendChunk(ev.data);
    };

    mediaRecorder.onstart = () => {
      updateStatus("Estado: Grabando");
      isPaused = false;
      pauseBtn.textContent = "⏸️ Pausar";
      startPolling();
    };

    mediaRecorder.onstop = () => {
      updateStatus("Estado: Inactivo");
      stopPolling();
      // liberar pistas
      if (mediaStream) {
        mediaStream.getTracks().forEach(t => t.stop());
        mediaStream = null;
      }
      if (rawStream) {
        rawStream.getTracks().forEach(t => t.stop());
        rawStream = null;
      }
      fetchTranscriptOnce(); // última sync
    };

    mediaRecorder.start(ms);
    startBtn.disabled = true;
    stopBtn.disabled = false;
  } catch (e) {
    console.error("No se pudo iniciar la captura:", e);
    alert("No se pudo iniciar la captura.\n" + (e.message || e));
    updateStatus("Estado: Error al iniciar");
  }
}

function stop() {
  try {
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      mediaRecorder.stop();
    }
  } catch {}
  startBtn.disabled = false;
  stopBtn.disabled = true;
}

async function pauseResume() {
  if (!mediaRecorder) return;
  if (!isPaused) {
    try { mediaRecorder.stop(); } catch {}
    isPaused = true;
    pauseBtn.textContent = "▶️ Reanudar";
    updateStatus("Estado: Pausado");
    startPolling(); // por si llega algo pendiente
  } else {
    isPaused = false;
    pauseBtn.textContent = "⏸️ Pausar";
    await start();
    updateStatus("Estado: Grabando");
  }
}

// ======= Clear / Copy =======
function resetSessionUI() {
  try {
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      mediaRecorder.stop();
    }
  } catch {}
  startBtn.disabled = false;
  stopBtn.disabled = true;
  isPaused = false;
  pauseBtn.textContent = "⏸️ Pausar";
  updateStatus("Estado: Inactivo");
  stopPolling();
}
async function clearAll() {
  transcriptBox.value = "";
  lastTranscript = "";
  resetSessionUI();
  try {
    await fetch(`${API_BASE}/api/reset`);
  } catch {}
}
async function copyTranscript() {
  try {
    await navigator.clipboard.writeText(transcriptBox.value || "");
    copyBtn.textContent = "✔ Copiado";
    setTimeout(() => (copyBtn.textContent = "📋 Copiar"), 1200);
  } catch {
    alert("No se pudo copiar. ¿Permisos del navegador?");
  }
}

// ======= Events =======
startBtn.addEventListener("click", start);
stopBtn .addEventListener("click", stop);
pauseBtn.addEventListener("click", pauseResume);
clearBtn.addEventListener("click", clearAll);
copyBtn .addEventListener("click", copyTranscript);
