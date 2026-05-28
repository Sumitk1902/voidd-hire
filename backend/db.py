"""SQLAlchemy models and DB engine for VOIDD Hire."""
import os
from datetime import datetime, timezone
from sqlalchemy import (
    create_engine, Column, String, Text, Integer, Float, DateTime,
    ForeignKey, Boolean
)
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session, relationship
from sqlalchemy.pool import NullPool
import uuid

from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

_engine_kwargs = dict(pool_pre_ping=True)
if DATABASE_URL.startswith("postgresql"):
    # Supabase Transaction Pooler (port 6543) handles pooling itself —
    # use NullPool here to avoid double-pooling and stale-connection issues.
    if "pooler.supabase.com" in DATABASE_URL:
        _engine_kwargs = dict(poolclass=NullPool)
    else:
        _engine_kwargs.update(pool_size=5, max_overflow=10, pool_recycle=1800)
else:
    # sqlite — single-process safe defaults
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **_engine_kwargs)
SessionLocal = scoped_session(
    sessionmaker(autocommit=False, autoflush=False, bind=engine)
)
Base = declarative_base()


def gen_uuid():
    return str(uuid.uuid4())


def utcnow():
    return datetime.now(timezone.utc)


class AdminUser(Base):
    __tablename__ = "admin_users"
    id = Column(String, primary_key=True, default=gen_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    name = Column(String, nullable=False, default="Admin")
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class Candidate(Base):
    __tablename__ = "candidates"
    id = Column(String, primary_key=True, default=gen_uuid)
    full_name = Column(String, nullable=False)
    email = Column(String, nullable=False, index=True)
    phone = Column(String, nullable=False)
    location = Column(String)
    skills = Column(Text)
    experience = Column(String)  # e.g. "3 years"
    preferred_role = Column(String)
    salary_expectation = Column(String)
    resume_path = Column(String)  # storage path
    resume_filename = Column(String)
    linkedin = Column(String)
    portfolio = Column(String)
    status = Column(String, default="new", nullable=False)  # new, contacted, shortlisted, placed, rejected
    is_shortlisted = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class CompanyInquiry(Base):
    __tablename__ = "company_inquiries"
    id = Column(String, primary_key=True, default=gen_uuid)
    company_name = Column(String, nullable=False)
    hr_name = Column(String, nullable=False)
    email = Column(String, nullable=False, index=True)
    phone = Column(String, nullable=False)
    required_role = Column(String, nullable=False)
    experience_required = Column(String)
    budget = Column(String)
    urgency = Column(String)  # immediate, 1_month, 3_months, flexible
    skills_required = Column(Text)
    hiring_timeline = Column(String)
    additional_notes = Column(Text)
    status = Column(String, default="new", nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class CRMNote(Base):
    __tablename__ = "crm_notes"
    id = Column(String, primary_key=True, default=gen_uuid)
    entity_type = Column(String, nullable=False)  # candidate | company
    entity_id = Column(String, nullable=False, index=True)
    note = Column(Text, nullable=False)
    author = Column(String, default="Admin")
    interaction_type = Column(String, default="note")  # note, call, email, meeting
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class Invoice(Base):
    __tablename__ = "invoices"
    id = Column(String, primary_key=True, default=gen_uuid)
    invoice_number = Column(String, unique=True, nullable=False)
    company_id = Column(String, ForeignKey("company_inquiries.id"))
    company_name = Column(String, nullable=False)
    company_email = Column(String)
    company_address = Column(Text)
    company_gstin = Column(String)
    candidate_name = Column(String)
    role = Column(String)
    placement_date = Column(String)
    placement_fee = Column(Float, nullable=False)
    gst_rate = Column(Float, default=18.0)
    gst_amount = Column(Float, default=0.0)
    total_amount = Column(Float, nullable=False)
    notes = Column(Text)
    status = Column(String, default="pending")  # pending, paid, overdue
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class Placement(Base):
    __tablename__ = "placements"
    id = Column(String, primary_key=True, default=gen_uuid)
    candidate_id = Column(String, ForeignKey("candidates.id"), nullable=False)
    company_id = Column(String, ForeignKey("company_inquiries.id"), nullable=False)
    candidate_name = Column(String)
    company_name = Column(String)
    role = Column(String)
    fee = Column(Float, default=0.0)
    placed_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class ContactMessage(Base):
    __tablename__ = "contact_messages"
    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    subject = Column(String)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


def init_db():
    """Create all tables. Idempotent."""
    Base.metadata.create_all(bind=engine)


def get_session():
    return SessionLocal()
