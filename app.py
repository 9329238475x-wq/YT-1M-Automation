import os
import sys
import socket

print("=== STARTUP ENV CHECK ===", flush=True)
print(f"Python: {sys.version}", flush=True)
print(f"PORT env var: {os.environ.get('PORT')}", flush=True)

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
res = s.connect_ex(('127.0.0.1', 7860))
print(f"Is port 7860 already in use?: {res == 0}", flush=True)
s.close()

from backend.server import app

# ZeroGPU hook
try:
    import spaces
    @spaces.GPU
    def gpu_task_worker():
        return True
except Exception:
    pass

import uvicorn
# Use PORT or 7860
port = int(os.environ.get("PORT", 7860))
if res == 0:
    print("Port 7860 was already in use! Trying port 7861...", flush=True)
    port = 7861

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=port)
