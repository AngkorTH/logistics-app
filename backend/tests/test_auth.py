"""ทดสอบระบบ Login, Single-Session Lock และ Role-based access"""
from tests.conftest import login


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_login_success_and_me(client):
    r = login(client, "D01")
    assert r.status_code == 200
    data = r.json()
    assert data["user"]["emp_id"] == "D01"
    token = data["access_token"]

    me = client.get("/auth/me", headers=auth(token))
    assert me.status_code == 200
    assert me.json()["role"] == "DRIVER"


def test_login_with_phone(client):
    r = login(client, "0810000001")  # ล็อกอินด้วยเบอร์โทรก็ได้
    assert r.status_code == 200


def test_login_wrong_password(client):
    r = login(client, "D01", password="9999")
    assert r.status_code == 401


def test_suspended_account_cannot_login(client):
    r = login(client, "D04")  # บัญชีถูกระงับ (active=False)
    assert r.status_code == 403


def test_no_token_rejected(client):
    assert client.get("/auth/me").status_code == 401


def test_single_session_lock_kicks_old_device(client):
    """เข้าเครื่องแรก -> token A ใช้ได้; เข้าซ้อนเครื่องสอง -> token B; token A ต้องถูกดีดออก"""
    token_a = login(client, "D01").json()["access_token"]
    assert client.get("/auth/me", headers=auth(token_a)).status_code == 200  # A ใช้ได้ตอนแรก

    token_b = login(client, "D01").json()["access_token"]  # login ซ้อนจากอีกเครื่อง

    # token เก่า (A) ต้องใช้ไม่ได้แล้ว
    kicked = client.get("/auth/me", headers=auth(token_a))
    assert kicked.status_code == 401
    # token ใหม่ (B) ต้องใช้งานได้
    assert client.get("/auth/me", headers=auth(token_b)).status_code == 200


def test_require_role_blocks_driver(client):
    driver_token = login(client, "D01").json()["access_token"]
    # Driver เข้า endpoint เฉพาะ Admin ไม่ได้
    assert client.get("/admin/ping", headers=auth(driver_token)).status_code == 403


def test_require_role_allows_admin(client):
    admin_token = login(client, "AD01").json()["access_token"]
    r = client.get("/admin/ping", headers=auth(admin_token))
    assert r.status_code == 200


def test_logout_invalidates_token(client):
    token = login(client, "D01").json()["access_token"]
    assert client.post("/auth/logout", headers=auth(token)).status_code == 200
    # หลัง logout token เดิมใช้ไม่ได้ (session_id ถูกล้าง)
    assert client.get("/auth/me", headers=auth(token)).status_code == 401
