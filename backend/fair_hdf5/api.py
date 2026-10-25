"""HTTP transport only. Synchronous handlers run processing in FastAPI's worker pool."""

import json
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .catalog import demo
from .domain import BlueprintInput
from .errors import DesignError
from .services import CatalogService, DesignService

router = APIRouter(prefix="/api")


def get_service(request: Request) -> DesignService:
    return request.app.state.design_service


Service = Annotated[DesignService, Depends(get_service)]


def get_catalog_service(request: Request) -> CatalogService:
    return request.app.state.catalog_service


Catalog = Annotated[CatalogService, Depends(get_catalog_service)]


class CapabilitiesOutput(BaseModel):
    max_nodes: int
    max_edges: int
    max_upload_bytes: int
    shacl_engine: Literal["pyshacl", "subset"]


@router.get("/catalog")
def catalog(service: Catalog):
    return service.catalog()


class ProfileImport(BaseModel):
    ttl: str
    source_uri: str | None = None
    documents: dict[str, Any] = Field(default_factory=dict)


@router.post("/catalog/analyze")
def analyze_profile(body: ProfileImport, service: Catalog):
    return service.analyze(body.ttl, body.source_uri, body.documents)


@router.post("/catalog", status_code=201)
def create_template(body: dict[str, Any], service: Catalog):
    return service.publish(body)


class TemplateRevision(BaseModel):
    expected_revision: int
    template: dict[str, Any]


@router.post("/catalog/{identifier}/revisions", status_code=201)
def publish_revision(identifier: str, body: TemplateRevision, service: Catalog):
    return service.publish(body.template, identifier, body.expected_revision)


@router.get("/catalog/{identifier}/revisions/{revision}")
def get_revision(identifier: str, revision: int, service: Catalog):
    return service.get_revision(identifier, revision)


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
    return Response(
        service.shacl(blueprint),
        media_type="text/turtle",
        headers={"Content-Disposition": 'attachment; filename="hdf5-design.shacl.ttl"'},
    )


@router.post("/export/hdf5")
def export_hdf5(service: Service, blueprint: BlueprintInput):
    return Response(
        service.template(blueprint),
        media_type="application/x-hdf5",
        headers={"Content-Disposition": 'attachment; filename="experiment-template.h5"'},
    )


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
