"""Configurable local password rules stay consistent across CLI, API and sessions."""

from unittest.mock import patch

from fair_hdf5.__main__ import main
from fair_hdf5.access import ApplicationError
from fair_hdf5.application import create_app
from fair_hdf5.settings import Settings
from fastapi.testclient import TestClient
from support import CatalogTestCase


class PasswordPolicyTests(CatalogTestCase):
    def application(self, minimum=15):
        return create_app(Settings(_env_file=None, password_min_length=minimum))

    def login(self, client, password):
        session = client.get("/api/auth/session").json()
        client.headers["X-CSRF-Token"] = session["csrf_token"]
        response = client.post("/api/auth/login", json={"username": "admin", "password": password})
        self.assertEqual(response.status_code, 200, response.text)
        client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
        return response.json()

    def assert_policy(self, data, minimum):
        self.assertEqual(data["password_policy"], {"min_length": minimum, "max_length": 128})

    def test_default_minimum_and_password_change_boundaries(self):
        app = self.application()
        accounts = app.state.account_service
        with self.assertRaises(ApplicationError) as error:
            accounts.create_user("admin", "Admin", "a" * 14, is_admin=True, bootstrap=True)
        self.assertEqual(error.exception.code, "invalid_password")
        accounts.create_user("admin", "Admin", "a" * 15, is_admin=True, bootstrap=True)
        with TestClient(app) as client:
            self.assert_policy(client.get("/api/auth/session").json(), 15)
            self.assert_policy(self.login(client, "a" * 15), 15)
            for length in (14, 129):
                response = client.post(
                    "/api/auth/password",
                    json={"old_password": "a" * 15, "new_password": "b" * length},
                )
                self.assertEqual(response.status_code, 422, response.text)
            response = client.post(
                "/api/auth/password",
                json={"old_password": "a" * 15, "new_password": "b" * 15},
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assert_policy(response.json(), 15)

    def test_three_character_admin_and_user_passwords(self):
        app = self.application(3)
        accounts = app.state.account_service
        with self.assertRaises(ApplicationError) as error:
            accounts.create_user("admin", "Admin", "ab", is_admin=True, bootstrap=True)
        self.assertEqual(error.exception.code, "invalid_password")
        accounts.create_user("admin", "Admin", "abc", is_admin=True, bootstrap=True)
        with TestClient(app) as client:
            self.assert_policy(client.get("/api/auth/session").json(), 3)
            self.assert_policy(self.login(client, "abc"), 3)
            principal = accounts.principal(client.cookies.get("fair_session"))
            with self.assertRaises(ApplicationError) as error:
                accounts.create_user("member", "Member", "ab", principal=principal)
            self.assertEqual(error.exception.code, "invalid_password")
            accounts.create_user("member", "Member", "abc", principal=principal)
            response = client.post(
                "/api/auth/password", json={"old_password": "abc", "new_password": "xy"}
            )
            self.assertEqual(response.status_code, 422, response.text)
            self.assertIn("3 to 128", response.json()["detail"])
            response = client.post(
                "/api/auth/password", json={"old_password": "abc", "new_password": "xyz"}
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assert_policy(response.json(), 3)
            self.assert_policy(client.get("/api/auth/session").json(), 3)
            self.assert_policy(self.login(client, "xyz"), 3)

    def test_temporary_passwords_satisfy_the_maximum_configured_minimum(self):
        app = self.application(128)
        app.state.account_service.create_user(
            "admin", "Admin", "a" * 128, is_admin=True, bootstrap=True
        )
        with TestClient(app) as client:
            self.assert_policy(self.login(client, "a" * 128), 128)
            response = client.post(
                "/api/admin/users", json={"username": "member", "display_name": "Member"}
            )
            self.assertEqual(response.status_code, 201, response.text)
            created = response.json()
            self.assertEqual(len(created["temporary_password"]), 128)
            response = client.post(f"/api/admin/users/{created['id']}/password")
            self.assertEqual(response.status_code, 200, response.text)
            temporary = response.json()["temporary_password"]
            self.assertEqual(len(temporary), 128)
            self.assertNotEqual(temporary, created["temporary_password"])
            response = client.post(
                "/api/auth/login", json={"username": "member", "password": temporary}
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertTrue(response.json()["user"]["must_change_password"])
            client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
            response = client.post(
                "/api/auth/password",
                json={"old_password": temporary, "new_password": "b" * 128},
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assert_policy(response.json(), 128)

    def test_increasing_minimum_keeps_existing_passwords_valid(self):
        app = self.application(3)
        app.state.account_service.create_user(
            "admin", "Admin", "abc", is_admin=True, bootstrap=True
        )
        with TestClient(self.application(15)) as client:
            self.assert_policy(self.login(client, "abc"), 15)
            response = client.post(
                "/api/auth/password", json={"old_password": "abc", "new_password": "xyz"}
            )
            self.assertEqual(response.status_code, 422, response.text)

    def test_admin_cli_uses_configured_minimum(self):
        app = self.application(3)
        with (
            patch("sys.argv", ["fair_hdf5", "--create-admin", "admin"]),
            patch("fair_hdf5.__main__.Settings", return_value=app.state.settings),
            patch("fair_hdf5.__main__.create_app", return_value=app),
            patch("fair_hdf5.__main__.getpass.getpass", side_effect=["abc", "abc"]) as prompt,
            patch("builtins.print"),
        ):
            main()
        self.assertIn("at least 3 characters", prompt.call_args_list[0].args[0])
        with TestClient(app) as client:
            self.assert_policy(self.login(client, "abc"), 3)
