"""End-to-end backend tests for VOIDD Hire Flask app.

Covers: health, auth, public submissions (candidate/company/contact),
resume upload (Emergent Object Storage), admin candidate/company CRUD,
notes, analytics, placements, invoices (CRUD + PDF), contact_messages.
"""
import io
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://voidd-hire-preview.preview.emergentagent.com",
).rstrip("/")

ADMIN_EMAIL = "admin@voiddhire.com"
ADMIN_PASSWORD = "Voidd@Admin2026"


@pytest.fixture(scope="session")
def session_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def admin_token(session_client):
    r = session_client.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    data = r.json()
    assert "token" in data and data["user"]["email"] == ADMIN_EMAIL
    return data["token"]


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ---------- Health ----------
def test_health(session_client):
    r = session_client.get(f"{BASE_URL}/api/health", timeout=15)
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "ok"
    assert j["service"] == "voidd-hire"


# ---------- Auth ----------
def test_login_invalid(session_client):
    r = session_client.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "nobody@example.com", "password": "wrong"},
        timeout=15,
    )
    assert r.status_code == 401


def test_login_success(admin_token):
    assert isinstance(admin_token, str) and len(admin_token) > 20


def test_me_without_token(session_client):
    r = session_client.get(f"{BASE_URL}/api/auth/me", timeout=15)
    assert r.status_code == 401


