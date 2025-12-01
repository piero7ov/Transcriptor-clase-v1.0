# Transcriptor de Clase 🎧

Aplicación web que captura audio del sistema o del micrófono y lo transcribe a texto en tiempo (casi) real usando **faster-whisper**.  
Pensado para tomar mejores apuntes durante clases, reuniones o vídeos.

> Frontend sencillo en HTML/CSS/JS + backend en FastAPI (Python).

---

## ✨ Características

- 🎙️ Captura desde:
  - Micrófono
  - Audio del sistema (compartiendo audio en el navegador)
- ⏱️ Transcripción por *chunks* configurables (4 s, 6 s, 8 s, 10 s…)
- 🌓 Tema claro / oscuro (toggle en la interfaz)
- 🧠 Contexto de dominio configurable (glosario de términos técnicos en el backend)
- 📋 Botones útiles:
  - Iniciar / Detener / Pausar–Reanudar
  - Copiar todo el texto al portapapeles
  - Limpiar la caja de transcripción
- 💾 Descarga de resultados:
  - TXT plano
  - SRT con marcas de tiempo
- 🌐 CORS preparado para funcionar con XAMPP u otros servidores locales (`http://localhost`, `http://127.0.0.1`)

---

## 🗂 Estructura del proyecto

```text
Transcriptor-clase-v1.0-main/
├── README.md
├── backend/
│   ├── app.py               # API FastAPI (endpoints, carga de modelo, lógica FFmpeg)
│   ├── chunk_buffer.py      # Buffer de segmentos y generación de TXT/SRT
│   ├── requirements.txt     # Dependencias del backend
│   ├── run_cpu.bat          # Script para lanzar en modo CPU (Windows)
│   └── .venv/               # Entorno virtual (puedes ignorarlo o recrearlo)
├── fronted/
│   ├── index.html           # Interfaz principal del transcriptor
│   ├── style.css            # Estilos (incluye modo oscuro/claro)
│   └── app.js               # Lógica de captura de audio y llamadas a la API
└── documentación/
    ├── Manual_de_Usuario_Transcriptor.odt  # Manual de usuario
    ├── portada.png
    └── portada2.png
````
---

## 🧩 Tecnologías utilizadas

**Frontend**

* HTML5
* CSS3 (variables, tema claro/oscuro)
* JavaScript:

  * `getUserMedia` / `MediaRecorder` para capturar audio
  * `fetch` para enviar *chunks* al backend
  * Copiado al portapapeles, autoscroll, etc.

**Backend**

* [FastAPI](https://fastapi.tiangolo.com/)
* [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
* `ffmpeg` y `ffprobe` vía `subprocess`
* `uvicorn` como servidor ASGI

---

## ✅ Requisitos previos

* **Python 3.10+** (recomendado)
* **FFmpeg** instalado y accesible en el `PATH`:

  * Comprobar con: `ffmpeg -version` y `ffprobe -version`
* Un navegador moderno (Chrome, Edge, Brave…) con soporte para:

  * Captura de pantalla/ventana/pestaña
  * Compartir audio del sistema (en caso de querer capturar el audio del PC)

Si quieres usar GPU:

* Tarjeta NVIDIA compatible
* Drivers + CUDA instalados (según requisitos de `faster-whisper`)

---

## ⚙️ Configuración del backend

1. Ve a la carpeta `backend`:

   ```bash
   cd backend
   ```

2. (Opcional pero recomendado) Crea y activa un entorno virtual:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # En Windows
   # o
   source .venv/bin/activate  # En Linux/Mac
   ```

3. Instala las dependencias:

   ```bash
   pip install -r requirements.txt
   ```

4. El backend lee estas **variables de entorno**:

   ```text
   FW_MODEL   : small | medium | base    (por defecto: small)
   FW_DEVICE  : cuda | cpu               (por defecto: cuda)
   FW_CTYPE   : float16 | int8           (por defecto: float16 en GPU)
   ```

   Ejemplos:

   * Forzar CPU (lento pero sin GPU):

     ```bash
     set FW_MODEL=small
     set FW_DEVICE=cpu
     set FW_CTYPE=int8
     uvicorn app:app --reload --port 8000
     ```

     O simplemente usar el script incluido en Windows:

     ```bash
     run_cpu.bat
     ```

   * Usar GPU (si está disponible):

     ```bash
     set FW_MODEL=small
     set FW_DEVICE=cuda
     set FW_CTYPE=float16
     uvicorn app:app --reload --port 8000
     ```

