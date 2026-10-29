import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key-test-secret-key-0123456789"
os.environ["PBKDF2_ROUNDS"] = "1000"
os.environ["SEED_DEMO"] = "1"
os.environ["SMS_BACKEND"] = "console"

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
    routers.auth._otp_hits.clear()
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


def login_otp(client, mobile, role):
    code = client.post("/api/auth/otp/request", json={"mobile": mobile, "role": role}).json()["dev_code"]
    r = client.post("/api/auth/otp/verify", json={"mobile": mobile, "role": role, "code": code})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}
