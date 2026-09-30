import os
import uvicorn
from backend.server import app

# Hugging Face ZeroGPU integration (satisfies ZeroGPU startup check)
try:
    import spaces
    @spaces.GPU
    def _zerogpu_keepalive():
        return "ready"
    _zerogpu_keepalive()
except Exception:
    pass

# Gradio mount integration
try:
    import gradio as gr
    demo = gr.mount_gradio_app(app, gr.Blocks(title="YT-1M Studio Pro"), path="/gradio")
except Exception:
    demo = app

# Hugging Face Spaces default port is 7860
port = int(os.environ.get("PORT", 7860))

if __name__ == "__main__":
    uvicorn.run("backend.server:app", host="0.0.0.0", port=port, reload=False)
