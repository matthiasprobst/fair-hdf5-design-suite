"""Project policy, membership and transactional editing leases."""

import json
import secrets
import time
from uuid import uuid4

from .access import ApplicationError, fail
from .account_service import current_user, digest
from .example_projects import bundled_examples
from .project_blueprint import editable_blueprint


def project_access(connection, principal, project_id, *, owner=False):
    current_user(connection, principal)
    row = connection.execute(
        "SELECT p.*, u.display_name AS owner_name, COALESCE(m.role, '') AS member_role, "
        "EXISTS(SELECT 1 FROM project_members WHERE project_id=p.id) AS shared, e.example_id "
        "FROM projects p JOIN users u ON u.id=p.owner_id "
        "LEFT JOIN user_examples e ON e.project_id=p.id "
        "LEFT JOIN project_members m ON m.project_id=p.id AND m.user_id=? WHERE p.id=?",
        (principal.user_id, project_id),
    ).fetchone()
    if not row or (row["owner_id"] != principal.user_id and not row["member_role"]):
        fail(404, "project_not_found", "Project not found or no longer shared with you.")
    if owner and row["owner_id"] != principal.user_id:
        fail(403, "owner_required", "Only the project owner can do this.")
    return row


def project_metadata(row, user_id):
    return {
        key: row[key]
        for key in (
            "id",
            "name",
            "description",
            "owner_id",
            "owner_name",
            "revision",
            "created_at",
            "updated_at",
        )
    } | {
        "role": "owner" if row["owner_id"] == user_id else row["member_role"],
        "shared": bool(row["shared"]),
        "example_id": row["example_id"],
    }


def active_lock(connection, project_id):
    return connection.execute(
        "SELECT l.*, u.id AS user_id, u.display_name FROM edit_locks l "
        "JOIN sessions s ON s.id=l.session_id JOIN users u ON u.id=s.user_id "
        "WHERE l.project_id=? AND l.expires_at>? AND s.expires_at>? AND u.active=1",
        (project_id, time.time(), time.time()),
    ).fetchone()


def lock_summary(row):
    return (
        {
            "user_id": row["user_id"],
            "display_name": row["display_name"],
            "expires_at": row["expires_at"],
        }
        if row
        else None
    )


def require_edit(connection, principal, project_id, token, revision):
    project = project_access(connection, principal, project_id)
    if project["owner_id"] != principal.user_id and project["member_role"] != "editor":
        fail(403, "read_only", "This project is read-only.")
    lease = active_lock(connection, project_id)
    if (
        not lease
        or lease["session_id"] != principal.session_id
        or not secrets.compare_digest(lease["token_hash"], digest(token or ""))
    ):
        fail(
            423,
            "lease_lost",
            "Editing has stopped. Acquire a new editing reservation before saving.",
        )
    if project["revision"] != revision:
        fail(
            409,
            "revision_conflict",
            "The saved project changed. Reload it or save your draft as a private copy.",
        )
    return project


