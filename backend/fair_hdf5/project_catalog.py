"""A project-scoped catalog composed with the read-only installation catalog."""

import json
import time

from .access import fail
from .errors import RevisionConflict
from .project_service import project_access, require_edit


class ScopedCatalogRepository:
    def __init__(self, projects, principal, project_id, *, token=None, revision=None):
        self.projects, self.principal, self.project_id = projects, principal, project_id
        self.token, self.revision = token, revision
        self.project_revision = revision

    def catalog(self):
        with self.projects.database.transaction() as connection:
            project_access(connection, self.principal, self.project_id)
            rows = connection.execute(
                "SELECT snapshot FROM project_templates t WHERE project_id=? AND revision=(SELECT MAX(revision) FROM project_templates WHERE project_id=t.project_id AND template_id=t.template_id)",
                (self.project_id,),
            )
            local = {}
            for row in rows:
                snapshot = json.loads(row["snapshot"])
                snapshot["project_local"] = True
                local[snapshot["id"]] = snapshot
        return self.projects.global_catalog.catalog() | local

    def get(self, identifier, revision=None):
        with self.projects.database.transaction() as connection:
            project_access(connection, self.principal, self.project_id)
            row = connection.execute(
                "SELECT snapshot FROM project_templates WHERE project_id=? AND template_id=? AND (? IS NULL OR revision=?) ORDER BY revision DESC LIMIT 1",
                (self.project_id, identifier, revision, revision),
            ).fetchone()
            if row:
                return json.loads(row["snapshot"])
        return self.projects.global_catalog.get(identifier, revision)

    def publish(self, snapshot, expected_revision=None):
        with self.projects.database.transaction(write=True) as connection:
            require_edit(connection, self.principal, self.project_id, self.token, self.revision)
            if snapshot["id"] in self.projects.global_catalog.catalog():
                fail(
                    403,
                    "global_template_read_only",
                    "Copy this shared template into the project before editing it.",
                )
            previous = connection.execute(
                "SELECT MAX(revision) FROM project_templates WHERE project_id=? AND template_id=?",
                (self.project_id, snapshot["id"]),
            ).fetchone()[0]
            if previous != expected_revision:
                raise RevisionConflict("Template changed. Reload before saving.")
            connection.execute(
                "INSERT INTO project_templates VALUES (?,?,?,?)",
                (self.project_id, snapshot["id"], snapshot["revision"], json.dumps(snapshot)),
            )
            connection.execute(
                "UPDATE projects SET revision=revision+1, updated_at=? WHERE id=?",
                (time.time(), self.project_id),
            )
            self.project_revision = self.revision + 1
        return snapshot | {"project_local": True, "project_revision": self.project_revision}
