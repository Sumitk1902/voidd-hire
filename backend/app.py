"""VOIDD Hire — Flask application.

Single app serving both HTML pages and /api/* JSON endpoints.
Runs on port 8001 (for /api routes via FastAPI WSGI wrapper) and
port 3000 (for HTML pages) — both via the Emergent ingress.
"""
import os
import uuid
import logging
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

print(os.getenv("DATABASE_URL"))
from flask import (
    Flask, render_template, request, jsonify, send_file, Response,
)
from sqlalchemy import func, desc
from sqlalchemy.exc import IntegrityError
from io import BytesIO

from db import (
    init_db, get_session, AdminUser, Candidate, CompanyInquiry,
    CRMNote, Invoice, Placement, ContactMessage,
)
from auth import (
    hash_password, verify_password, create_token, admin_required,
)
from storage import put_object, get_object, init_storage, APP_NAME
from invoice import generate_invoice_pdf
from matching import score_candidate, rank_candidates

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

flask_app = Flask(
    __name__,
    template_folder=str(ROOT_DIR / "templates"),
    static_folder=str(ROOT_DIR / "static"),
    static_url_path="/static",
)
flask_app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB uploads


# ---------- Startup ----------
def seed_admin():
    session = get_session()
    try:
        email = os.environ["ADMIN_EMAIL"].strip().lower()
        password = os.environ["ADMIN_PASSWORD"]
        existing = session.query(AdminUser).filter_by(email=email).first()
        if existing:
            # Refresh password if env changes (idempotent)
            if not verify_password(password, existing.password_hash):
                existing.password_hash = hash_password(password)
                session.commit()
                logger.info("Admin password refreshed from env")
            return
        admin = AdminUser(
            email=email,
            password_hash=hash_password(password),
            name=os.environ.get("ADMIN_NAME", "VOIDD Admin"),
        )
        session.add(admin)
        session.commit()
        logger.info(f"Seeded admin user: {email}")
    except Exception as e:
        session.rollback()
        logger.exception(f"seed_admin failed: {e}")
    finally:
        session.close()


def bootstrap():
    try:
        init_db()
        logger.info("DB initialized")
        seed_admin()
    except Exception as e:
        logger.exception(f"DB bootstrap failed: {e}")
    try:
        init_storage()
    except Exception as e:
        logger.warning(f"Storage init deferred: {e}")


bootstrap()