class ProjectService:
    def __init__(self, database, settings, global_catalog):
        self.database, self.settings, self.global_catalog = database, settings, global_catalog

    def ensure_examples(self, principal):
        """Provision once, including existing accounts; deletion retains the receipt."""
        with self.database.transaction() as connection:
            current_user(connection, principal)
            installed = {
                row["example_id"]
                for row in connection.execute(
                    "SELECT example_id FROM user_examples WHERE user_id=?", (principal.user_id,)
                )
            }
        pending = []
        for example in bundled_examples():
            if example["id"] in installed:
                continue
            try:
                content = editable_blueprint(
                    example["blueprint"], self.settings, self.global_catalog
                )
            except ApplicationError as error:
                if error.code in {"graph_limit", "blueprint_too_large"}:
                    continue
                raise
            pending.append((example, content))
        if not pending:
            return
        with self.database.transaction(write=True) as connection:
            current_user(connection, principal)
            for example, content in pending:
                if connection.execute(
                    "SELECT 1 FROM user_examples WHERE user_id=? AND example_id=?",
                    (principal.user_id, example["id"]),
                ).fetchone():
                    continue
                identifier, now = str(uuid4()), time.time()
                connection.execute(
                    "INSERT INTO projects VALUES (?,?,?,?,?,1,?,?,NULL)",
                    (
                        identifier,
                        principal.user_id,
                        content["name"],
                        example["description"],
                        json.dumps(content, ensure_ascii=False),
                        now,
                        now,
                    ),
                )
                connection.execute(
                    "INSERT INTO user_examples VALUES (?,?,?,?)",
                    (principal.user_id, example["id"], identifier, now),
                )

    def catalog_service(self, principal, project_id, token=None, revision=None):
        from .project_catalog import ScopedCatalogRepository
        from .services import CatalogService

        with self.database.transaction() as connection:
            if revision is None:
                project_access(connection, principal, project_id)
            else:
                require_edit(connection, principal, project_id, token, revision)
        return CatalogService(
            self.settings,
            ScopedCatalogRepository(self, principal, project_id, token=token, revision=revision),
        )

    def list(self, principal):
        self.ensure_examples(principal)
        with self.database.transaction() as connection:
            current_user(connection, principal)
            rows = connection.execute(
                "SELECT p.*, u.display_name AS owner_name, COALESCE(m.role, '') AS member_role, "
                "EXISTS(SELECT 1 FROM project_members WHERE project_id=p.id) AS shared, e.example_id "
                "FROM projects p JOIN users u ON u.id=p.owner_id LEFT JOIN project_members m "
                "ON m.project_id=p.id AND m.user_id=? LEFT JOIN user_examples e ON e.project_id=p.id "
                "WHERE p.owner_id=? OR m.user_id=? ORDER BY p.updated_at DESC",
                (principal.user_id, principal.user_id, principal.user_id),
            )
            return [project_metadata(row, principal.user_id) for row in rows]

    def get(self, principal, project_id):
        with self.database.transaction() as connection:
            row = project_access(connection, principal, project_id)
            return project_metadata(row, principal.user_id) | {
                "blueprint": json.loads(row["blueprint"]),
                "edit_lock": lock_summary(active_lock(connection, project_id)),
            }

    def create(
        self, principal, name, description="", blueprint=None, source_id=None, import_key=None
    ):
        self.validate_metadata(name, description)
        if source_id:
            with self.database.transaction() as connection:
                source = project_access(connection, principal, source_id)
                blueprint = json.loads(source["blueprint"])
                templates = list(
                    connection.execute(
                        "SELECT template_id, revision, snapshot FROM project_templates WHERE project_id=?",
                        (source_id,),
                    )
                )
        else:
            templates = []
        if blueprint is None:
            blueprint = {"name": name, "version": "0.1", "nodes": [], "edges": []}
        from .project_catalog import ScopedCatalogRepository

        catalog = (
            ScopedCatalogRepository(self, principal, source_id)
            if source_id
            else self.global_catalog
        )
        content = editable_blueprint(blueprint, self.settings, catalog)
        content["name"] = name.strip()
        identifier, now = str(uuid4()), time.time()
        with self.database.transaction(write=True) as connection:
            current_user(connection, principal)
            if source_id:
                project_access(connection, principal, source_id)
            if import_key:
                existing = connection.execute(
                    "SELECT id FROM projects WHERE owner_id=? AND import_key=?",
                    (principal.user_id, import_key),
                ).fetchone()
                if existing:
                    identifier = existing["id"]
                    return self.get(principal, identifier)
            connection.execute(
                "INSERT INTO projects VALUES (?,?,?,?,?,1,?,?,?)",
                (
                    identifier,
                    principal.user_id,
                    name.strip(),
                    description,
                    json.dumps(content),
                    now,
                    now,
                    import_key,
                ),
            )
            connection.executemany(
                "INSERT INTO project_templates VALUES (?,?,?,?)",
                [(identifier, t["template_id"], t["revision"], t["snapshot"]) for t in templates],
            )
        return self.get(principal, identifier)

    @staticmethod
    def validate_metadata(name, description):
        if not isinstance(name, str) or not name.strip() or len(name) > 160:
            fail(422, "invalid_name", "Enter a project name of 1 to 160 characters.")
        if not isinstance(description, str) or len(description) > 3000:
            fail(422, "invalid_description", "Descriptions may contain up to 3000 characters.")

    def save(self, principal, project_id, token, revision, blueprint, description):
        from .project_catalog import ScopedCatalogRepository

        self.validate_metadata(
            blueprint.get("name") if isinstance(blueprint, dict) else None, description
        )
        content = editable_blueprint(
            blueprint, self.settings, ScopedCatalogRepository(self, principal, project_id)
        )
        content["name"] = content["name"].strip()
        with self.database.transaction(write=True) as connection:
            require_edit(connection, principal, project_id, token, revision)
            connection.execute(
                "UPDATE projects SET name=?, description=?, blueprint=?, revision=revision+1, updated_at=? WHERE id=?",
                (
                    content["name"].strip(),
                    description,
                    json.dumps(content),
                    time.time(),
                    project_id,
                ),
            )
        return self.get(principal, project_id)

    def delete(self, principal, project_id):
        with self.database.transaction(write=True) as connection:
            project_access(connection, principal, project_id, owner=True)
            if active_lock(connection, project_id):
                fail(423, "project_locked", "End editing before deleting this project.")
            connection.execute("DELETE FROM projects WHERE id=?", (project_id,))

    def lock(self, principal, project_id, action, token=None, editor_id=None):
        new_token = secrets.token_urlsafe(32)
        with self.database.transaction(write=True) as connection:
            row = project_access(connection, principal, project_id)
            lease = active_lock(connection, project_id)
            if action == "status":
                return {"edit_lock": lock_summary(lease)}
            if row["owner_id"] != principal.user_id and row["member_role"] != "editor":
                fail(403, "read_only", "This project is read-only.")
            if action == "acquire":
                if lease:
                    fail(
                        423,
                        "project_locked",
                        f"{lease['display_name']} is editing this project. Try again after they finish.",
                    )
                connection.execute("DELETE FROM edit_locks WHERE project_id=?", (project_id,))
                expires = time.time() + self.settings.edit_lock_seconds
                connection.execute(
                    "INSERT INTO edit_locks VALUES (?,?,?,?,?)",
                    (project_id, principal.session_id, editor_id, digest(new_token), expires),
                )
                return {"token": new_token, "expires_at": expires, "revision": row["revision"]}
            if (
                not lease
                or lease["session_id"] != principal.session_id
                or not secrets.compare_digest(lease["token_hash"], digest(token or ""))
            ):
                fail(423, "lease_lost", "Your editing reservation has expired.")
            if action == "release":
                connection.execute("DELETE FROM edit_locks WHERE project_id=?", (project_id,))
                return {"released": True}
            expires = time.time() + self.settings.edit_lock_seconds
            connection.execute(
                "UPDATE edit_locks SET expires_at=? WHERE project_id=?", (expires, project_id)
            )
            return {"expires_at": expires}

    def members(self, principal, project_id):
        with self.database.transaction() as connection:
            project = project_access(connection, principal, project_id)
            owner = connection.execute(
                "SELECT id, username, display_name FROM users WHERE id=?", (project["owner_id"],)
            ).fetchone()
            members = connection.execute(
                "SELECT u.id, u.username, u.display_name, m.role FROM project_members m JOIN users u ON u.id=m.user_id WHERE m.project_id=? ORDER BY u.username",
                (project_id,),
            )
            return [dict(owner) | {"role": "owner"}] + [dict(row) for row in members]

    def change_member(self, principal, project_id, username, role):
        with self.database.transaction(write=True) as connection:
            project = project_access(connection, principal, project_id, owner=True)
            user = connection.execute(
                "SELECT id FROM users WHERE username=? AND active=1", (username.strip().lower(),)
            ).fetchone()
            if not user:
                fail(404, "user_not_found", "No active account has that username.")
            if user["id"] == project["owner_id"]:
                fail(422, "owner_role", "The owner cannot be removed or assigned another role.")
            if role is None:
                connection.execute(
                    "DELETE FROM project_members WHERE project_id=? AND user_id=?",
                    (project_id, user["id"]),
                )
            else:
                connection.execute(
                    "INSERT INTO project_members VALUES (?,?,?) ON CONFLICT(project_id,user_id) DO UPDATE SET role=excluded.role",
                    (project_id, user["id"], role),
                )
            if role != "editor":
                connection.execute(
                    "DELETE FROM edit_locks WHERE project_id=? AND session_id IN (SELECT id FROM sessions WHERE user_id=?)",
                    (project_id, user["id"]),
                )
        return self.members(principal, project_id)
