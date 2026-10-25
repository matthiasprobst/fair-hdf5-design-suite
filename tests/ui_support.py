"""Real cookie/CSRF authentication helpers shared by browser regression suites."""

import os

URL = os.environ.get("FAIR_UI_URL", "http://127.0.0.1:5173")


def sign_in(context, username=None):
    username = username or os.environ.get("FAIR_TEST_ADMIN", "qaadmin")
    password = os.environ["FAIR_TEST_PASSWORD"]
    session = context.request.get(URL + "/api/auth/session").json()
    response = context.request.post(
        URL + "/api/auth/login",
        headers={"X-CSRF-Token": session["csrf_token"]},
        data={"username": username, "password": password},
    )
    if response.status != 200:
        raise AssertionError(f"Cannot sign in as test user {username}: {response.status}")
    result = response.json()
    return result["user"], result["csrf_token"]


def create_project(context, csrf, blueprint):
    response = context.request.post(
        URL + "/api/projects",
        headers={"X-CSRF-Token": csrf},
        data={"name": blueprint["name"], "blueprint": blueprint},
    )
    if response.status != 201:
        raise AssertionError(f"Cannot create browser fixture: {response.status} {response.text()}")
    return response.json()
