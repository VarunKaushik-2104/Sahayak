import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key-test-secret-key-0123456789"
os.environ["PBKDF2_ROUNDS"] = "1000"
os.environ["SEED_DEMO"] = "1"

import pytest
from fastapi.testclient import TestClient

from app import clock
from app.content import get_curriculum
from app.db import Base, SessionLocal, engine
from app.main import app


@pytest.fixture(scope="session")
def cur():
    return get_curriculum()


@pytest.fixture()
def client():
    """A fresh seeded database for every test."""
    Base.metadata.drop_all(engine)
    clock.set_now(None)
    from app import routers
    routers.feedback._hits.clear()
    with TestClient(app) as c:     # runs the lifespan: create tables and seed the demo
        yield c
    clock.set_now(None)


@pytest.fixture()
def db(client):
    with SessionLocal() as s:
        yield s


def login_student(client, student_id=None, pin="1234"):
    if student_id is None:
        student_id = next(p["id"] for p in client.get("/api/auth/demo-profiles").json() if p["name"] == "Ravi K.")
    r = client.post("/api/auth/student/login", json={"student_id": student_id, "pin": pin})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def login_staff(client, role):
    """Sign in as the seeded demo teacher or parent (email + password)."""
    from app.seed import DEMO_PARENT_EMAIL, DEMO_PASSWORD, DEMO_TEACHER_EMAIL
    email = DEMO_TEACHER_EMAIL if role == "teacher" else DEMO_PARENT_EMAIL
    r = client.post("/api/auth/login", json={"email": email, "password": DEMO_PASSWORD, "role": role})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}
