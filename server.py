import asyncio
import threading
import sys
import os
import pyaudiowpatch as pyaudio
import numpy as np
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse
from contextlib import asynccontextmanager

TARGET_DEVICE_ID = None
TARGET_SAMPLE_RATE = 48000
active_connections: set[WebSocket] = set()

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(__file__), relative_path)

def audio_capture_thread(loop):
    global TARGET_SAMPLE_RATE
    p = pyaudio.PyAudio()
    stream = None
    try:
        device_idx = TARGET_DEVICE_ID
        if device_idx == 'default':
            wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
            default_speakers = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
            for loopback in p.get_loopback_device_info_generator():
                if default_speakers["name"] in loopback["name"]:
                    device_idx = loopback["index"]
                    break

        dev_info = p.get_device_info_by_index(device_idx)
        channels = dev_info["maxInputChannels"]
        TARGET_SAMPLE_RATE = int(dev_info["defaultSampleRate"])

        # 縮小 chunk 以降低延遲
        chunk_size = 1024

        stream = p.open(format=pyaudio.paInt16, channels=channels, rate=TARGET_SAMPLE_RATE,
                        input=True, input_device_index=device_idx, frames_per_buffer=chunk_size)

        while True:
            data = stream.read(chunk_size, exception_on_overflow=False)
            if channels == 1:
                arr = np.frombuffer(data, dtype=np.int16)
                data = np.repeat(arr, 2).tobytes()

            if active_connections:
                asyncio.run_coroutine_threadsafe(broadcast_audio(data), loop)

    except Exception as e:
        print(f"擷取錯誤: {e}")
    finally:
        if stream: stream.close()
        p.terminate()

async def broadcast_audio(data: bytes):
    if not active_connections: return

    async def send_to_client(ws):
        try:
            # ⚡ 洩壓閥：傳送超時就丟棄封包，保證不囤積舊聲音
            await asyncio.wait_for(ws.send_bytes(data), timeout=0.04)
        except Exception:
            active_connections.discard(ws)

    tasks = [send_to_client(ws) for ws in list(active_connections)]
    await asyncio.gather(*tasks)

@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_running_loop()
    threading.Thread(target=audio_capture_thread, args=(loop,), daemon=True).start()
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def index():
    with open(resource_path("client.html"), "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/config")
async def config():
    return JSONResponse({"sample_rate": TARGET_SAMPLE_RATE})

@app.websocket("/ws")
async def audio_ws(websocket: WebSocket):
    await websocket.accept()
    active_connections.add(websocket)
    try:
        while True:
            await websocket.receive()
    except:
        pass
    finally:
        active_connections.discard(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="error")