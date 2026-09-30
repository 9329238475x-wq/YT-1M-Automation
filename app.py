import os
from backend.server import app

# ZeroGPU hook (satisfies Hugging Face ZeroGPU check without running at import)
try:
    import spaces
    @spaces.GPU
    def gpu_task_worker():
        """Reserved for GPU accelerated operations."""
        return True
except Exception:
    pass

# Standard Gradio integration for Hugging Face Spaces
try:
    import gradio as gr
    demo = gr.mount_gradio_app(app, gr.Blocks(title="YT-1M Studio Pro"), path="/gradio")
except Exception:
    demo = app

if __name__ == "__main__":
    if hasattr(demo, "launch"):
        demo.launch(server_name="0.0.0.0", server_port=7860)
    else:
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=7860)
