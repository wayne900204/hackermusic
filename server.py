import asyncio
import threading
import queue
import sys
import os
import pyaudiowpatch as pyaudio
import numpy as np
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse
from contextlib import asynccontextmanager

TARGET_DEVICE_ID = None
TARGET_SAMPLE_RATE = 48000
clients = set()


def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(__file__), relative_path)


def audio_capture_thread():
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
        chunk_size = int(TARGET_SAMPLE_RATE * 0.02)

        stream = p.open(format=pyaudio.paInt16, channels=channels, rate=TARGET_SAMPLE_RATE,
                        input=True, input_device_index=device_idx, frames_per_buffer=chunk_size)

        while True:
            data = stream.read(chunk_size, exception_on_overflow=False)
            if channels == 1:
                arr = np.frombuffer(data, dtype=np.int16)
                data = np.repeat(arr, 2).tobytes()
            for q in list(clients):
                if not q.full(): q.put_nowait(data)
    except Exception as e:
        print(f"擷取錯誤: {e}")
    finally:
        if stream: stream.close()
        p.terminate()


@asynccontextmanager
async def lifespan(app: FastAPI):
    threading.Thread(target=audio_capture_thread, daemon=True).start()
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
    q = queue.Queue(maxsize=10)
    clients.add(q)
    try:
        while True:
            data = q.get()
            await websocket.send_bytes(data)
    except:
        pass
    finally:
        clients.remove(q)