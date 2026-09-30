import os
import uvicorn
from backend.server import app

# Hugging Face Spaces default port is 7860
port = int(os.environ.get("PORT", 7860))

if __name__ == "__main__":
    uvicorn.run("backend.server:app", host="0.0.0.0", port=port, reload=False)
