"""import os
import shutil
from fastapi import FastAPI, File, UploadFile, Request
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from pipeline import run_pipeline_on_uploaded_csv, get_history

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
REPORT_DIR = os.path.join(BASE_DIR, "static", "reports")
CHART_DIR  = os.path.join(BASE_DIR, "static", "charts")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)
os.makedirs(CHART_DIR, exist_ok=True)

app = FastAPI(title="AI Calibration Platform API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload_csv/")
async def upload_csv(file: UploadFile = File(...)):
    save_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        result = run_pipeline_on_uploaded_csv(save_path)
    except Exception as e:
        import traceback
        return JSONResponse({"error": str(e), "trace": traceback.format_exc()}, status_code=500)

    # Convert paths to frontend URLs
    pdf_url = None
    if "report_files" in result and result["report_files"].get("pdf"):
        pdf_url = result["report_files"]["pdf"].replace("\\", "/").replace("^.*static/", "/static/")

    chart_files = result.get("chart_files", {})
    for k, v in chart_files.items():
        chart_files[k] = v.replace("\\", "/").replace("^.*static/", "/static/")

    return {
        "processed_csv": result.get("processed_csv"),
        "report_files": result.get("report_files"),
        "report_pdf_url": pdf_url,
        "chart_files": chart_files,
        "alerts": result.get("alerts", [])
    }

@app.get("/download_report/{fname}")
def download_report(fname: str):
    fpath = os.path.join(REPORT_DIR, fname)
    if not os.path.exists(fpath):
        return JSONResponse({"error": "file not found"}, status_code=404)
    return FileResponse(fpath, media_type="application/pdf", filename=fname)

@app.get("/history/")
def history(limit: int = 200):
    try:
        df = get_history(limit=limit)
    except Exception as e:
        import traceback
        return JSONResponse({"error": str(e), "trace": traceback.format_exc()}, status_code=500)
    return df.to_dict(orient="records")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

# app.py
import os
from fastapi import FastAPI, File, UploadFile, Request
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import shutil
import uvicorn

# Import pipeline functions
from pipeline import run_pipeline_on_uploaded_csv, get_history  

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
REPORT_DIR = os.path.join(BASE_DIR, "static", "reports")
CHART_DIR  = os.path.join(BASE_DIR, "static", "charts")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)
os.makedirs(CHART_DIR, exist_ok=True)

app = FastAPI(title="AI Calibration Platform API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ⚠️ for dev only, restrict later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (charts + reports)
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload_csv/")
async def upload_csv(file: UploadFile = File(...)):
    save_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        result = run_pipeline_on_uploaded_csv(save_path)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

    # --- Format response for React frontend ---
    alerts = result.get("alerts", [])
    report_files = result.get("report_files", {})
    chart_files = result.get("chart_files", {})

    # Fix paths to be accessible via /static/
    def make_static_url(path):
        if path and "static" in path:
            return "/" + os.path.relpath(path, BASE_DIR).replace("\\", "/")
        return None

    pdf_url = make_static_url(report_files.get("pdf"))
    drift_url = make_static_url(chart_files.get("drift"))
    rul_url = make_static_url(chart_files.get("rul_health"))

    return {
        "alerts": alerts,
        "report_pdf_url": pdf_url,
        "chart_files": {
            "drift": drift_url,
            "rul_health": rul_url
        }
    }

@app.get("/download_report/{fname}")
def download_report(fname: str):
    fpath = os.path.join(REPORT_DIR, fname)
    if not os.path.exists(fpath):
        return JSONResponse({"error": "file not found"}, status_code=404)
    return FileResponse(fpath, media_type="application/pdf", filename=fname)

@app.get("/history/")
def history(limit: int = 200):
    try:
        df = get_history(limit=limit)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    return df.to_dict(orient="records")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
"""

import os
import shutil
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from pipeline import run_pipeline_on_uploaded_csv, get_history

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
REPORT_DIR = os.path.join(BASE_DIR, "static", "reports")
CHART_DIR = os.path.join(BASE_DIR, "static", "charts")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)
os.makedirs(CHART_DIR, exist_ok=True)

app = FastAPI(title="AI Calibration Platform API")

# Enable CORS for standalone HTML frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # for dev, allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static charts/reports
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")


@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    """
    Serve the standalone calibration_frontend.html file.
    Place calibration_frontend.html in the BASE_DIR or /templates.
    """
    fpath = os.path.join(BASE_DIR, "templates", "calibration_frontend.html")
    if not os.path.exists(fpath):
        return HTMLResponse("<h2>Frontend file not found</h2>", status_code=404)
    return FileResponse(fpath)

'''
@app.post("/upload_csv/")
async def upload_csv(file: UploadFile = File(...)):
    save_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        result = run_pipeline_on_uploaded_csv(save_path)
    except Exception as e:
        import traceback
        return JSONResponse({"error": str(e), "trace": traceback.format_exc()}, status_code=500)

    # Convert local paths → URLs usable by frontend
    pdf_url = None
    if "report_files" in result and result["report_files"].get("pdf"):
        pdf_path = result["report_files"]["pdf"]
        pdf_url = "/static/reports/" + os.path.basename(pdf_path)

    chart_urls = []
    chart_files = result.get("chart_files", {})
    for _, v in chart_files.items():
        chart_urls.append("/static/charts/" + os.path.basename(v))

    return {
        "alerts": result.get("alerts", []),
        "report_pdf_url": pdf_url,
        "chart_urls": chart_urls
    }'''


@app.post("/upload_csv/")
async def upload_csv(file: UploadFile = File(...)):
    save_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        result = run_pipeline_on_uploaded_csv(save_path)
    except Exception as e:
        import traceback
        return JSONResponse(
            {"error": str(e), "trace": traceback.format_exc()},
            status_code=500
        )

    # Convert local paths → frontend URLs
    pdf_url = None
    if "report_files" in result and result["report_files"].get("pdf"):
        pdf_path = result["report_files"]["pdf"]
        pdf_url = "/static/reports/" + os.path.basename(pdf_path)

    # Preserve chart keys (drift, rul_health, etc.)
    chart_files = {}
    for k, v in result.get("chart_files", {}).items():
        chart_files[k] = "/static/charts/" + os.path.basename(v)

    return {
        "alerts": result.get("alerts", []),
        "report_pdf_url": pdf_url,
        "chart_files": chart_files
    }



@app.get("/download_report/{fname}")
def download_report(fname: str):
    fpath = os.path.join(REPORT_DIR, fname)
    if not os.path.exists(fpath):
        return JSONResponse({"error": "file not found"}, status_code=404)
    return FileResponse(fpath, media_type="application/pdf", filename=fname)


@app.get("/history/")
def history(limit: int = 200):
    try:
        df = get_history(limit=limit)
    except Exception as e:
        import traceback
        return JSONResponse({"error": str(e), "trace": traceback.format_exc()}, status_code=500)
    return df.to_dict(orient="records")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
