"""Academy: coaches, programs, batches, students, sessions, attendance."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import TenantScoped
from app.db.types import enum_type, money


class CoachType(StrEnum):
    FULL_TIME = "full-time"
    PART_TIME = "part-time"
    GUEST = "guest"
    VISITING = "visiting"


class CoachStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ON_LEAVE = "on-leave"


class StudentStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    INACTIVE = "inactive"


class SessionStatus(StrEnum):
    SCHEDULED = "scheduled"
    ONGOING = "ongoing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class BatchStatus(StrEnum):
    ACTIVE = "active"
    UPCOMING = "upcoming"
    COMPLETED = "completed"


class AttendanceStatus(StrEnum):
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    NOT_STARTED = "not-started"


class EnrollmentStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Coach(TenantScoped):
    """A coach. ← `Coach` in src/pages/Coaching.tsx.

    `activeBatches` and `totalStudents` from the frontend are derived — they are
    counts over batches and enrolments, and a stored copy drifts the moment a
    student transfers between batches.
    """

    __tablename__ = "coach"
    __table_args__ = (
        Index("uq_coach_tenant_number", "tenant_id", "coach_no", unique=True),
        Index("ix_coach_tenant_status", "tenant_id", "status"),
        Index(
            "uq_coach_tenant_email",
            "tenant_id",
            text("lower(email)"),
            unique=True,
            postgresql_where=text("email IS NOT NULL"),
        ),
    )

    coach_no: Mapped[str] = mapped_column(String(32), nullable=False)  # XC-C-001
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(320))
    avatar_initials: Mapped[str | None] = mapped_column(String(4))
    gender: Mapped[str | None] = mapped_column(String(20))

    specialization: Mapped[str | None] = mapped_column(Text)
    type: Mapped[CoachType] = mapped_column(
        enum_type(CoachType, name="coach_type"), default=CoachType.FULL_TIME, nullable=False
    )
    experience_years: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    certifications: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    languages: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)

    joining_date: Mapped[date | None] = mapped_column(Date)
    salary: Mapped[Decimal] = mapped_column(money(), default=0, nullable=False)
    hourly_rate: Mapped[Decimal] = mapped_column(money(), default=0, nullable=False)

    morning_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    evening_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    rating: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=0, nullable=False)
    status: Mapped[CoachStatus] = mapped_column(
        enum_type(CoachStatus, name="coach_status"), default=CoachStatus.ACTIVE, nullable=False
    )
    bio: Mapped[str | None] = mapped_column(Text)

    # A coach who also logs in to the app. Nullable because most do not.
    user_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True))

    sports: Mapped[list[CoachSport]] = relationship(
        back_populates="coach", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Coach {self.coach_no} {self.name}>"


class CoachSport(TenantScoped):
    """Which sports a coach teaches.

    `Coach.sport: string[]` in the frontend becomes a join table, because `sport` is
    a real entity here and the coaches list filters by it — a JSONB array of names
    would need a scan and would break the moment a sport is renamed.
    """

    __tablename__ = "coach_sport"
    __table_args__ = (
        Index("uq_coach_sport_tenant_pair", "tenant_id", "coach_id", "sport_id", unique=True),
    )

    coach_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("coach.id", ondelete="CASCADE"), nullable=False
    )
    sport_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("sport.id", ondelete="CASCADE"), nullable=False
    )

    coach: Mapped[Coach] = relationship(back_populates="sports")


class Program(TenantScoped):
    """A coaching programme. ← `CoachingProgram`."""

    __tablename__ = "program"
    __table_args__ = (Index("uq_program_tenant_name", "tenant_id", "name", unique=True),)

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    sport_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("sport.id", ondelete="RESTRICT")
    )
    level: Mapped[str | None] = mapped_column(String(50))  # Beginner | Intermediate | Advanced
    age_group: Mapped[str | None] = mapped_column(String(50))  # "6–14 yrs"
    duration_label: Mapped[str | None] = mapped_column(String(50))  # "3 Months"
    max_students: Mapped[int] = mapped_column(Integer, default=12, nullable=False)
    session_freq: Mapped[str | None] = mapped_column(String(50))  # "3 sessions/week"
    session_duration: Mapped[str | None] = mapped_column(String(50))  # "60 min"
    coach_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("coach.id", ondelete="SET NULL")
    )
    location: Mapped[str | None] = mapped_column(String(150))

    fee_1m: Mapped[Decimal] = mapped_column(money(), default=0, nullable=False)
    fee_3m: Mapped[Decimal] = mapped_column(money(), default=0, nullable=False)
    fee_6m: Mapped[Decimal] = mapped_column(money(), default=0, nullable=False)
    fee_12m: Mapped[Decimal] = mapped_column(money(), default=0, nullable=False)

    color: Mapped[str | None] = mapped_column(String(9))
    bg_color: Mapped[str | None] = mapped_column(String(9))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def fee_for(self, duration: str) -> Decimal:
        return {"1m": self.fee_1m, "3m": self.fee_3m, "6m": self.fee_6m, "12m": self.fee_12m}[
            duration
        ]


class Batch(TenantScoped):
    """A scheduled group. ← `Batch`.

    `enrolled` and the `full` status are derived from `student_enrollment` — a
    stored count and a real enrolment row are two things that can disagree, and the
    capacity check would then admit a student into a full batch.
    """

    __tablename__ = "batch"
    __table_args__ = (
        Index("uq_batch_tenant_name", "tenant_id", "name", unique=True),
        Index("ix_batch_tenant_coach", "tenant_id", "coach_id"),
        Index("ix_batch_tenant_program", "tenant_id", "program_id"),
        CheckConstraint("capacity > 0", name="capacity_positive"),
    )

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    sport_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("sport.id", ondelete="RESTRICT")
    )
    program_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("program.id", ondelete="RESTRICT"), nullable=False
    )
    coach_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("coach.id", ondelete="SET NULL")
    )

    capacity: Mapped[int] = mapped_column(Integer, default=12, nullable=False)
    schedule: Mapped[str | None] = mapped_column(String(100))  # "Mon · Wed · Fri"
    time_label: Mapped[str | None] = mapped_column(String(50))  # "6:30 AM – 7:30 AM"
    location: Mapped[str | None] = mapped_column(String(150))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[BatchStatus] = mapped_column(
        enum_type(BatchStatus, name="batch_status"), default=BatchStatus.ACTIVE, nullable=False
    )
    color: Mapped[str | None] = mapped_column(String(9))


class Student(TenantScoped):
    """An academy student. ← `Student`.

    Two changes from the frontend interface:

    `age: number` becomes `date_of_birth`. An age column is wrong within a year of
    being written, and Coaching.tsx filters by age group.

    The enrolment fields (`programId`, `batchId`, `coachId`, `joiningDate`,
    `renewalDate`, `totalFee`, `pendingFee`) move to `student_enrollment`. Inline,
    they model a student as being in exactly one batch forever and destroy the
    history on renewal or transfer — and there is nowhere to hang the fee invoice.
    """

    __tablename__ = "student"
    __table_args__ = (
        Index("uq_student_tenant_number", "tenant_id", "student_no", unique=True),
        Index("ix_student_tenant_status", "tenant_id", "status"),
        Index("ix_student_tenant_name", "tenant_id", "name"),
    )

    student_no: Mapped[str] = mapped_column(String(32), nullable=False)  # XC-S-001
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    parent_name: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(320))
    avatar_initials: Mapped[str | None] = mapped_column(String(4))
    gender: Mapped[str | None] = mapped_column(String(20))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    blood_group: Mapped[str | None] = mapped_column(String(8))

    status: Mapped[StudentStatus] = mapped_column(
        enum_type(StudentStatus, name="student_status"),
        default=StudentStatus.ACTIVE,
        nullable=False,
    )
    performance_rating: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=0, nullable=False)

    achievements: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    # [{"name": "Forehand", "score": 7}] — genuinely document-shaped, rendered as a
    # radar chart and never queried across students.
    skills: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)

    # Links a student to the payer's customer record, so academy fees and court
    # bookings roll up to one person.
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("customer.id", ondelete="SET NULL")
    )

    def age_on(self, today: date) -> int | None:
        if self.date_of_birth is None:
            return None
        born = self.date_of_birth
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


class StudentEnrollment(TenantScoped):
    """A student's place in a batch for one paid term.

    Extracted from the frontend's flat `Student` so that renewals and batch
    transfers accumulate rather than overwrite: the current enrolment is the active
    row, and the endpoint flattens it back into the shape Coaching.tsx renders.
    """

    __tablename__ = "student_enrollment"
    __table_args__ = (
        Index("ix_student_enrollment_tenant_student", "tenant_id", "student_id"),
        Index("ix_student_enrollment_tenant_batch", "tenant_id", "batch_id"),
        Index("ix_student_enrollment_tenant_status", "tenant_id", "status"),
        # One live enrolment per student per batch. A student may re-enrol in the
        # same batch next term, so the constraint is partial on the active status.
        Index(
            "uq_student_enrollment_active",
            "tenant_id",
            "student_id",
            "batch_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("student.id", ondelete="CASCADE"), nullable=False
    )
    program_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("program.id", ondelete="RESTRICT"), nullable=False
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("batch.id", ondelete="RESTRICT"), nullable=False
    )
    coach_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("coach.id", ondelete="SET NULL")
    )

    duration: Mapped[str] = mapped_column(String(8), default="3m", nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    renewal_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_fee: Mapped[Decimal] = mapped_column(money(), default=0, nullable=False)
    status: Mapped[EnrollmentStatus] = mapped_column(
        enum_type(EnrollmentStatus, name="enrollment_status"),
        default=EnrollmentStatus.ACTIVE,
        nullable=False,
    )


class CoachingSession(TenantScoped):
    """One class. ← `Session`.

    Named CoachingSession rather than Session so it cannot be confused with a
    SQLAlchemy session anywhere in this codebase; the table is still `session`.

    `studentsEnrolled`, `present` and `absent` are derived from `attendance` rows.
    """

    __tablename__ = "coaching_session"
    __table_args__ = (
        Index("ix_coaching_session_tenant_batch", "tenant_id", "batch_id", "starts_at"),
        Index("ix_coaching_session_tenant_starts", "tenant_id", "starts_at"),
        Index("ix_coaching_session_tenant_coach", "tenant_id", "coach_id"),
        CheckConstraint("ends_at > starts_at", name="ends_after_starts"),
    )

    batch_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("batch.id", ondelete="CASCADE"), nullable=False
    )
    coach_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("coach.id", ondelete="SET NULL")
    )
    sport_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("sport.id", ondelete="SET NULL")
    )
    batch_name: Mapped[str] = mapped_column(String(150), nullable=False)  # snapshot

    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_min: Mapped[int] = mapped_column(Integer, default=60, nullable=False)

    status: Mapped[SessionStatus] = mapped_column(
        enum_type(SessionStatus, name="coaching_session_status"),
        default=SessionStatus.SCHEDULED,
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text)


class Attendance(TenantScoped):
    """One student's attendance at one session. ← the `attendanceToday` array."""

    __tablename__ = "attendance"
    __table_args__ = (
        # Marking the same student twice for one session would double-count them in
        # every attendance percentage on the dashboard.
        Index(
            "uq_attendance_tenant_session_student",
            "tenant_id",
            "session_id",
            "student_id",
            unique=True,
        ),
        Index("ix_attendance_tenant_student", "tenant_id", "student_id"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("coaching_session.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("student.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[AttendanceStatus] = mapped_column(
        enum_type(AttendanceStatus, name="attendance_status"),
        default=AttendanceStatus.NOT_STARTED,
        nullable=False,
    )
    marked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    marked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True))
    note: Mapped[str | None] = mapped_column(Text)
