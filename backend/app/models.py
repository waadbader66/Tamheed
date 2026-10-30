import json
from datetime import datetime, date

from sqlalchemy import String, Text, Integer, ForeignKey, DateTime, Date, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def now() -> datetime:
    return datetime.utcnow()


class JSONMixin:
    @staticmethod
    def dump(v) -> str:
        return json.dumps(v, ensure_ascii=False)

    @staticmethod
    def load(v):
        return json.loads(v) if v else None


# ---------------- Company directory ----------------
class Department(Base):
    __tablename__ = "departments"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    mission: Mapped[str] = mapped_column(Text, default="")


class Role(Base):
    """A job role with required competencies, responsibilities and equipment."""
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(120), unique=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"))
    summary: Mapped[str] = mapped_column(Text, default="")
    skills_json: Mapped[str] = mapped_column(Text, default="[]")  # [{key,name,keywords[]}]
    responsibilities_json: Mapped[str] = mapped_column(Text, default="[]")  # [{title,detail,skills[]}]
    equipment_json: Mapped[str] = mapped_column(Text, default="[]")  # [{item,kind,reason}]
    work_example_json: Mapped[str] = mapped_column(Text, default="{}")
    department: Mapped[Department] = relationship()


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    client: Mapped[str] = mapped_column(String(200), default="")
    background: Mapped[str] = mapped_column(Text, default="")
    objectives_json: Mapped[str] = mapped_column(Text, default="[]")
    deliverables_json: Mapped[str] = mapped_column(Text, default="[]")
    phase: Mapped[str] = mapped_column(String(80), default="")


class Employee(Base):
    __tablename__ = "employees"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_code: Mapped[str] = mapped_column(String(40), unique=True)
    full_name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(200), unique=True)
    title: Mapped[str] = mapped_column(String(120))
    role_id: Mapped[int | None] = mapped_column(ForeignKey("roles.id"), nullable=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"))
    manager_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_new_hire: Mapped[bool] = mapped_column(Boolean, default=False)
    bio: Mapped[str] = mapped_column(Text, default="")
    experience_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    experience_text: Mapped[str] = mapped_column(Text, default="")
    qualifications: Mapped[str] = mapped_column(Text, default="")
    extra_context: Mapped[str] = mapped_column(Text, default="")
    responsibilities_text: Mapped[str] = mapped_column(Text, default="")  # HR-entered, one per line
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    role: Mapped[Role | None] = relationship()
    department: Mapped[Department] = relationship()
    project: Mapped[Project | None] = relationship()
    manager: Mapped["Employee | None"] = relationship(remote_side=[id])


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(200), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20))  # hr | employee
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    temp_password_expires: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    temp_hashes_json: Mapped[str] = mapped_column(Text, default="[]")  # every emailed temp password stays valid until first change
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    employee: Mapped[Employee | None] = relationship()


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    token_hash: Mapped[str] = mapped_column(String(80), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime)


# ---------------- Company knowledge (what the assistant searches) ----------------
class CompanyEmail(Base):
    __tablename__ = "company_emails"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)  # None = company-wide
    sender: Mapped[str] = mapped_column(String(200))
    recipients: Mapped[str] = mapped_column(Text)
    subject: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(DateTime)
    project: Mapped[Project | None] = relationship()


class CompanyDocument(Base):
    __tablename__ = "company_documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(60))  # policy | decision-log | charter | procedure | meeting-notes
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    project: Mapped[Project | None] = relationship()


class Course(Base):
    __tablename__ = "courses"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    provider: Mapped[str] = mapped_column(String(120), default="Rimal Academy (internal)")
    description: Mapped[str] = mapped_column(Text)
    skills_json: Mapped[str] = mapped_column(Text, default="[]")
    level: Mapped[str] = mapped_column(String(30), default="Foundation")
    hours: Mapped[float] = mapped_column(default=1.0)
    mandatory: Mapped[bool] = mapped_column(Boolean, default=False)
    available: Mapped[bool] = mapped_column(Boolean, default=True)
    external: Mapped[bool] = mapped_column(Boolean, default=False)
    url: Mapped[str] = mapped_column(String(500), default="")  # external courses only; verified reachable when seeded
    content_md: Mapped[str] = mapped_column(Text, default="")


# ---------------- Onboarding ----------------
class OnboardingCase(Base):
    __tablename__ = "onboarding_cases"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), unique=True)  # one case per hire
    status: Mapped[str] = mapped_column(String(30), default="preparing")  # preparing | ready | failed
    cv_filename: Mapped[str] = mapped_column(String(300), default="")
    cv_text: Mapped[str] = mapped_column(Text, default="")
    analysis_json: Mapped[str] = mapped_column(Text, default="")
    analysis_source: Mapped[str] = mapped_column(String(200), default="")
    plan_json: Mapped[str] = mapped_column(Text, default="")  # the onboarding agent's validated plan
    plan_source: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # everything required done
    completion_seen: Mapped[bool] = mapped_column(Boolean, default=False)  # HR dismissed the notification
    graduated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # moved to existing employees
    employee: Mapped[Employee] = relationship()