# ---------- Helpers ----------
def candidate_to_dict(c: Candidate) -> dict:
    return {
        "id": c.id,
        "full_name": c.full_name,
        "email": c.email,
        "phone": c.phone,
        "location": c.location,
        "skills": c.skills,
        "experience": c.experience,
        "preferred_role": c.preferred_role,
        "salary_expectation": c.salary_expectation,
        "resume_path": c.resume_path,
        "resume_filename": c.resume_filename,
        "linkedin": c.linkedin,
        "portfolio": c.portfolio,
        "status": c.status,
        "is_shortlisted": c.is_shortlisted,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def company_to_dict(c: CompanyInquiry) -> dict:
    return {
        "id": c.id,
        "company_name": c.company_name,
        "hr_name": c.hr_name,
        "email": c.email,
        "phone": c.phone,
        "required_role": c.required_role,
        "experience_required": c.experience_required,
        "budget": c.budget,
        "urgency": c.urgency,
        "skills_required": c.skills_required,
        "hiring_timeline": c.hiring_timeline,
        "additional_notes": c.additional_notes,
        "status": c.status,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def invoice_to_dict(i: Invoice) -> dict:
    return {
        "id": i.id,
        "invoice_number": i.invoice_number,
        "company_id": i.company_id,
        "company_name": i.company_name,
        "company_email": i.company_email,
        "company_address": i.company_address,
        "company_gstin": i.company_gstin,
        "candidate_name": i.candidate_name,
        "role": i.role,
        "placement_date": i.placement_date,
        "placement_fee": i.placement_fee,
        "gst_rate": i.gst_rate,
        "gst_amount": i.gst_amount,
        "total_amount": i.total_amount,
        "notes": i.notes,
        "status": i.status,
        "created_at": i.created_at.isoformat() if i.created_at else None,
    }


# ---------- Page routes (served on port 3000) ----------
@flask_app.route("/")
def page_home():
    return render_template("index.html", active="home")


@flask_app.route("/candidate")
def page_candidate():
    return render_template("candidate.html", active="candidate")


@flask_app.route("/company")
def page_company():
    return render_template("company.html", active="company")


@flask_app.route("/about")
def page_about():
    return render_template("about.html", active="about")


@flask_app.route("/contact")
def page_contact():
    return render_template("contact.html", active="contact")


@flask_app.route("/login")
def page_login():
    return render_template("login.html", active="login")


@flask_app.route("/admin")
def page_admin():
    return render_template("admin.html", active="admin")


# ---------- Health ----------
@flask_app.route("/api/health")
def api_health():
    return jsonify({"status": "ok", "service": "voidd-hire"})


# ---------- Auth ----------
@flask_app.route("/api/auth/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not email or not password:
        return jsonify({"error": "email and password required"}), 400
    session = get_session()
    try:
        user = session.query(AdminUser).filter_by(email=email).first()
        if not user or not verify_password(password, user.password_hash):
            return jsonify({"error": "Invalid credentials"}), 401
        token = create_token(user.id, user.email)
        return jsonify({
            "token": token,
            "user": {"id": user.id, "email": user.email, "name": user.name},
        })
    finally:
        session.close()


@flask_app.route("/api/auth/me", methods=["GET"])
@admin_required
def api_me():
    return jsonify({"admin": request.admin})


# ---------- Public submissions ----------
@flask_app.route("/api/candidates", methods=["POST"])
def api_create_candidate():
    data = request.get_json(silent=True) or {}
    required = ["full_name", "email", "phone"]
    for f in required:
        if not data.get(f):
            return jsonify({"error": f"{f} is required"}), 400
    session = get_session()
    try:
        c = Candidate(
            full_name=data["full_name"].strip(),
            email=data["email"].strip().lower(),
            phone=data["phone"].strip(),
            location=data.get("location", "").strip() or None,
            skills=data.get("skills", "").strip() or None,
            experience=data.get("experience", "").strip() or None,
            preferred_role=data.get("preferred_role", "").strip() or None,
            salary_expectation=data.get("salary_expectation", "").strip() or None,
            resume_path=data.get("resume_path") or None,
            resume_filename=data.get("resume_filename") or None,
            linkedin=data.get("linkedin", "").strip() or None,
            portfolio=data.get("portfolio", "").strip() or None,
        )
        session.add(c)
        session.commit()
        return jsonify({"id": c.id, "status": "received"}), 201
    except Exception as e:
        session.rollback()
        logger.exception("create_candidate failed")
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@flask_app.route("/api/companies", methods=["POST"])
def api_create_company():
    data = request.get_json(silent=True) or {}
    required = ["company_name", "hr_name", "email", "phone", "required_role"]
    for f in required:
        if not data.get(f):
            return jsonify({"error": f"{f} is required"}), 400
    session = get_session()
    try:
        c = CompanyInquiry(
            company_name=data["company_name"].strip(),
            hr_name=data["hr_name"].strip(),
            email=data["email"].strip().lower(),
            phone=data["phone"].strip(),
            required_role=data["required_role"].strip(),
            experience_required=data.get("experience_required", "").strip() or None,
            budget=data.get("budget", "").strip() or None,
            urgency=data.get("urgency", "").strip() or None,
            skills_required=data.get("skills_required", "").strip() or None,
            hiring_timeline=data.get("hiring_timeline", "").strip() or None,
            additional_notes=data.get("additional_notes", "").strip() or None,
        )
        session.add(c)
        session.commit()
        return jsonify({"id": c.id, "status": "received"}), 201
    except Exception as e:
        session.rollback()
        logger.exception("create_company failed")
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@flask_app.route("/api/contact", methods=["POST"])
def api_create_contact():
    data = request.get_json(silent=True) or {}
    if not data.get("name") or not data.get("email") or not data.get("message"):
        return jsonify({"error": "name, email, and message are required"}), 400
    session = get_session()
    try:
        m = ContactMessage(
            name=data["name"].strip(),
            email=data["email"].strip().lower(),
            subject=(data.get("subject") or "").strip() or None,
            message=data["message"].strip(),
        )
        session.add(m)
        session.commit()
        return jsonify({"id": m.id, "status": "received"}), 201
    finally:
        session.close()


# ---------- Resume upload (public, attached to candidate submission) ----------
ALLOWED_RESUME_EXT = {"pdf", "doc", "docx", "rtf", "txt"}


@flask_app.route("/api/upload/resume", methods=["POST"])
def api_upload_resume():
    if "file" not in request.files:
        return jsonify({"error": "file is required"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "empty filename"}), 400
    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else "bin"
    if ext not in ALLOWED_RESUME_EXT:
        return jsonify({"error": f"unsupported extension .{ext}"}), 400
    data = f.read()
    if len(data) > 8 * 1024 * 1024:
        return jsonify({"error": "file exceeds 8MB limit"}), 400
    content_type = f.mimetype or "application/octet-stream"
    path = f"{APP_NAME}/resumes/{uuid.uuid4()}.{ext}"
    try:
        result = put_object(path, data, content_type)
    except Exception as e:
        logger.exception("resume upload failed")
        return jsonify({"error": f"upload failed: {e}"}), 500
    return jsonify({
        "path": result["path"],
        "filename": f.filename,
        "size": result.get("size", len(data)),
        "content_type": content_type,
    })


# ---------- Admin: Candidates ----------
@flask_app.route("/api/admin/candidates", methods=["GET"])
@admin_required
def api_admin_list_candidates():
    q = (request.args.get("q") or "").strip().lower()
    status = request.args.get("status")
    shortlisted = request.args.get("shortlisted")
    session = get_session()
    try:
        query = session.query(Candidate)
        if status:
            query = query.filter(Candidate.status == status)
        if shortlisted in ("true", "1"):
            query = query.filter(Candidate.is_shortlisted.is_(True))
        if q:
            like = f"%{q}%"
            query = query.filter(
                (func.lower(Candidate.full_name).like(like))
                | (func.lower(Candidate.email).like(like))
                | (func.lower(Candidate.skills).like(like))
                | (func.lower(Candidate.preferred_role).like(like))
            )
        rows = query.order_by(desc(Candidate.created_at)).limit(500).all()
        return jsonify([candidate_to_dict(c) for c in rows])
    finally:
        session.close()


@flask_app.route("/api/admin/candidates/<cid>", methods=["GET"])
@admin_required
def api_admin_get_candidate(cid):
    session = get_session()
    try:
        c = session.query(Candidate).filter_by(id=cid).first()
        if not c:
            return jsonify({"error": "not found"}), 404
        return jsonify(candidate_to_dict(c))
    finally:
        session.close()


@flask_app.route("/api/admin/candidates/<cid>", methods=["PATCH"])
@admin_required
def api_admin_update_candidate(cid):
    data = request.get_json(silent=True) or {}
    session = get_session()
    try:
        c = session.query(Candidate).filter_by(id=cid).first()
        if not c:
            return jsonify({"error": "not found"}), 404
        for field in ("status", "preferred_role", "location", "salary_expectation"):
            if field in data:
                setattr(c, field, data[field])
        if "is_shortlisted" in data:
            c.is_shortlisted = bool(data["is_shortlisted"])
        session.commit()
        return jsonify(candidate_to_dict(c))
    finally:
        session.close()


@flask_app.route("/api/admin/candidates/<cid>", methods=["DELETE"])
@admin_required
def api_admin_delete_candidate(cid):
    session = get_session()
    try:
        c = session.query(Candidate).filter_by(id=cid).first()
        if not c:
            return jsonify({"error": "not found"}), 404
        session.delete(c)
        session.commit()
        return jsonify({"deleted": True})
    finally:
        session.close()


@flask_app.route("/api/admin/candidates/<cid>/resume", methods=["GET"])
@admin_required
def api_admin_download_resume(cid):
    session = get_session()
    try:
        c = session.query(Candidate).filter_by(id=cid).first()
        if not c or not c.resume_path:
            return jsonify({"error": "no resume"}), 404
        data, ctype = get_object(c.resume_path)
        resp = Response(data, mimetype=ctype)
        fn = c.resume_filename or f"resume-{cid}"
        resp.headers["Content-Disposition"] = f'inline; filename="{fn}"'
        return resp
    except Exception as e:
        logger.exception("download_resume failed")
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


# ---------- Admin: Companies ----------
@flask_app.route("/api/admin/companies", methods=["GET"])
@admin_required
def api_admin_list_companies():
    q = (request.args.get("q") or "").strip().lower()
    status = request.args.get("status")
    session = get_session()
    try:
        query = session.query(CompanyInquiry)
        if status:
            query = query.filter(CompanyInquiry.status == status)
        if q:
            like = f"%{q}%"
            query = query.filter(
                (func.lower(CompanyInquiry.company_name).like(like))
                | (func.lower(CompanyInquiry.email).like(like))
                | (func.lower(CompanyInquiry.required_role).like(like))
            )
        rows = query.order_by(desc(CompanyInquiry.created_at)).limit(500).all()
        return jsonify([company_to_dict(c) for c in rows])
    finally:
        session.close()


@flask_app.route("/api/admin/companies/<cid>", methods=["GET"])
@admin_required
def api_admin_get_company(cid):
    session = get_session()
    try:
        c = session.query(CompanyInquiry).filter_by(id=cid).first()
        if not c:
            return jsonify({"error": "not found"}), 404
        return jsonify(company_to_dict(c))
    finally:
        session.close()


@flask_app.route("/api/admin/companies/<cid>", methods=["PATCH"])
@admin_required
def api_admin_update_company(cid):
    data = request.get_json(silent=True) or {}
    session = get_session()
    try:
        c = session.query(CompanyInquiry).filter_by(id=cid).first()
        if not c:
            return jsonify({"error": "not found"}), 404
        for field in ("status", "urgency", "budget", "required_role"):
            if field in data:
                setattr(c, field, data[field])
        session.commit()
        return jsonify(company_to_dict(c))
    finally:
        session.close()


# ---------- Admin: Matching ----------
@flask_app.route("/api/admin/companies/<cid>/matches", methods=["GET"])
@admin_required
def api_admin_company_matches(cid):
    """Return ranked candidate matches for a company brief."""
    try:
        limit = int(request.args.get("limit", "20"))
    except ValueError:
        limit = 20
    session = get_session()
    try:
        company = session.query(CompanyInquiry).filter_by(id=cid).first()
        if not company:
            return jsonify({"error": "company not found"}), 404
        candidates = (
            session.query(Candidate)
            .filter(Candidate.status != "rejected")
            .order_by(desc(Candidate.created_at))
            .limit(500)
            .all()
        )
        ranked = rank_candidates(candidates, company, limit=limit)
        return jsonify({
            "company": {
                "id": company.id,
                "company_name": company.company_name,
                "required_role": company.required_role,
                "experience_required": company.experience_required,
                "budget": company.budget,
                "skills_required": company.skills_required,
            },
            "matches": ranked,
        })
    finally:
        session.close()


@flask_app.route("/api/admin/candidates/<cand_id>/match/<comp_id>", methods=["GET"])
@admin_required
def api_admin_candidate_match(cand_id, comp_id):
    session = get_session()
    try:
        cand = session.query(Candidate).filter_by(id=cand_id).first()
        comp = session.query(CompanyInquiry).filter_by(id=comp_id).first()
        if not cand or not comp:
            return jsonify({"error": "not found"}), 404
        return jsonify(score_candidate(cand, comp))
    finally:
        session.close()



# ---------- Admin: CRM notes ----------
@flask_app.route("/api/admin/notes", methods=["POST"])
@admin_required
def api_admin_create_note():
    data = request.get_json(silent=True) or {}
    if not data.get("entity_type") or not data.get("entity_id") or not data.get("note"):
        return jsonify({"error": "entity_type, entity_id, note required"}), 400
    session = get_session()
    try:
        n = CRMNote(
            entity_type=data["entity_type"],
            entity_id=data["entity_id"],
            note=data["note"].strip(),
            author=request.admin.get("email", "Admin"),
            interaction_type=data.get("interaction_type", "note"),
        )
        session.add(n)
        session.commit()
        return jsonify({
            "id": n.id,
            "entity_type": n.entity_type,
            "entity_id": n.entity_id,
            "note": n.note,
            "author": n.author,
            "interaction_type": n.interaction_type,
            "created_at": n.created_at.isoformat(),
        }), 201
    finally:
        session.close()


@flask_app.route("/api/admin/notes/<entity_type>/<entity_id>", methods=["GET"])
@admin_required
def api_admin_list_notes(entity_type, entity_id):
    session = get_session()
    try:
        rows = (
            session.query(CRMNote)
            .filter_by(entity_type=entity_type, entity_id=entity_id)
            .order_by(desc(CRMNote.created_at))
            .all()
        )
        return jsonify([{
            "id": n.id,
            "note": n.note,
            "author": n.author,
            "interaction_type": n.interaction_type,
            "created_at": n.created_at.isoformat(),
        } for n in rows])
    finally:
        session.close()


# ---------- Admin: Analytics ----------
@flask_app.route("/api/admin/analytics", methods=["GET"])
@admin_required
def api_admin_analytics():
    session = get_session()
    try:
        total_candidates = session.query(func.count(Candidate.id)).scalar() or 0
        total_companies = session.query(func.count(CompanyInquiry.id)).scalar() or 0
        shortlisted = (
            session.query(func.count(Candidate.id))
            .filter(Candidate.is_shortlisted.is_(True)).scalar() or 0
        )
        placements = session.query(func.count(Placement.id)).scalar() or 0
        revenue = session.query(func.coalesce(func.sum(Invoice.total_amount), 0.0)).filter(
            Invoice.status == "paid"
        ).scalar() or 0.0
        pending_revenue = session.query(func.coalesce(func.sum(Invoice.total_amount), 0.0)).filter(
            Invoice.status == "pending"
        ).scalar() or 0.0

        # by status
        cand_by_status = dict(
            session.query(Candidate.status, func.count(Candidate.id))
            .group_by(Candidate.status).all()
        )
        comp_by_status = dict(
            session.query(CompanyInquiry.status, func.count(CompanyInquiry.id))
            .group_by(CompanyInquiry.status).all()
        )

        # last 12 weeks trend (candidates created per week) — keep simple: just last 30 records
        recent_candidates = (
            session.query(Candidate.created_at)
            .order_by(desc(Candidate.created_at)).limit(60).all()
        )
        # group by date
        trend = {}
        for (dt,) in recent_candidates:
            if not dt:
                continue
            key = dt.strftime("%Y-%m-%d")
            trend[key] = trend.get(key, 0) + 1
        trend_list = sorted([{"date": k, "count": v} for k, v in trend.items()], key=lambda x: x["date"])

        return jsonify({
            "totals": {
                "candidates": total_candidates,
                "companies": total_companies,
                "shortlisted": shortlisted,
                "placements": placements,
                "revenue_paid": float(revenue),
                "revenue_pending": float(pending_revenue),
            },
            "candidates_by_status": cand_by_status,
            "companies_by_status": comp_by_status,
            "trend": trend_list,
        })
    finally:
        session.close()


# ---------- Admin: Placements ----------
@flask_app.route("/api/admin/placements", methods=["POST"])
@admin_required
def api_admin_create_placement():
    data = request.get_json(silent=True) or {}
    if not data.get("candidate_id") or not data.get("company_id"):
        return jsonify({"error": "candidate_id and company_id required"}), 400
    session = get_session()
    try:
        cand = session.query(Candidate).filter_by(id=data["candidate_id"]).first()
        comp = session.query(CompanyInquiry).filter_by(id=data["company_id"]).first()
        if not cand or not comp:
            return jsonify({"error": "candidate or company not found"}), 404
        p = Placement(
            candidate_id=cand.id,
            company_id=comp.id,
            candidate_name=cand.full_name,
            company_name=comp.company_name,
            role=data.get("role") or comp.required_role,
            fee=float(data.get("fee") or 0),
        )
        cand.status = "placed"
        session.add(p)
        session.commit()
        return jsonify({"id": p.id, "candidate_id": p.candidate_id, "company_id": p.company_id}), 201
    finally:
        session.close()


@flask_app.route("/api/admin/placements", methods=["GET"])
@admin_required
def api_admin_list_placements():
    session = get_session()
    try:
        rows = session.query(Placement).order_by(desc(Placement.placed_at)).limit(200).all()
        return jsonify([{
            "id": p.id,
            "candidate_id": p.candidate_id,
            "company_id": p.company_id,
            "candidate_name": p.candidate_name,
            "company_name": p.company_name,
            "role": p.role,
            "fee": p.fee,
            "placed_at": p.placed_at.isoformat() if p.placed_at else None,
        } for p in rows])
    finally:
        session.close()


# ---------- Admin: Invoices ----------
def _next_invoice_number(session) -> str:
    year = datetime.utcnow().year
    count = session.query(func.count(Invoice.id)).scalar() or 0
    return f"VH-{year}-{count + 1:04d}"


@flask_app.route("/api/admin/invoices", methods=["GET"])
@admin_required
def api_admin_list_invoices():
    session = get_session()
    try:
        rows = session.query(Invoice).order_by(desc(Invoice.created_at)).limit(200).all()
        return jsonify([invoice_to_dict(i) for i in rows])
    finally:
        session.close()


@flask_app.route("/api/admin/invoices", methods=["POST"])
@admin_required
def api_admin_create_invoice():
    data = request.get_json(silent=True) or {}
    if not data.get("company_name") or data.get("placement_fee") is None:
        return jsonify({"error": "company_name and placement_fee required"}), 400
    session = get_session()
    try:
        fee = float(data["placement_fee"])
        gst_rate = float(data.get("gst_rate", 18.0))
        gst_amount = round(fee * gst_rate / 100, 2)
        total = round(fee + gst_amount, 2)
        inv = Invoice(
            invoice_number=_next_invoice_number(session),
            company_id=data.get("company_id"),
            company_name=data["company_name"].strip(),
            company_email=(data.get("company_email") or "").strip() or None,
            company_address=(data.get("company_address") or "").strip() or None,
            company_gstin=(data.get("company_gstin") or "").strip() or None,
            candidate_name=(data.get("candidate_name") or "").strip() or None,
            role=(data.get("role") or "").strip() or None,
            placement_date=(data.get("placement_date") or "").strip() or None,
            placement_fee=fee,
            gst_rate=gst_rate,
            gst_amount=gst_amount,
            total_amount=total,
            notes=(data.get("notes") or "").strip() or None,
            status=data.get("status", "pending"),
        )
        session.add(inv)
        session.commit()
        return jsonify(invoice_to_dict(inv)), 201
    except Exception as e:
        session.rollback()
        logger.exception("create_invoice failed")
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@flask_app.route("/api/admin/invoices/<iid>", methods=["PATCH"])
@admin_required
def api_admin_update_invoice(iid):
    data = request.get_json(silent=True) or {}
    session = get_session()
    try:
        inv = session.query(Invoice).filter_by(id=iid).first()
        if not inv:
            return jsonify({"error": "not found"}), 404
        if "status" in data:
            inv.status = data["status"]
        session.commit()
        return jsonify(invoice_to_dict(inv))
    finally:
        session.close()


@flask_app.route("/api/admin/invoices/<iid>/pdf", methods=["GET"])
@admin_required
def api_admin_invoice_pdf(iid):
    session = get_session()
    try:
        inv = session.query(Invoice).filter_by(id=iid).first()
        if not inv:
            return jsonify({"error": "not found"}), 404
        d = invoice_to_dict(inv)
        d["date"] = (inv.created_at.strftime("%d %b %Y") if inv.created_at else "")
        pdf = generate_invoice_pdf(d)
        return send_file(
            BytesIO(pdf),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"{inv.invoice_number}.pdf",
        )
    finally:
        session.close()


# ---------- Admin: Contact messages ----------
@flask_app.route("/api/admin/contact_messages", methods=["GET"])
@admin_required
def api_admin_contact_messages():
    session = get_session()
    try:
        rows = session.query(ContactMessage).order_by(desc(ContactMessage.created_at)).limit(200).all()
        return jsonify([{
            "id": m.id,
            "name": m.name,
            "email": m.email,
            "subject": m.subject,
            "message": m.message,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        } for m in rows])
    finally:
        session.close()


# ---------- Error handlers ----------
@flask_app.errorhandler(404)
def not_found(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "not found"}), 404
    return render_template("index.html", active="home"), 200


@flask_app.errorhandler(413)
def too_large(e):
    return jsonify({"error": "file too large"}), 413


# Allow running directly for the frontend port
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "3000"))
    flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