5. Por defecto, el backend queda escuchando en:

   ```text
   http://127.0.0.1:8000
   ```

---

## 💻 Puesta en marcha del frontend

1. Ve a la carpeta `fronted`:

   ```bash
   cd fronted
   ```

2. Opciones para servir el frontend:

   * Usar **XAMPP** (u otro servidor local) y colocar esta carpeta en `htdocs`.
   * Usar la extensión **Live Server** (VS Code / similar).
   * O cualquier servidor estático sencillo.

3. Abre la página en tu navegador:

   ```text
   http://localhost/.../fronted/index.html
   ```

Asegúrate de que la constante `API_BASE` de `app.js` apunta correctamente al backend:

```js
const API_BASE = "http://127.0.0.1:8000";
```

Si cambias el puerto o la IP, actualiza esta línea.

---

## 🧪 Uso básico

1. Abre el frontend (`index.html`).
2. Elige el origen:

   * **Audio del sistema** (compartir pestaña/ventana + marcar “Compartir audio”)
   * **Micrófono**
3. Ajusta el tamaño del *chunk* (por defecto 4 s).
4. Pulsa **▶ Iniciar**:

   * El navegador pedirá permisos para capturar audio.
   * El backend irá recibiendo *chunks* y actualizando la transcripción.
5. Usa los controles:

   * ⏸ **Pausar** / reanudar la captura
   * ■ **Detener** para terminar la sesión
   * 📋 **Copiar** para copiar todo el texto
   * 🧹 **Limpiar caja** para vaciar la transcripción
6. Para descargar:

   * **TXT**: `http://127.0.0.1:8000/api/transcript.txt`
   * **SRT**: `http://127.0.0.1:8000/api/transcript.srt`

---

## 📡 Endpoints principales (API)

| Método | Ruta                  | Descripción                                                 |
| ------ | --------------------- | ----------------------------------------------------------- |
| GET    | `/ping`               | Comprobación rápida del backend (modelo, dispositivo, etc.) |
| GET    | `/api/reset`          | Reinicia la sesión y borra el acumulado de audio            |
| POST   | `/api/chunk`          | Recibe un *chunk* de audio (`file`) y lo transcribe         |
| GET    | `/api/transcript.txt` | Devuelve la transcripción completa en texto plano           |
| GET    | `/api/transcript.srt` | Devuelve la transcripción completa en formato SRT           |

`/api/chunk` espera:

* `file`: audio (`.webm` o `.wav`) vía `multipart/form-data`
* `offset`: (opcional) inicio del *chunk* en segundos

La lógica del buffer y las marcas de tiempo está en `chunk_buffer.py`.

---

## 🔧 Configuración del glosario / contexto

En `backend/app.py` hay una constante:

```python
PROMPT_EXTRA = (
    "informática hardware software placa base placas base buses de datos "
    "procesadores CPU GPU memoria RAM almacenamiento SSD disco duro SATA NVMe "
    "interfaces USB HDMI PCIe chipset BIOS UEFI audio digital analógico "
    "altavoces micrófono periféricos teclado ratón monitor "
)
```

Puedes adaptarla a tu contexto de clase (derecho, medicina, logística, etc.) para ayudar al modelo a entender mejor la terminología de tu asignatura.

---

## 📄 Documentación adicional

En la carpeta `documentación/` tienes:

* `Manual_de_Usuario_Transcriptor.odt`: manual detallado de uso.
* `portada.png`, `portada2.png`: recursos gráficos para presentación o documentación.

---

## 👤 Autor

**Piero Olivares**

Proyecto creado para practicar captura de audio en navegador, FastAPI y transcripción con modelos Whisper.

---
