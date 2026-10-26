"""HTTP transport only. Synchronous handlers run processing in FastAPI's worker pool."""

import json
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi import Response as CookieResponse
from fastapi.responses import Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile as FormUploadFile

from .access import Principal, fail
from .catalog import demo
from .domain import BlueprintInput
from .errors import DesignError
from .example_projects import example_csv
from .services import CatalogService, DesignService


def get_principal(request: Request) -> Principal:
    return request.app.state.account_service.principal(
        request.cookies.get("fair_session"), allow_password_change=False
    )


Identity = Annotated[Principal, Depends(get_principal)]
router = APIRouter(prefix="/api", dependencies=[Depends(get_principal)])
auth_router = APIRouter(prefix="/api/auth")


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
    max_dimension_size: int
    max_dataset_elements: int


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
    fail(403, "global_template_read_only", "Create templates inside a project.")


class TemplateRevision(BaseModel):
    expected_revision: int
    template: dict[str, Any]


@router.post("/catalog/{identifier}/revisions", status_code=201)
def publish_revision(identifier: str, body: TemplateRevision, service: Catalog):
    fail(
        403, "global_template_read_only", "Shared templates are read-only. Copy one into a project."
    )


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


@router.post("/export/rdf")
def export_metadata(service: Service, blueprint: BlueprintInput):
    return Response(
        service.rdf(blueprint),
        media_type="text/turtle",
        headers={"Content-Disposition": 'attachment; filename="experiment.metadata.ttl"'},
    )


def json_object(raw, limit):
    if len(raw.encode("utf-8")) > limit:
        from .errors import UploadTooLarge

        raise UploadTooLarge("The JSON form field is too large.")
    try:
        value = json.loads(raw)
    except (ValueError, RecursionError) as exc:
        raise DesignError("Invalid JSON form field.") from exc
    if not isinstance(value, dict):
        raise DesignError("Expected a JSON object.")
    return value


@router.post("/data/csv/preview")
def csv_preview(service: Service, settings_json: str = Form(...), file: UploadFile = File(...)):
    try:
        return service.csv_preview(
            file.file, json_object(settings_json, service.settings.max_blueprint_bytes)
        )
    finally:
        file.file.close()