class JobStage(Base):
    """Persisted pipeline stage. Survives restarts; each stage is idempotent and retryable."""
    __tablename__ = "job_stages"
    __table_args__ = (UniqueConstraint("case_id", "key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("onboarding_cases.id"))
    key: Mapped[str] = mapped_column(String(40))
    label: Mapped[str] = mapped_column(String(200))
    position: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|running|done|failed
    detail: Mapped[str] = mapped_column(Text, default="")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class OnboardingTask(Base):
    __tablename__ = "onboarding_tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("onboarding_cases.id"))
    category: Mapped[str] = mapped_column(String(40))  # hr-paperwork | hardware | software | access | orientation
    title: Mapped[str] = mapped_column(String(300))
    detail: Mapped[str] = mapped_column(Text, default="")
    owner: Mapped[str] = mapped_column(String(40), default="employee")  # employee | hr | it
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | submitted | verified
    reason: Mapped[str] = mapped_column(Text, default="")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)


class ResponsibilityPlan(Base):
    __tablename__ = "responsibility_plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("onboarding_cases.id"))
    title: Mapped[str] = mapped_column(String(300))
    detail: Mapped[str] = mapped_column(Text, default="")
    support_level: Mapped[str] = mapped_column(String(30))  # independent | light-guidance | mentoring
    mentor_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    rationale: Mapped[str] = mapped_column(Text, default="")
    evidence_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(20), default="not-started")  # not-started | in-progress | done
    position: Mapped[int] = mapped_column(Integer, default=0)
    mentor: Mapped[Employee | None] = relationship()


class TrainingAssignment(Base):
    __tablename__ = "training_assignments"
    __table_args__ = (UniqueConstraint("case_id", "course_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("onboarding_cases.id"))
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))
    priority: Mapped[str] = mapped_column(String(20))  # mandatory | high | recommended | optional
    rationale: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="not-started")  # not-started | in-progress | completed
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    course: Mapped[Course] = relationship()


class Artifact(Base):
    __tablename__ = "artifacts"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("onboarding_cases.id"))
    kind: Mapped[str] = mapped_column(String(40))  # video | cv | script
    title: Mapped[str] = mapped_column(String(300))
    rel_path: Mapped[str] = mapped_column(String(500))
    mime: Mapped[str] = mapped_column(String(100))
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    meta_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Invitation(Base):
    __tablename__ = "invitations"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), unique=True)  # never duplicated
    username: Mapped[str] = mapped_column(String(200))
    to_email: Mapped[str] = mapped_column(String(200))
    view_token: Mapped[str] = mapped_column(String(80), unique=True)
    status: Mapped[str] = mapped_column(String(40), default="prepared")
    # prepared | waiting-sender-config | blocked-not-allowlisted | sent | failed
    detail: Mapped[str] = mapped_column(Text, default="")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    viewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    first_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    employee: Mapped[Employee] = relationship()


class Exercise(Base):
    """A practical exercise designed by the agent for one responsibility; graded by AI, confirmed by HR."""
    __tablename__ = "exercises"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("onboarding_cases.id"))
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    responsibility: Mapped[str] = mapped_column(String(300), default="")
    title: Mapped[str] = mapped_column(String(300))
    scenario: Mapped[str] = mapped_column(Text)
    worksheet_json: Mapped[str] = mapped_column(Text, default="{}")  # {"columns": [...], "rows": [[...]], "notes": "..."}
    task: Mapped[str] = mapped_column(Text)
    deliverable: Mapped[str] = mapped_column(Text, default="")
    minutes: Mapped[int] = mapped_column(Integer, default=45)
    rubric_json: Mapped[str] = mapped_column(Text, default="[]")  # [{"criterion", "points"}]
    answer_key_json: Mapped[str] = mapped_column(Text, default="[]")  # hidden from the employee
    sources_json: Mapped[str] = mapped_column(Text, default="[]")
    source: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(20), default="open")  # open | submitted | assessed
    mentor_review_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    answer: Mapped[str] = mapped_column(Text, default="")
    ai_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ai_feedback: Mapped[str] = mapped_column(Text, default="")
    ai_breakdown_json: Mapped[str] = mapped_column(Text, default="[]")
    grade_source: Mapped[str] = mapped_column(String(120), default="")
    final_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reviewer_comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AgentEvent(Base):
    """What the onboarding agent did and decided: shown live to HR and kept as an audit trail."""
    __tablename__ = "agent_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("onboarding_cases.id"))
    run: Mapped[str] = mapped_column(String(40), default="plan")  # plan | adapt-N | review-N
    kind: Mapped[str] = mapped_column(String(20))  # thinking | tool | decision | guardrail | fallback | plan-update | next-step
    text: Mapped[str] = mapped_column(Text)
    data_json: Mapped[str] = mapped_column(Text, default="{}")
    visible_to_employee: Mapped[bool] = mapped_column(Boolean, default=False)
    at: Mapped[datetime] = mapped_column(DateTime, default=now)


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(String(20))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    meta_json: Mapped[str] = mapped_column(Text, default="{}")  # sources, steps, engine
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor: Mapped[str] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(100))
    target: Mapped[str] = mapped_column(String(200), default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    at: Mapped[datetime] = mapped_column(DateTime, default=now)


def audit(db, actor: str, action: str, target: str = "", detail: str = "") -> None:
    db.add(AuditLog(actor=actor, action=action, target=target, detail=detail))
