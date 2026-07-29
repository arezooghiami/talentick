"""اجرای uvicorn برای توسعه محلی — cwd را به backend/ تغییر می‌دهد تا .env درست پیدا شود."""
import logging
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
logging.basicConfig(level=logging.INFO)

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
