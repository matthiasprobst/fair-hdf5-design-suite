"""HTTP API and single-page frontend for the FAIR HDF5 Design Suite POC."""
from __future__ import annotations
import json
from pathlib import Path
from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from backend import CATALOG, demo, hdf5_template, shacl_turtle, structure_preview, validate_hdf5

HERE = Path(__file__).resolve().parent
app = FastAPI(title="FAIR HDF5 Design Suite", version="0.1.0-beta.1")
# React's production bundle is served by FastAPI after npm run build.
FRONTEND_DIST = HERE / "frontend" / "dist"
if (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="react-assets")


class Blueprint(BaseModel):
    name: str = "Untitled experiment"
    version: str = "0.1"
    nodes: list[dict]
    edges: list[dict] = []


def call(fn, *args):
    try:
        return fn(*args)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/")
def home():
    if (FRONTEND_DIST / "index.html").exists():
        return FileResponse(FRONTEND_DIST / "index.html")
    raise HTTPException(
        status_code=503,
        detail="React frontend is not built. Run 'npm ci && npm run build' in the frontend directory, or use the Vite development server.",
    )


@app.get("/health")
def health():
    return {"status": "ok", "version": app.version, "react_built": (FRONTEND_DIST / "index.html").exists()}


@app.get("/api/catalog")
def get_catalog():
    return {"catalog": CATALOG, "profile_source": "Illustrative local profiles, not live NFDI4Ing MPS profiles"}


@app.get("/api/demo")
def get_demo():
    return demo()


@app.post("/api/preview")
def get_preview(blueprint: Blueprint):
    return call(structure_preview, blueprint.model_dump())


@app.post("/api/export/shacl")
def export_shacl(blueprint: Blueprint):
    ttl = call(shacl_turtle, blueprint.model_dump())
    return Response(ttl, media_type="text/turtle", headers={"Content-Disposition": 'attachment; filename="hdf5-design.shacl.ttl"'})


@app.post("/api/export/hdf5")
def export_hdf5(blueprint: Blueprint):
    content = call(hdf5_template, blueprint.model_dump())
    return Response(content, media_type="application/x-hdf5", headers={"Content-Disposition": 'attachment; filename="experiment-template.h5"'})


@app.post("/api/validate/template")
def validate_template(blueprint: Blueprint):
    design = blueprint.model_dump()
    content = call(hdf5_template, design)
    return call(validate_hdf5, design, content)


@app.post("/api/validate/file")
async def validate_file(design_json: str = Form(...), file: UploadFile = File(...)):
    try:
        design = json.loads(design_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="Invalid design JSON.") from exc
    content = await file.read(30_000_001)
    if len(content) > 30_000_000:
        raise HTTPException(status_code=413, detail="POC validation upload limit is 30 MB.")
    return call(validate_hdf5, design, content)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