def test_me_with_token(admin_headers):
    r = requests.get(f"{BASE_URL}/api/auth/me", headers=admin_headers, timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert "admin" in data
    assert data["admin"]["email"] == ADMIN_EMAIL


# ---------- Public submissions ----------
@pytest.fixture(scope="session")
def created_candidate(session_client):
    payload = {
        "full_name": "TEST Candidate Alpha",
        "email": f"test_alpha_{uuid.uuid4().hex[:6]}@example.com",
        "phone": "+91-9000000000",
        "skills": "Python, FastAPI",
        "preferred_role": "Backend Engineer",
        "experience": "5",
    }
    r = session_client.post(f"{BASE_URL}/api/candidates", json=payload, timeout=20)
    assert r.status_code == 201, r.text
    data = r.json()
    assert "id" in data
    return {"id": data["id"], "payload": payload}


def test_create_candidate(created_candidate):
    assert created_candidate["id"]


def test_create_candidate_missing_field(session_client):
    r = session_client.post(
        f"{BASE_URL}/api/candidates",
        json={"full_name": "Only Name"},
        timeout=15,
    )
    assert r.status_code == 400


@pytest.fixture(scope="session")
def created_company(session_client):
    payload = {
        "company_name": "TEST Co Pvt Ltd",
        "hr_name": "TEST HR",
        "email": f"test_hr_{uuid.uuid4().hex[:6]}@example.com",
        "phone": "+91-9111111111",
        "required_role": "Senior Backend Engineer",
        "experience_required": "5+ yrs",
        "budget": "20-30 LPA",
        "urgency": "high",
    }
    r = session_client.post(f"{BASE_URL}/api/companies", json=payload, timeout=20)
    assert r.status_code == 201, r.text
    return {"id": r.json()["id"], "payload": payload}


def test_create_company(created_company):
    assert created_company["id"]


def test_create_company_missing_field(session_client):
    r = session_client.post(
        f"{BASE_URL}/api/companies",
        json={"company_name": "TEST"},
        timeout=15,
    )
    assert r.status_code == 400


def test_create_contact(session_client):
    r = session_client.post(
        f"{BASE_URL}/api/contact",
        json={
            "name": "TEST Contact",
            "email": "test_contact@example.com",
            "subject": "Hi",
            "message": "Hello team, this is a test message.",
        },
        timeout=15,
    )
    assert r.status_code == 201
    assert "id" in r.json()


# ---------- Resume upload (Emergent Object Storage) ----------
@pytest.fixture(scope="session")
def uploaded_resume():
    files = {
        "file": (
            "test_resume.txt",
            io.BytesIO(b"TEST resume content for VOIDD Hire end-to-end test."),
            "text/plain",
        ),
    }
    r = requests.post(f"{BASE_URL}/api/upload/resume", files=files, timeout=60)
    assert r.status_code == 200, f"upload failed: {r.status_code} {r.text}"
    data = r.json()
    assert "path" in data and data["filename"] == "test_resume.txt"
    assert data["size"] > 0
    return data


def test_upload_resume(uploaded_resume):
    assert uploaded_resume["path"].startswith("voidd-hire/resumes/") or "resumes/" in uploaded_resume["path"]


@pytest.fixture(scope="session")
def candidate_with_resume(session_client, uploaded_resume):
    payload = {
        "full_name": "TEST Candidate WithResume",
        "email": f"test_wr_{uuid.uuid4().hex[:6]}@example.com",
        "phone": "+91-9000000111",
        "resume_path": uploaded_resume["path"],
        "resume_filename": uploaded_resume["filename"],
    }
    r = session_client.post(f"{BASE_URL}/api/candidates", json=payload, timeout=20)
    assert r.status_code == 201
    return r.json()["id"]


# ---------- Admin: Candidates ----------
def test_admin_list_candidates_requires_token(session_client):
    r = session_client.get(f"{BASE_URL}/api/admin/candidates", timeout=15)
    assert r.status_code == 401


def test_admin_list_candidates(admin_headers, created_candidate):
    r = requests.get(f"{BASE_URL}/api/admin/candidates", headers=admin_headers, timeout=20)
    assert r.status_code == 200
    rows = r.json()
    assert isinstance(rows, list)
    assert any(c["id"] == created_candidate["id"] for c in rows)


def test_admin_list_candidates_filter_q(admin_headers):
    r = requests.get(
        f"{BASE_URL}/api/admin/candidates?q=Alpha",
        headers=admin_headers,
        timeout=20,
    )
    assert r.status_code == 200


def test_admin_get_candidate(admin_headers, created_candidate):
    r = requests.get(
        f"{BASE_URL}/api/admin/candidates/{created_candidate['id']}",
        headers=admin_headers,
        timeout=15,
    )
    assert r.status_code == 200
    assert r.json()["email"] == created_candidate["payload"]["email"]


def test_admin_patch_candidate(admin_headers, created_candidate):
    r = requests.patch(
        f"{BASE_URL}/api/admin/candidates/{created_candidate['id']}",
        headers=admin_headers,
        json={"status": "shortlisted", "is_shortlisted": True},
        timeout=15,
    )
    assert r.status_code == 200
    assert r.json()["is_shortlisted"] is True
    # verify persistence
    r2 = requests.get(
        f"{BASE_URL}/api/admin/candidates/{created_candidate['id']}",
        headers=admin_headers,
        timeout=15,
    )
    assert r2.json()["status"] == "shortlisted"


def test_admin_candidate_resume_download(admin_headers, candidate_with_resume):
    r = requests.get(
        f"{BASE_URL}/api/admin/candidates/{candidate_with_resume}/resume",
        headers={"Authorization": admin_headers["Authorization"]},
        timeout=60,
    )
    assert r.status_code == 200, r.text
    assert len(r.content) > 0


# ---------- Admin: Companies ----------
def test_admin_list_companies(admin_headers, created_company):
    r = requests.get(f"{BASE_URL}/api/admin/companies", headers=admin_headers, timeout=20)
    assert r.status_code == 200
    rows = r.json()
    assert any(c["id"] == created_company["id"] for c in rows)


def test_admin_patch_company_status(admin_headers, created_company):
    r = requests.patch(
        f"{BASE_URL}/api/admin/companies/{created_company['id']}",
        headers=admin_headers,
        json={"status": "qualified"},
        timeout=15,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "qualified"


# ---------- Admin: CRM Notes ----------
def test_admin_create_and_list_notes(admin_headers, created_candidate):
    r = requests.post(
        f"{BASE_URL}/api/admin/notes",
        headers=admin_headers,
        json={
            "entity_type": "candidate",
            "entity_id": created_candidate["id"],
            "note": "TEST CRM note from pytest",
            "interaction_type": "call",
        },
        timeout=15,
    )
    assert r.status_code == 201
    r2 = requests.get(
        f"{BASE_URL}/api/admin/notes/candidate/{created_candidate['id']}",
        headers=admin_headers,
        timeout=15,
    )
    assert r2.status_code == 200
    notes = r2.json()
    assert any(n["note"] == "TEST CRM note from pytest" for n in notes)


# ---------- Admin: Analytics ----------
def test_admin_analytics(admin_headers):
    r = requests.get(f"{BASE_URL}/api/admin/analytics", headers=admin_headers, timeout=20)
    assert r.status_code == 200
    data = r.json()
    for k in ("totals", "candidates_by_status", "companies_by_status", "trend"):
        assert k in data
    totals = data["totals"]
    for k in ("candidates", "companies", "shortlisted", "placements", "revenue_paid", "revenue_pending"):
        assert k in totals


# ---------- Admin: Placements ----------
@pytest.fixture(scope="session")
def created_placement(admin_headers, created_candidate, created_company):
    r = requests.post(
        f"{BASE_URL}/api/admin/placements",
        headers=admin_headers,
        json={
            "candidate_id": created_candidate["id"],
            "company_id": created_company["id"],
            "role": "Backend Engineer",
            "fee": 150000,
        },
        timeout=15,
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_create_placement(created_placement):
    assert "id" in created_placement


def test_placement_marks_candidate_placed(admin_headers, created_candidate, created_placement):
    r = requests.get(
        f"{BASE_URL}/api/admin/candidates/{created_candidate['id']}",
        headers=admin_headers,
        timeout=15,
    )
    assert r.json()["status"] == "placed"


def test_list_placements(admin_headers, created_placement):
    r = requests.get(f"{BASE_URL}/api/admin/placements", headers=admin_headers, timeout=15)
    assert r.status_code == 200
    assert any(p["id"] == created_placement["id"] for p in r.json())


# ---------- Admin: Invoices ----------
@pytest.fixture(scope="session")
def created_invoice(admin_headers, created_company):
    r = requests.post(
        f"{BASE_URL}/api/admin/invoices",
        headers=admin_headers,
        json={
            "company_id": created_company["id"],
            "company_name": created_company["payload"]["company_name"],
            "company_email": created_company["payload"]["email"],
            "candidate_name": "TEST Candidate Alpha",
            "role": "Backend Engineer",
            "placement_date": "2026-01-10",
            "placement_fee": 100000,
            "gst_rate": 18.0,
        },
        timeout=20,
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_create_invoice_computes_amounts(created_invoice):
    assert created_invoice["gst_amount"] == 18000
    assert created_invoice["total_amount"] == 118000
    assert created_invoice["invoice_number"].startswith("VH-")


def test_list_invoices(admin_headers, created_invoice):
    r = requests.get(f"{BASE_URL}/api/admin/invoices", headers=admin_headers, timeout=15)
    assert r.status_code == 200
    assert any(i["id"] == created_invoice["id"] for i in r.json())


def test_invoice_pdf(admin_headers, created_invoice):
    r = requests.get(
        f"{BASE_URL}/api/admin/invoices/{created_invoice['id']}/pdf",
        headers={"Authorization": admin_headers["Authorization"]},
        timeout=30,
    )
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/pdf")
    assert r.content[:4] == b"%PDF"


def test_invoice_mark_paid(admin_headers, created_invoice):
    r = requests.patch(
        f"{BASE_URL}/api/admin/invoices/{created_invoice['id']}",
        headers=admin_headers,
        json={"status": "paid"},
        timeout=15,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "paid"


# ---------- Admin: Contact messages ----------
def test_admin_contact_messages(admin_headers):
    r = requests.get(f"{BASE_URL}/api/admin/contact_messages", headers=admin_headers, timeout=15)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ---------- Admin: Delete candidate (last) ----------
def test_admin_delete_candidate(admin_headers, session_client):
    payload = {
        "full_name": "TEST Delete Me",
        "email": f"test_del_{uuid.uuid4().hex[:6]}@example.com",
        "phone": "+91-9999999999",
    }
    r = session_client.post(f"{BASE_URL}/api/candidates", json=payload, timeout=15)
    cid = r.json()["id"]
    rd = requests.delete(
        f"{BASE_URL}/api/admin/candidates/{cid}",
        headers=admin_headers,
        timeout=15,
    )
    assert rd.status_code == 200
    rg = requests.get(
        f"{BASE_URL}/api/admin/candidates/{cid}",
        headers=admin_headers,
        timeout=15,
    )
    assert rg.status_code == 404
