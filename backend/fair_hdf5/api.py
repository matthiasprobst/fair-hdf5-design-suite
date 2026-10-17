"""HTTP transport only. Synchronous handlers run processing in FastAPI's worker pool."""
import json
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, File, Form, Request, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from .catalog import CATALOG, demo
from .domain import BlueprintInput
from .errors import DesignError
from .services import DesignService

router = APIRouter(prefix="/api")


def get_service(request: Request) -> DesignService:
    return request.app.state.design_service


Service = Annotated[DesignService, Depends(get_service)]


class CapabilitiesOutput(BaseModel):
    max_nodes: int
    max_edges: int
    max_upload_bytes: int
    shacl_engine: Literal["pyshacl", "subset"]


@router.get("/catalog")
def catalog(service: Service):
    return {"catalog": service.repository.catalog(), "legacy_catalog": {key:service.repository.get(key, 1) for key in CATALOG}, "profile_source": "Persistent local SHACL library; MPS file import supported"}


class ProfileImport(BaseModel):
    ttl: str


@router.post("/catalog/analyze")
def analyze_profile(body: ProfileImport):
    from .profile_schema import analyze_profile
    return analyze_profile(body.ttl)


@router.post("/catalog", status_code=201)
def create_template(body: dict, service: Service):
    if service.settings.shacl_engine != "pyshacl":
        raise DesignError("Custom profiles require pyshacl.")
    return service.repository.publish(body)


class TemplateRevision(BaseModel):
    expected_revision: int
    template: dict


@router.post("/catalog/{identifier}/revisions", status_code=201)
def publish_revision(identifier: str, body: TemplateRevision, service: Service):
    from .library import RevisionConflict
    if service.settings.shacl_engine != "pyshacl": raise DesignError("Custom profiles require pyshacl.")
    try:
        return service.repository.publish(body.template, identifier, body.expected_revision)
    except RevisionConflict as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/catalog/{identifier}/revisions/{revision}")
def get_revision(identifier: str, revision: int, service: Service):
    return service.repository.get(identifier, revision)


@router.get("/demo")
def get_demo(service: Service):
    return service.normalize(demo())


@router.get("/capabilities", response_model=CapabilitiesOutput)
def capabilities(service: Service):
    return service.settings.capabilities()


@router.post("/preview")
def preview(service: Service, blueprint: BlueprintInput):
    return service.preview(blueprint)


@router.post("/export/shacl")
def export_shacl(service: Service, blueprint: BlueprintInput):
    return Response(service.shacl(blueprint), media_type="text/turtle",
                    headers={"Content-Disposition": 'attachment; filename="hdf5-design.shacl.ttl"'})


@router.post("/export/hdf5")
def export_hdf5(service: Service, blueprint: BlueprintInput):
    return Response(service.template(blueprint), media_type="application/x-hdf5",
                    headers={"Content-Disposition": 'attachment; filename="experiment-template.h5"'})


@router.post("/validate/template")
def validate_template(service: Service, blueprint: BlueprintInput):
    return service.validate_template(blueprint)


@router.post("/validate/file")
def validate_file(service: Service, design_json: str = Form(...), file: UploadFile = File(...)):
    try:
        try:
            blueprint = json.loads(design_json)
        except (ValueError, RecursionError) as exc:
            raise DesignError("Invalid design JSON.") from exc
        return service.validate_upload(blueprint, file.file)
    finally:
        file.file.close()