@router.post("/export/hdf5/data")
async def export_hdf5_data(request: Request, service: Service):
    async with request.form(
        max_files=service.settings.max_nodes,
        max_fields=1,
        max_part_size=service.settings.max_blueprint_bytes,
    ) as form:
        raw = form.get("design_json")
        if not isinstance(raw, str):
            raise DesignError("Missing design_json form field.")
        files = {}
        for key, item in form.multi_items():
            if key == "design_json" and isinstance(item, str):
                continue
            if not isinstance(item, FormUploadFile) or key in files:
                raise DesignError("Expected one CSV file per source node ID.")
            files[key] = item.file
        content = await run_in_threadpool(
            service.data_file, json_object(raw, service.settings.max_blueprint_bytes), files
        )
        return Response(
            content,
            media_type="application/x-hdf5",
            headers={"Content-Disposition": 'attachment; filename="experiment-data.h5"'},
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


def set_session_cookie(request: Request, response: CookieResponse, token: str):
    response.set_cookie(
        "fair_session",
        token,
        httponly=True,
        secure=request.app.state.settings.cookie_secure,
        samesite="lax",
        max_age=request.app.state.settings.session_seconds,
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"


@auth_router.get("/session")
def session(request: Request, response: CookieResponse):
    token, data = request.app.state.account_service.session(request.cookies.get("fair_session"))
    set_session_cookie(request, response, token)
    return data


class LoginInput(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(max_length=128)


@auth_router.post("/login")
def login(body: LoginInput, request: Request, response: CookieResponse):
    token, data = request.app.state.account_service.login(
        body.username,
        body.password,
        request.client.host if request.client else "unknown",
        request.cookies.get("fair_session"),
    )
    set_session_cookie(request, response, token)
    return data


@auth_router.post("/logout")
def logout(request: Request, response: CookieResponse):
    accounts = request.app.state.account_service
    accounts.logout(accounts.principal(request.cookies.get("fair_session")))
    response.delete_cookie("fair_session", path="/")
    return {"signed_out": True}


class PasswordInput(BaseModel):
    old_password: str = Field(max_length=128)
    new_password: str = Field(max_length=128)


@auth_router.post("/password")
def change_password(body: PasswordInput, request: Request, response: CookieResponse):
    accounts = request.app.state.account_service
    token, data = accounts.change_password(
        accounts.principal(request.cookies.get("fair_session")),
        body.old_password,
        body.new_password,
    )
    set_session_cookie(request, response, token)
    return data


class CreateUserInput(BaseModel):
    username: str
    display_name: str
    is_admin: bool = False


@router.get("/admin/users")
def users(request: Request, principal: Identity):
    return request.app.state.account_service.list_users(principal)


@router.post("/admin/users", status_code=201)
def create_user(body: CreateUserInput, request: Request, principal: Identity):
    accounts = request.app.state.account_service
    temporary = accounts.temporary_password()
    identifier = accounts.create_user(
        body.username, body.display_name, temporary, is_admin=body.is_admin, principal=principal
    )
    return {"id": identifier, "temporary_password": temporary}


class ActiveInput(BaseModel):
    active: bool


@router.patch("/admin/users/{identifier}")
def activate_user(identifier: str, body: ActiveInput, request: Request, principal: Identity):
    request.app.state.account_service.set_active(principal, identifier, body.active)
    return {"active": body.active}


@router.post("/admin/users/{identifier}/password")
def reset_password(identifier: str, request: Request, principal: Identity):
    return {
        "temporary_password": request.app.state.account_service.reset_password(
            principal, identifier
        )
    }


class CreateProjectInput(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=3000)
    blueprint: dict[str, Any] | None = None
    source_id: str | None = None
    import_key: str | None = Field(default=None, max_length=100)


@router.get("/projects")
def projects(request: Request, principal: Identity):
    return request.app.state.project_service.list(principal)


@router.get("/examples/files/measurements.csv")
def download_example_csv():
    return Response(
        example_csv(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="measurements.csv"'},
    )


@router.get("/examples")
def examples(request: Request):
    return request.app.state.example_service.list()


@router.get("/examples/{identifier}")
def example(identifier: str, request: Request):
    return request.app.state.example_service.get(identifier)


@router.post("/examples/{identifier}/copy", status_code=201)
def copy_example(identifier: str, request: Request, principal: Identity):
    selected = request.app.state.example_service.get(identifier)
    return request.app.state.project_service.create(
        principal, selected["name"], selected["description"], blueprint=selected["blueprint"]
    )


@router.post("/projects", status_code=201)
def create_project(body: CreateProjectInput, request: Request, principal: Identity):
    return request.app.state.project_service.create(principal, **body.model_dump())


@router.get("/projects/{identifier}")
def project(identifier: str, request: Request, principal: Identity):
    return request.app.state.project_service.get(principal, identifier)


class SaveProjectInput(BaseModel):
    blueprint: dict[str, Any]
    description: str = Field(default="", max_length=3000)
    expected_revision: int = Field(ge=1)


@router.put("/projects/{identifier}")
def save_project(identifier: str, body: SaveProjectInput, request: Request, principal: Identity):
    return request.app.state.project_service.save(
        principal,
        identifier,
        request.headers.get("X-Edit-Lease"),
        body.expected_revision,
        body.blueprint,
        body.description,
    )


@router.delete("/projects/{identifier}")
def delete_project(identifier: str, request: Request, principal: Identity):
    request.app.state.project_service.delete(principal, identifier)
    return {"deleted": True}


class AcquireLockInput(BaseModel):
    editor_id: str = Field(min_length=1, max_length=100)


@router.get("/projects/{identifier}/edit-lock")
def edit_lock(identifier: str, request: Request, principal: Identity):
    return request.app.state.project_service.lock(principal, identifier, "status")


@router.post("/projects/{identifier}/edit-lock")
def acquire_lock(identifier: str, body: AcquireLockInput, request: Request, principal: Identity):
    return request.app.state.project_service.lock(
        principal, identifier, "acquire", editor_id=body.editor_id
    )


@router.post("/projects/{identifier}/edit-lock/renew")
def renew_lock(identifier: str, request: Request, principal: Identity):
    return request.app.state.project_service.lock(
        principal, identifier, "renew", request.headers.get("X-Edit-Lease")
    )


@router.delete("/projects/{identifier}/edit-lock")
def release_lock(identifier: str, request: Request, principal: Identity):
    return request.app.state.project_service.lock(
        principal, identifier, "release", request.headers.get("X-Edit-Lease")
    )


@router.get("/projects/{identifier}/members")
def project_members(identifier: str, request: Request, principal: Identity):
    return request.app.state.project_service.members(principal, identifier)


class MemberInput(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    role: Literal["editor", "viewer"] | None


@router.put("/projects/{identifier}/members")
def change_member(identifier: str, body: MemberInput, request: Request, principal: Identity):
    return request.app.state.project_service.change_member(
        principal, identifier, body.username, body.role
    )


def scoped_catalog(request, principal, identifier, revision=None):
    return request.app.state.project_service.catalog_service(
        principal, identifier, request.headers.get("X-Edit-Lease"), revision
    )


@router.get("/projects/{identifier}/catalog")
def project_catalog(identifier: str, request: Request, principal: Identity):
    return scoped_catalog(request, principal, identifier).catalog()


class ProjectTemplateInput(BaseModel):
    template: dict[str, Any]
    expected_revision: int = Field(ge=1)
    expected_template_revision: int | None = None


@router.post("/projects/{identifier}/catalog", status_code=201)
def create_project_template(
    identifier: str, body: ProjectTemplateInput, request: Request, principal: Identity
):
    return scoped_catalog(request, principal, identifier, body.expected_revision).publish(
        body.template
    )


@router.post("/projects/{identifier}/catalog/{template_id}/revisions", status_code=201)
def revise_project_template(
    identifier: str,
    template_id: str,
    body: ProjectTemplateInput,
    request: Request,
    principal: Identity,
):
    return scoped_catalog(request, principal, identifier, body.expected_revision).publish(
        body.template, template_id, body.expected_template_revision
    )


@router.get("/projects/{identifier}/catalog/{template_id}/revisions/{revision}")
def project_template_revision(
    identifier: str, template_id: str, revision: int, request: Request, principal: Identity
):
    return scoped_catalog(request, principal, identifier).get_revision(template_id, revision)
