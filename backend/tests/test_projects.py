"""Multi-user boundaries, lease fencing and portable project persistence."""

import time
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

from fair_hdf5.access import ApplicationError
from fair_hdf5.application import create_app
from fair_hdf5.catalog import CATALOG
from fair_hdf5.settings import Settings
from fastapi.testclient import TestClient
from support import TEST_PASSWORD, CatalogTestCase, authenticated_client


class ProjectTests(CatalogTestCase):
    def setUp(self):
        super().setUp()
        self.app = create_app(Settings(_env_file=None))
        self.owner = authenticated_client(TestClient(self.app))
        self.addCleanup(self.owner.close)
        self.accounts = self.app.state.account_service
        self.principal = self.accounts.principal(self.owner.cookies.get("fair_session"))
        self.project = self.owner.post("/api/projects", json={"name": "Private research"}).json()
        self.url = f"/api/projects/{self.project['id']}"

    def user(self, username, *, admin=False, change_required=False):
        identifier = self.accounts.create_user(
            username, username.title(), TEST_PASSWORD, principal=self.principal, is_admin=admin
        )
        if not change_required:
            with self.app.state.database.transaction(write=True) as connection:
                connection.execute(
                    "UPDATE local_credentials SET must_change=0 WHERE user_id=?", (identifier,)
                )
        client = TestClient(self.app)
        self.addCleanup(client.close)
        session = client.get("/api/auth/session").json()
        client.headers["X-CSRF-Token"] = session["csrf_token"]
        login = client.post(
            "/api/auth/login", json={"username": username, "password": TEST_PASSWORD}
        )
        self.assertEqual(login.status_code, 200, login.text)
        client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
        return identifier, client

    def share(self, username, role):
        response = self.owner.put(self.url + "/members", json={"username": username, "role": role})
        self.assertEqual(response.status_code, 200, response.text)

    def acquire(self, client=None):
        client = client or self.owner
        response = client.post(self.url + "/edit-lock", json={"editor_id": "one-tab"})
        self.assertEqual(response.status_code, 200, response.text)
        client.headers["X-Edit-Lease"] = response.json()["token"]
        return response.json()["token"]

    def save(self, client=None, *, revision=1, blueprint=None):
        return (client or self.owner).put(
            self.url,
            json={
                "expected_revision": revision,
                "blueprint": blueprint or self.project["blueprint"],
            },
        )

    def test_private_projects_and_templates_are_hidden_even_from_an_admin(self):
        _, outsider = self.user("otheradmin", admin=True)
        visible = outsider.get("/api/projects").json()
        self.assertNotIn(self.project["id"], [p["id"] for p in visible])
        self.assertTrue(all(p["role"] == "owner" and p["example_id"] for p in visible))
        for suffix in ("", "/members", "/catalog", "/edit-lock", "/catalog/unknown/revisions/1"):
            self.assertEqual(outsider.get(self.url + suffix).status_code, 404)
        self.assertEqual(self.save(outsider).status_code, 404)
        self.assertEqual(outsider.delete(self.url).status_code, 404)

    def test_membership_roles_and_private_copy(self):
        _, viewer = self.user("viewer")
        self.share("viewer", "viewer")
        summary = next(
            p for p in viewer.get("/api/projects").json() if p["id"] == self.project["id"]
        )
        self.assertEqual(summary["role"], "viewer")
        self.assertTrue(summary["shared"])
        self.assertEqual(viewer.get(self.url).status_code, 200)
        self.assertEqual(
            viewer.post(self.url + "/edit-lock", json={"editor_id": "viewer"}).status_code, 403
        )
        self.assertEqual(self.save(viewer).status_code, 403)
        self.assertEqual(
            viewer.put(
                self.url + "/members", json={"username": "viewer", "role": "editor"}
            ).status_code,
            403,
        )
        copied = viewer.post(
            "/api/projects", json={"name": "My copy", "source_id": self.project["id"]}
        )
        self.assertEqual(copied.status_code, 201)
        self.assertEqual(copied.json()["role"], "owner")
        self.assertFalse(copied.json()["shared"])
        self.assertNotEqual(copied.json()["id"], self.project["id"])
        self.share("viewer", None)
        self.assertEqual(viewer.get(self.url).status_code, 404)

    def test_only_one_tab_can_edit_and_old_tokens_cannot_release_new_locks(self):
        first = self.acquire()
        blocked = self.owner.post(self.url + "/edit-lock", json={"editor_id": "second-tab"})
        self.assertEqual(blocked.status_code, 423)
        self.assertEqual(self.owner.delete(self.url).status_code, 423)
        self.assertEqual(self.owner.delete(self.url + "/edit-lock").status_code, 200)
        second = self.acquire()
        self.assertNotEqual(first, second)
        for method, suffix in (("post", "/renew"), ("delete", "")):
            response = getattr(self.owner, method)(
                self.url + "/edit-lock" + suffix, headers={"X-Edit-Lease": first}
            )
            self.assertEqual(response.status_code, 423)
        self.assertEqual(self.save().status_code, 200)

    def test_expired_lease_cannot_save_or_renew(self):
        self.acquire()
        with self.app.state.database.transaction(write=True) as connection:
            connection.execute("UPDATE edit_locks SET expires_at=?", (time.time() - 1,))
        self.assertEqual(self.save().status_code, 423)
        self.assertEqual(self.owner.post(self.url + "/edit-lock/renew").status_code, 423)
        self.acquire()
        self.assertEqual(self.save().status_code, 200)

    def test_token_is_bound_to_the_authentication_session(self):
        _, editor = self.user("editor")
        self.share("editor", "editor")
        token = self.acquire()
        editor.headers["X-Edit-Lease"] = token
        self.assertEqual(self.save(editor).status_code, 423)

    def test_role_revocation_and_deactivation_revoke_active_leases(self):
        identifier, editor = self.user("editor")
        self.share("editor", "editor")
        self.acquire(editor)
        self.share("editor", "viewer")
        self.assertEqual(self.save(editor).status_code, 403)
        self.assertIsNone(self.owner.get(self.url + "/edit-lock").json()["edit_lock"])
        self.share("editor", "editor")
        self.acquire(editor)
        self.assertEqual(
            self.owner.patch(f"/api/admin/users/{identifier}", json={"active": False}).status_code,
            200,
        )
        self.assertEqual(self.save(editor).status_code, 401)
        self.assertIsNone(self.owner.get(self.url + "/edit-lock").json()["edit_lock"])

    def test_concurrent_saves_compare_revision_in_the_write_transaction(self):
        token = self.acquire()
        service = self.app.state.project_service

        def save():
            try:
                return service.save(
                    self.principal, self.project["id"], token, 1, self.project["blueprint"], ""
                )["revision"]
            except ApplicationError as error:
                return error.status

        with ThreadPoolExecutor(max_workers=2) as executor:
            self.assertCountEqual(list(executor.map(lambda _: save(), range(2))), [2, 409])
        self.assertEqual(self.owner.get(self.url).json()["revision"], 2)

    def test_concurrent_lock_acquisition_has_exactly_one_winner(self):
        service = self.app.state.project_service

        def acquire(i):
            try:
                service.lock(self.principal, self.project["id"], "acquire", editor_id=str(i))
                return 200
            except ApplicationError as error:
                return error.status

        with ThreadPoolExecutor(max_workers=2) as executor:
            self.assertCountEqual(list(executor.map(acquire, range(2))), [200, 423])

    def test_incomplete_designs_save_but_keep_scientific_validation(self):
        self.acquire()
        blueprint = {
            "name": "Unfinished",
            "version": "0.1",
            "nodes": [
                {
                    "id": "draft",
                    "type": "group",
                    "label": "",
                    "x": 1,
                    "y": 2,
                    "config": {"path": "", "missing_field": ""},
                }
            ],
            "edges": [],
        }
        saved = self.save(blueprint=blueprint)
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json()["blueprint"]["nodes"][0]["config"]["path"], "")
        self.assertEqual(
            self.owner.post("/api/preview", json=saved.json()["blueprint"]).status_code, 422
        )
        self.assertEqual(self.owner.get(self.url).json()["name"], "Unfinished")

    def test_invalid_envelopes_are_rejected_without_changing_the_project(self):
        self.acquire()
        blueprint = deepcopy(self.project["blueprint"])
        blueprint["edges"] = [
            {"id": "dangling", "source": "missing", "target": "missing", "relation": "feeds"}
        ]
        self.assertEqual(self.save(blueprint=blueprint).status_code, 422)
        self.assertEqual(self.owner.get(self.url).json()["revision"], 1)

    def test_numeric_lists_follow_the_frontend_number_contract(self):
        self.acquire()
        blueprint = {
            "name": "Numbers",
            "version": "0.1",
            "nodes": [
                {
                    "id": "draft",
                    "type": "group",
                    "label": "Draft",
                    "x": 1,
                    "y": 2,
                    "config": {"path": "", "values": [1, 2.5]},
                }
            ],
            "edges": [],
        }
        response = self.save(blueprint=blueprint)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["blueprint"]["nodes"][0]["config"]["values"], [1, 2.5])
        blueprint["nodes"][0]["x"] = 10**400
        self.assertEqual(self.save(revision=2, blueprint=blueprint).status_code, 422)
        self.assertEqual(self.owner.get(self.url).json()["revision"], 2)

    def test_empty_blueprint_objects_are_rejected_instead_of_silently_replaced(self):
        response = self.owner.post("/api/projects", json={"name": "Malformed", "blueprint": {}})
        self.assertEqual(response.status_code, 422)

    def test_project_templates_are_immutable_isolated_and_copied(self):
        self.acquire()
        published = self.owner.post(
            self.url + "/catalog", json={"expected_revision": 1, "template": CATALOG["group"]}
        )
        self.assertEqual(published.status_code, 201, published.text)
        template = published.json()
        self.assertEqual(template["project_revision"], 2)
        self.assertNotIn(template["id"], self.owner.get("/api/catalog").json()["catalog"])
        other = self.owner.post("/api/projects", json={"name": "Unrelated"}).json()
        other_url = f"/api/projects/{other['id']}/catalog"
        self.assertNotIn(template["id"], self.owner.get(other_url).json()["catalog"])
        self.assertNotEqual(
            self.owner.get(other_url + f"/{template['id']}/revisions/1").status_code, 200
        )
        copied = self.owner.post(
            "/api/projects", json={"name": "Copy", "source_id": self.project["id"]}
        ).json()
        self.assertIn(
            template["id"],
            self.owner.get(f"/api/projects/{copied['id']}/catalog").json()["catalog"],
        )
        stale = self.owner.post(
            self.url + "/catalog", json={"expected_revision": 1, "template": CATALOG["group"]}
        )
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(
            len(
                [
                    t
                    for t in self.owner.get(self.url + "/catalog").json()["catalog"].values()
                    if t.get("project_local")
                ]
            ),
            1,
        )

    def test_global_writes_are_disabled(self):
        self.assertEqual(self.owner.post("/api/catalog", json=CATALOG["group"]).status_code, 403)
        self.assertEqual(
            self.owner.post(
                "/api/catalog/group/revisions",
                json={"expected_revision": 1, "template": CATALOG["group"]},
            ).status_code,
            403,
        )

    def test_legacy_import_is_idempotent_and_persists_across_app_restart(self):
        payload = {
            "name": "Imported",
            "blueprint": self.project["blueprint"],
            "import_key": "legacy-unique",
        }
        first = self.owner.post("/api/projects", json=payload).json()
        second = self.owner.post("/api/projects", json=payload).json()
        self.assertEqual(first["id"], second["id"])
        restarted = create_app(Settings(_env_file=None))
        with authenticated_client(TestClient(restarted)) as client:
            self.assertEqual(
                client.get(f"/api/projects/{first['id']}").json()["blueprint"], first["blueprint"]
            )

    def test_authentication_csrf_origin_and_cookie_contract(self):
        with TestClient(self.app) as anonymous:
            self.assertEqual(anonymous.get("/api/projects").status_code, 401)
            self.assertEqual(anonymous.post("/api/projects", json={"name": "No"}).status_code, 401)
            response = anonymous.get("/api/auth/session")
            self.assertIn("HttpOnly", response.headers["set-cookie"])
            self.assertIn("SameSite=lax", response.headers["set-cookie"])
            self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(
            self.owner.post(
                "/api/projects", json={"name": "No"}, headers={"X-CSRF-Token": "wrong"}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.owner.post(
                "/api/projects", json={"name": "No"}, headers={"Origin": "https://evil.invalid"}
            ).status_code,
            403,
        )

    def test_forced_password_change_resets_sessions_and_unlocks_projects(self):
        _, user = self.user("newuser", change_required=True)
        self.assertEqual(user.get("/api/projects").status_code, 403)
        old_cookie = user.cookies.get("fair_session")
        unchanged = user.post(
            "/api/auth/password",
            json={"old_password": TEST_PASSWORD, "new_password": TEST_PASSWORD},
        )
        self.assertEqual(unchanged.status_code, 422)
        response = user.post(
            "/api/auth/password",
            json={
                "old_password": TEST_PASSWORD,
                "new_password": "a new long and unique passphrase",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(user.cookies.get("fair_session"), old_cookie)
        self.assertFalse(response.json()["user"]["must_change_password"])
        self.assertEqual(user.get("/api/projects").status_code, 200)
        with self.assertRaises(ApplicationError):
            self.accounts.principal(old_cookie)

    def test_admin_reset_invalidates_session_and_last_admin_is_preserved(self):
        identifier, editor = self.user("editor")
        self.share("editor", "editor")
        self.acquire(editor)
        response = self.owner.post(f"/api/admin/users/{identifier}/password")
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.json()["temporary_password"]), 15)
        self.assertEqual(editor.get(self.url).status_code, 401)
        self.assertIsNone(self.owner.get(self.url + "/edit-lock").json()["edit_lock"])
        response = self.owner.patch(
            f"/api/admin/users/{self.principal.user_id}", json={"active": False}
        )
        self.assertEqual(response.status_code, 409)

    def test_login_is_rate_limited_and_never_reuses_the_anonymous_session(self):
        with TestClient(self.app) as client:
            session = client.get("/api/auth/session").json()
            client.headers["X-CSRF-Token"] = session["csrf_token"]
            for _ in range(10):
                self.assertEqual(
                    client.post(
                        "/api/auth/login", json={"username": "unknown", "password": "wrong"}
                    ).status_code,
                    401,
                )
            self.assertEqual(
                client.post(
                    "/api/auth/login", json={"username": "unknown", "password": "wrong"}
                ).status_code,
                429,
            )
        before = self.owner.cookies.get("fair_session")
        authenticated_client(self.owner)
        self.assertNotEqual(before, self.owner.cookies.get("fair_session"))

    def test_logout_ends_the_editing_reservation(self):
        self.acquire()
        self.assertEqual(self.owner.post("/api/auth/logout").status_code, 200)
        self.assertEqual(self.owner.get(self.url).status_code, 401)
        with self.app.state.database.transaction() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM edit_locks").fetchone()[0], 0)
