"""Project/account journeys in distinct real browser sessions against the built app."""

import json
import os
import unittest
from pathlib import Path
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright
from ui_support import URL, create_project, sign_in

OUT = Path(os.environ.get("FAIR_SCREENSHOT_DIR", "/tmp/fair-project-qa-screenshots"))


class ProjectBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        kwargs = {"headless": True, "args": ["--no-sandbox"]}
        if os.environ.get("FAIR_BROWSER_EXECUTABLE"):
            kwargs["executable_path"] = os.environ["FAIR_BROWSER_EXECUTABLE"]
        cls.browser = cls.playwright.chromium.launch(**kwargs)
        OUT.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.contexts = []
        self.errors = []
        self.allowed_statuses = {401, 403, 404, 423}
        self.context, self.page, self.csrf = self.new_session()
        self.name = "QA project " + uuid4().hex[:8]
        self.project = create_project(
            self.context,
            self.csrf,
            {
                "name": self.name,
                "version": "0.1",
                "nodes": [
                    {
                        "id": "metadata",
                        "type": "group",
                        "label": "Project metadata",
                        "x": 0,
                        "y": 0,
                        "config": {"path": "/experiment"},
                    }
                ],
                "edges": [],
            },
        )
        self.project_url = URL + "/projects/" + self.project["id"]

    def new_session(self, username=None):
        context = self.browser.new_context(viewport={"width": 1672, "height": 941})
        self.contexts.append(context)
        context.route("https://fonts.googleapis.com/**", lambda route: route.fulfill(body=""))
        context.route("https://fonts.gstatic.com/**", lambda route: route.fulfill(body=""))
        _, csrf = sign_in(context, username)
        page = context.new_page()
        page.on("pageerror", lambda error: self.errors.append(str(error)))

        def console(message):
            if message.type not in ("error", "warning"):
                return
            if message.text.startswith("React Flow: It seems like you are hiding the attribution."):
                return
            if any(f"status of {status}" in message.text for status in self.allowed_statuses):
                return
            self.errors.append(message.text)

        page.on("console", console)
        return context, page, csrf

    def tearDown(self):
        try:
            result = self._outcome.result
            if any(case is self for case, _ in result.failures + result.errors):
                self.page.screenshot(
                    path=str(OUT / (self._testMethodName + "-failure.png")), full_page=True
                )
            self.assertEqual(self.errors, [], "Browser console must remain clean")
        finally:
            for context in self.contexts:
                context.close()

    def open(self, page=None):
        page = page or self.page
        page.goto(self.project_url)
        expect(page).to_have_title("FAIR Data Design Suite")
        expect(page.locator(".react-flow__viewport")).to_be_attached(timeout=20000)
        expect(page.locator("vite-error-overlay")).to_have_count(0)

    def share(self, username, role):
        response = self.context.request.put(
            URL + f"/api/projects/{self.project['id']}/members",
            headers={"X-CSRF-Token": self.csrf},
            data={"username": username, "role": role},
        )
        self.assertEqual(response.status, 200, response.text())

    def test_overview_create_view_edit_save_copy_and_deep_link(self):
        self.page.goto(URL + "/projects")
        expect(self.page.get_by_role("heading", name="Projects", exact=True)).to_be_visible()
        self.page.get_by_label("Search projects", exact=True).fill(self.name)
        expect(self.page.get_by_role("link", name=self.name, exact=True)).to_be_visible()
        self.page.screenshot(path=str(OUT / "projects-desktop.png"), full_page=True)
        self.page.set_viewport_size({"width": 768, "height": 600})
        self.assertLessEqual(self.page.evaluate("document.documentElement.scrollWidth"), 768)
        self.page.screenshot(path=str(OUT / "projects-compact.png"), full_page=True)
        self.page.get_by_role("link", name=self.name, exact=True).click()
        expect(self.page.get_by_label("Experiment title")).to_have_attribute("readonly", "")
        status = self.context.request.get(
            URL + f"/api/projects/{self.project['id']}/edit-lock"
        ).json()
        self.assertIsNone(status["edit_lock"], "Viewing must not reserve a project")
        self.page.get_by_role("button", name="Edit project", exact=True).click()
        expect(self.page.get_by_role("button", name="Finish editing", exact=True)).to_be_visible()
        renamed = self.name + " saved"
        self.page.get_by_label("Experiment title").fill(renamed)
        expect(self.page.locator(".saved-text")).to_contain_text("Saved on server")
        self.page.get_by_role("button", name="Finish editing", exact=True).click()
        expect(self.page.get_by_role("button", name="Edit project", exact=True)).to_be_visible()
        self.page.reload()
        expect(self.page.get_by_label("Experiment title")).to_have_value(renamed)
        expect(self.page.get_by_label("Experiment title")).to_have_attribute("readonly", "")
        self.page.get_by_role("button", name="Back to projects", exact=True).click()
        expect(self.page.get_by_role("heading", name="Projects", exact=True)).to_be_visible()
        self.page.get_by_label("Search projects", exact=True).fill(renamed)
        self.page.get_by_role("button", name="Copy " + renamed, exact=True).click()
        expect(self.page.get_by_label("Experiment title")).to_have_value(renamed + " (copy)")
        self.assertNotEqual(self.page.url, self.project_url)
        self.assertEqual(self.page.locator(".draft-tag").inner_text(), "Private")

    def test_private_project_sharing_viewer_and_editor_permissions(self):
        viewer_context, viewer, _ = self.new_session("qaviewer")
        viewer.goto(self.project_url)
        expect(
            viewer.get_by_role("heading", name="Project unavailable", exact=True)
        ).to_be_visible()
        self.open()
        self.page.get_by_role("button", name="Share", exact=True).click()
        self.page.get_by_label("Add an existing user").fill("qaviewer")
        self.page.get_by_label("Permission", exact=True).select_option("viewer")
        self.page.get_by_role("button", name="Add member", exact=True).click()
        expect(self.page.get_by_role("dialog")).to_contain_text("qaviewer")
        self.page.screenshot(path=str(OUT / "sharing.png"), full_page=True)
        self.page.get_by_role("button", name="Close dialog", exact=True).click()
        expect(self.page.locator(".draft-tag")).to_contain_text("Shared")
        self.open(viewer)
        expect(viewer.get_by_text("View only", exact=True)).to_be_visible()
        expect(
            viewer.get_by_role("button", name="Create / import template", exact=True)
        ).to_be_disabled()
        expect(viewer.get_by_label("Experiment title")).to_have_attribute("readonly", "")
        viewer.locator(".react-flow__node").first.click()
        expect(viewer.locator(".inspector")).to_contain_text("Project metadata")
        expect(viewer.locator(".inspector input").first).to_be_disabled()
        expect(viewer.get_by_role("button", name="Close inspector", exact=True)).to_be_enabled()
        viewer.get_by_role("button", name="Project", exact=True).click()
        with viewer.expect_download() as download:
            viewer.get_by_role("button", name="Export blueprint JSON", exact=True).click()
        self.assertEqual(json.loads(Path(download.value.path()).read_text())["name"], self.name)
        self.share("qaviewer", "editor")
        viewer.reload()
        viewer.get_by_role("button", name="Edit project", exact=True).click()
        expect(viewer.get_by_role("button", name="Finish editing", exact=True)).to_be_visible()
        viewer.get_by_label("Experiment title").fill(self.name + " by member")
        expect(viewer.locator(".saved-text")).to_contain_text("Saved on server")
        self.share("qaviewer", None)
        viewer.get_by_label("Experiment title").fill(self.name + " revoked")
        expect(viewer.get_by_role("alert")).to_contain_text("no longer shared")
        self.assertEqual(
            viewer_context.request.get(URL + f"/api/projects/{self.project['id']}").status, 404
        )

    def test_two_tabs_in_the_same_login_cannot_edit_together(self):
        self.open()
        second = self.context.new_page()
        self.open(second)
        self.page.get_by_role("button", name="Edit project", exact=True).click()
        expect(self.page.get_by_role("button", name="Finish editing", exact=True)).to_be_visible()
        second.get_by_role("button", name="Edit project", exact=True).click()
        expect(second.get_by_role("alert")).to_contain_text("is editing this project")
        expect(second.get_by_label("Experiment title")).to_have_attribute("readonly", "")
        self.page.get_by_role("button", name="Finish editing", exact=True).click()
        expect(self.page.get_by_role("button", name="Edit project", exact=True)).to_be_visible()
        second.get_by_role("button", name="Edit project", exact=True).click()
        expect(second.get_by_role("button", name="Finish editing", exact=True)).to_be_visible()
        second.close()

    def test_navigation_saves_then_releases_the_reservation(self):
        self.open()
        self.page.get_by_role("button", name="Edit project", exact=True).click()
        expect(self.page.get_by_role("button", name="Finish editing", exact=True)).to_be_visible()
        self.page.get_by_label("Experiment title").fill(self.name + " before leaving")
        self.page.get_by_role("button", name="Projects", exact=True).click()
        expect(self.page.get_by_role("heading", name="Projects", exact=True)).to_be_visible()
        saved = self.context.request.get(URL + f"/api/projects/{self.project['id']}").json()
        self.assertEqual(saved["name"], self.name + " before leaving")
        self.assertIsNone(saved["edit_lock"])

    def test_failed_save_preserves_export_and_private_copy(self):
        self.allowed_statuses.add(503)
        self.open()
        self.page.get_by_role("button", name="Edit project", exact=True).click()
        expect(self.page.get_by_role("button", name="Finish editing", exact=True)).to_be_visible()
        pattern = "**/api/projects/" + self.project["id"]

        def unavailable(route):
            if route.request.method == "PUT":
                route.fulfill(status=503, json={"detail": "Connection interrupted"})
            else:
                route.continue_()

        self.page.route(pattern, unavailable)
        draft_name = self.name + " local recovery"
        self.page.get_by_label("Experiment title").fill(draft_name)
        expect(self.page.get_by_role("alert")).to_contain_text("Connection interrupted")
        expect(self.page.get_by_label("Experiment title")).to_have_attribute("readonly", "")
        self.page.screenshot(path=str(OUT / "editing-paused.png"), full_page=True)
        with self.page.expect_download() as download:
            self.page.get_by_role("button", name="Export draft", exact=True).click()
        self.assertEqual(json.loads(Path(download.value.path()).read_text())["name"], draft_name)
        self.page.unroute(pattern)
        self.page.get_by_role("button", name="Save private copy", exact=True).click()
        expect(self.page.get_by_label("Experiment title")).to_have_value(draft_name + " (copy)")
        self.assertNotEqual(self.page.url, self.project_url)
        original = self.context.request.get(URL + f"/api/projects/{self.project['id']}").json()
        self.assertEqual(original["name"], self.name)
        self.assertIsNone(original["edit_lock"])

    def test_configured_password_policy_controls_form_and_sign_in(self):
        session = self.context.request.get(URL + "/api/auth/session").json()
        policy = session["password_policy"]
        minimum = policy["min_length"]
        username = "qa_policy_" + uuid4().hex[:8]
        response = self.context.request.post(
            URL + "/api/admin/users",
            headers={"X-CSRF-Token": self.csrf},
            data={"username": username, "display_name": "Password policy test"},
        )
        self.assertEqual(response.status, 201, response.text())
        temporary = response.json()["temporary_password"]
        self.context.clear_cookies()
        self.page.goto(URL + "/login")
        expect(self.page).to_have_title("FAIR Data Design Suite")
        self.page.get_by_label("Username", exact=True).fill(username)
        self.page.get_by_label("Password", exact=True).fill(temporary)
        self.page.get_by_role("button", name="Sign in", exact=True).click()
        expect(self.page.get_by_role("heading", name="Your account", exact=True)).to_be_visible()
        expect(self.page.locator("vite-error-overlay")).to_have_count(0)
        expect(
            self.page.get_by_text(f"Use at least {minimum} characters.", exact=False)
        ).to_be_visible()
        new_password = self.page.get_by_label("New password", exact=True)
        expect(new_password).to_have_attribute("minlength", str(minimum))
        expect(new_password).to_have_attribute("maxlength", str(policy["max_length"]))
        self.page.get_by_label("Current password", exact=True).fill(temporary)
        new_password.fill("p" * (minimum - 1))
        self.page.get_by_label("Repeat new password", exact=True).fill("p" * (minimum - 1))
        self.page.get_by_role("button", name="Change password", exact=True).click()
        self.assertTrue(new_password.evaluate("input => input.validity.tooShort"))
        expect(self.page).to_have_url(URL + "/account")
        password = "p" * minimum
        new_password.fill(password)
        self.page.get_by_label("Repeat new password", exact=True).fill(password)
        self.page.screenshot(path=str(OUT / "password-policy-desktop.png"), full_page=True)
        self.page.set_viewport_size({"width": 768, "height": 600})
        self.assertLessEqual(self.page.evaluate("document.documentElement.scrollWidth"), 768)
        self.page.screenshot(path=str(OUT / "password-policy-compact.png"), full_page=True)
        self.page.get_by_role("button", name="Change password", exact=True).click()
        expect(self.page.get_by_role("heading", name="Projects", exact=True)).to_be_visible()
        self.page.goto(URL + "/logout")
        expect(self.page.get_by_role("button", name="Sign in", exact=True)).to_be_visible()
        self.page.get_by_label("Username", exact=True).fill(username)
        self.page.get_by_label("Password", exact=True).fill(password)
        self.page.get_by_role("button", name="Sign in", exact=True).click()
        expect(self.page.get_by_role("heading", name="Projects", exact=True)).to_be_visible()

    def test_admin_creates_account_and_first_login_requires_password_change(self):
        self.page.goto(URL + "/admin/users")
        expect(self.page.get_by_role("heading", name="User accounts", exact=True)).to_be_visible()
        self.page.get_by_role("button", name="New account", exact=True).click()
        username = "qa_" + uuid4().hex[:8]
        self.page.get_by_label("Username", exact=True).fill(username)
        self.page.get_by_label("Display name", exact=True).fill("New Researcher")
        self.page.get_by_role("button", name="Create account", exact=True).click()
        dialog = self.page.get_by_role("dialog", name="Temporary password", exact=True)
        expect(dialog).to_be_visible()
        temporary = dialog.get_by_label("Password", exact=True).input_value()
        dialog.get_by_role("button", name="Done", exact=True).click()
        self.page.screenshot(path=str(OUT / "users-desktop.png"), full_page=True)
        context = self.browser.new_context(viewport={"width": 1000, "height": 800})
        self.contexts.append(context)
        page = context.new_page()
        page.goto(URL + "/login")
        page.get_by_label("Username", exact=True).fill(username)
        page.get_by_label("Password", exact=True).fill(temporary)
        page.get_by_role("button", name="Sign in", exact=True).click()
        expect(page.get_by_role("heading", name="Your account", exact=True)).to_be_visible()
        page.get_by_label("Current password", exact=True).fill(temporary)
        page.get_by_label("New password", exact=True).fill(os.environ["FAIR_TEST_PASSWORD"])
        page.get_by_label("Repeat new password", exact=True).fill(os.environ["FAIR_TEST_PASSWORD"])
        page.get_by_role("button", name="Change password", exact=True).click()
        expect(page.get_by_role("heading", name="Projects", exact=True)).to_be_visible()
        expect(
            page.get_by_role("heading", name="Your first project starts here", exact=True)
        ).to_be_visible()


if __name__ == "__main__":
    unittest.main(verbosity=2)
