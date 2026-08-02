"""Academy: coach numbering, batch capacity, enrolment history, attendance."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from httpx import AsyncClient

from tests.conftest import PASSWORD, TenantFixture, auth_headers, login
from tests.test_booking import setup_academy

IST = ZoneInfo("Asia/Kolkata")


def session_at(day: int, hour: int) -> str:
    return datetime(2026, 10, day, hour, 0, tzinfo=IST).isoformat()


async def build_academy(client: AsyncClient, tenant: TenantFixture) -> dict:
    """A coach, a programme and a batch with two places."""
    ctx = await setup_academy(client, tenant)
    h = ctx["headers"]

    coach = await client.post(
        "/api/v1/academy/coaches",
        json={
            "name": "Rahul Sharma",
            "phone": "9876500001",
            "email": "rahul@alpha.example.com",
            "specialization": "Baseline Game & Serve Technique",
            "type": "full-time",
            "experience_years": 8,
            "certifications": ["AITA Level 3"],
            "languages": ["Hindi", "English"],
            "salary": "55000",
            "hourly_rate": "1500",
            "sport_ids": [ctx["sport_id"]],
        },
        headers=h,
    )
    assert coach.status_code == 201, coach.text

    program = await client.post(
        "/api/v1/academy/programs",
        json={
            "name": "Tennis Beginners",
            "sport_id": ctx["sport_id"],
            "level": "Beginner",
            "age_group": "6–14 yrs",
            "max_students": 12,
            "coach_id": coach.json()["id"],
            "fee_1m": "3500",
            "fee_3m": "9500",
            "fee_6m": "17000",
            "fee_12m": "30000",
        },
        headers=h,
    )
    assert program.status_code == 201, program.text

    batch = await client.post(
        "/api/v1/academy/batches",
        json={
            "name": "Tennis A – Morning",
            "program_id": program.json()["id"],
            "sport_id": ctx["sport_id"],
            "coach_id": coach.json()["id"],
            "capacity": 2,
            "schedule": "Mon · Wed · Fri",
            "time_label": "6:30 AM – 7:30 AM",
        },
        headers=h,
    )
    assert batch.status_code == 201, batch.text

    return {
        **ctx,
        "coach_id": coach.json()["id"],
        "program_id": program.json()["id"],
        "batch_id": batch.json()["id"],
    }


async def make_student(client: AsyncClient, ctx: dict, name: str, dob: str | None = None) -> str:
    response = await client.post(
        "/api/v1/academy/students",
        json={
            "name": name,
            "parent_name": f"Parent of {name}",
            "phone": "9811000001",
            "date_of_birth": dob or "2014-05-01",
            "skills": [{"name": "Forehand", "score": 7}, {"name": "Serve", "score": 5}],
        },
        headers=ctx["headers"],
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


# ── Numbering ───────────────────────────────────────────────────────────────


async def test_coach_and_student_numbers_are_per_tenant_series(
    client: AsyncClient, tenant_a: TenantFixture, tenant_b: TenantFixture
) -> None:
    """XC-C-001 and XC-S-001 restart for every academy, like invoices do."""
    ctx_a = await build_academy(client, tenant_a)
    ctx_b = await build_academy(client, tenant_b)

    coaches_a = await client.get("/api/v1/academy/coaches", headers=ctx_a["headers"])
    coaches_b = await client.get("/api/v1/academy/coaches", headers=ctx_b["headers"])
    assert coaches_a.json()["items"][0]["coach_no"] == "XC-C-001"
    assert coaches_b.json()["items"][0]["coach_no"] == "XC-C-001"

    await make_student(client, ctx_a, "Aryan Mehta")
    await make_student(client, ctx_a, "Nisha Kapoor")
    students = await client.get("/api/v1/academy/students", headers=ctx_a["headers"])
    assert sorted(s["student_no"] for s in students.json()["items"]) == ["XC-S-001", "XC-S-002"]

    # And tenant B's first student is still 001.
    await make_student(client, ctx_b, "Beta Student")
    students_b = await client.get("/api/v1/academy/students", headers=ctx_b["headers"])
    assert students_b.json()["items"][0]["student_no"] == "XC-S-001"


# ── Capacity ────────────────────────────────────────────────────────────────


async def test_batch_occupancy_is_counted_not_stored(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    ctx = await build_academy(client, tenant_a)

    batches = await client.get("/api/v1/academy/batches", headers=ctx["headers"])
    assert batches.json()[0]["enrolled"] == 0
    assert batches.json()[0]["is_full"] is False

    student_id = await make_student(client, ctx, "Aryan Mehta")
    await client.post(
        "/api/v1/academy/enrollments",
        json={"student_id": student_id, "batch_id": ctx["batch_id"], "duration": "3m"},
        headers=ctx["headers"],
    )

    batches = await client.get("/api/v1/academy/batches", headers=ctx["headers"])
    assert batches.json()[0]["enrolled"] == 1


async def test_a_full_batch_refuses_further_enrolment(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    """Capacity is checked against live enrolments, not a column that can drift."""
    ctx = await build_academy(client, tenant_a)  # capacity 2

    for name in ("Aryan Mehta", "Nisha Kapoor"):
        student_id = await make_student(client, ctx, name)
        response = await client.post(
            "/api/v1/academy/enrollments",
            json={"student_id": student_id, "batch_id": ctx["batch_id"], "duration": "3m"},
            headers=ctx["headers"],
        )
        assert response.status_code == 201, response.text

    third = await make_student(client, ctx, "Rohit Jain")
    refused = await client.post(
        "/api/v1/academy/enrollments",
        json={"student_id": third, "batch_id": ctx["batch_id"], "duration": "3m"},
        headers=ctx["headers"],
    )
    assert refused.status_code == 409
    assert refused.json()["error"]["details"]["capacity"] == 2

    batches = await client.get("/api/v1/academy/batches", headers=ctx["headers"])
    assert batches.json()[0]["is_full"] is True


# ── Enrolment and fees ──────────────────────────────────────────────────────


async def test_enrolment_raises_a_fee_invoice(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    """The academy fee becomes a real invoice, in the same numbering series."""
    ctx = await build_academy(client, tenant_a)
    student_id = await make_student(client, ctx, "Aryan Mehta")

    response = await client.post(
        "/api/v1/academy/enrollments",
        json={"student_id": student_id, "batch_id": ctx["batch_id"], "duration": "3m"},
        headers=ctx["headers"],
    )
    assert response.status_code == 201, response.text
    body = response.json()

    assert body["enrollment"]["total_fee"] == "9500.00"
    assert body["invoice_no"].startswith("XC-")
    # 9500 + 18% GST
    assert Decimal(body["invoice_total"]) == Decimal("11210.00")

    invoice = await client.get(
        f"/api/v1/invoices/{body['invoice_id']}", headers=ctx["headers"]
    )
    assert invoice.json()["student_enrollment_id"] == body["enrollment"]["id"]
    assert invoice.json()["booking_id"] is None


async def test_pending_fee_falls_as_payments_arrive(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    """`Student.pendingFee` is derived. Stored, it would go stale on every payment."""
    ctx = await build_academy(client, tenant_a)
    student_id = await make_student(client, ctx, "Kavya Reddy")

    enrolled = await client.post(
        "/api/v1/academy/enrollments",
        json={"student_id": student_id, "batch_id": ctx["batch_id"], "duration": "3m"},
        headers=ctx["headers"],
    )
    invoice_id = enrolled.json()["invoice_id"]

    detail = await client.get(f"/api/v1/academy/students/{student_id}", headers=ctx["headers"])
    assert Decimal(detail.json()["pending_fee"]) == Decimal("9500.00")

    await client.post(
        "/api/v1/payments",
        json={"invoice_id": invoice_id, "amount": "5000", "method": "upi"},
        headers=ctx["headers"],
    )

    detail = await client.get(f"/api/v1/academy/students/{student_id}", headers=ctx["headers"])
    assert Decimal(detail.json()["pending_fee"]) == Decimal("4500.00")


async def test_enrolment_history_survives_a_second_term(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    """The history the frontend's flat Student interface would have overwritten.

    A student re-enrolling in the same batch next term keeps both rows, which is
    what makes fee history and batch transfers auditable.
    """
    ctx = await build_academy(client, tenant_a)
    student_id = await make_student(client, ctx, "Dev Sharma")

    first = await client.post(
        "/api/v1/academy/enrollments",
        json={
            "student_id": student_id,
            "batch_id": ctx["batch_id"],
            "duration": "3m",
            "start_date": "2026-01-01",
        },
        headers=ctx["headers"],
    )
    assert first.status_code == 201

    # Close the first term, then enrol again — the partial unique index allows it.
    from sqlalchemy import select

    from app.db.session import tenant_session
    from app.modules.academy.models import EnrollmentStatus, StudentEnrollment

    async with tenant_session(tenant_a.id) as session:
        row = (await session.execute(select(StudentEnrollment))).scalar_one()
        row.status = EnrollmentStatus.COMPLETED

    second = await client.post(
        "/api/v1/academy/enrollments",
        json={
            "student_id": student_id,
            "batch_id": ctx["batch_id"],
            "duration": "6m",
            "start_date": "2026-04-01",
        },
        headers=ctx["headers"],
    )
    assert second.status_code == 201, second.text

    history = await client.get(
        f"/api/v1/academy/students/{student_id}/enrollments", headers=ctx["headers"]
    )
    assert len(history.json()) == 2
    assert {row["duration"] for row in history.json()} == {"3m", "6m"}

    # The student detail flattens to the *current* term.
    detail = await client.get(f"/api/v1/academy/students/{student_id}", headers=ctx["headers"])
    assert detail.json()["renewal_date"] == "2026-10-01"
    assert Decimal(detail.json()["total_fee"]) == Decimal("17000.00")


async def test_renewal_date_uses_calendar_months(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    ctx = await build_academy(client, tenant_a)
    student_id = await make_student(client, ctx, "Tanvi Singh")

    response = await client.post(
        "/api/v1/academy/enrollments",
        json={
            "student_id": student_id,
            "batch_id": ctx["batch_id"],
            "duration": "1m",
            "start_date": "2027-01-31",
        },
        headers=ctx["headers"],
    )
    assert response.json()["enrollment"]["renewal_date"] == "2027-02-28"


# ── Students ────────────────────────────────────────────────────────────────


async def test_age_is_derived_from_date_of_birth(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    """An age column is wrong within a year of being written."""
    ctx = await build_academy(client, tenant_a)
    born = date.today().replace(year=date.today().year - 12)
    student_id = await make_student(client, ctx, "Aryan Mehta", dob=born.isoformat())

    detail = await client.get(f"/api/v1/academy/students/{student_id}", headers=ctx["headers"])
    assert detail.json()["age"] == 12
    assert detail.json()["date_of_birth"] == born.isoformat()


async def test_skills_round_trip_as_jsonb(client: AsyncClient, tenant_a: TenantFixture) -> None:
    ctx = await build_academy(client, tenant_a)
    student_id = await make_student(client, ctx, "Nisha Kapoor")

    detail = await client.get(f"/api/v1/academy/students/{student_id}", headers=ctx["headers"])
    assert detail.json()["skills"] == [
        {"name": "Forehand", "score": 7},
        {"name": "Serve", "score": 5},
    ]

    updated = await client.patch(
        f"/api/v1/academy/students/{student_id}",
        json={"skills": [{"name": "Forehand", "score": 9}], "achievements": ["Best Newcomer"]},
        headers=ctx["headers"],
    )
    assert updated.json()["skills"] == [{"name": "Forehand", "score": 9}]
    assert updated.json()["achievements"] == ["Best Newcomer"]


# ── Sessions and attendance ─────────────────────────────────────────────────


async def test_marking_attendance_is_idempotent_per_student(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    """Re-marking updates the existing row.

    A second row for the same student would double-count them in every attendance
    percentage on the dashboard.
    """
    ctx = await build_academy(client, tenant_a)
    student_id = await make_student(client, ctx, "Aryan Mehta")
    await client.post(
        "/api/v1/academy/enrollments",
        json={"student_id": student_id, "batch_id": ctx["batch_id"], "duration": "3m"},
        headers=ctx["headers"],
    )

    created = await client.post(
        "/api/v1/academy/sessions",
        json={"batch_id": ctx["batch_id"], "starts_at": session_at(1, 6), "duration_min": 60},
        headers=ctx["headers"],
    )
    assert created.status_code == 201, created.text
    session_id = created.json()["id"]

    await client.post(
        f"/api/v1/academy/sessions/{session_id}/attendance",
        json={"marks": [{"student_id": student_id, "status": "absent"}]},
        headers=ctx["headers"],
    )
    corrected = await client.post(
        f"/api/v1/academy/sessions/{session_id}/attendance",
        json={"marks": [{"student_id": student_id, "status": "present"}]},
        headers=ctx["headers"],
    )
    assert corrected.status_code == 200

    register = await client.get(
        f"/api/v1/academy/sessions/{session_id}/attendance", headers=ctx["headers"]
    )
    assert len(register.json()) == 1
    assert register.json()[0]["status"] == "present"


async def test_session_counters_are_derived_from_the_register(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    ctx = await build_academy(client, tenant_a)
    first = await make_student(client, ctx, "Aryan Mehta")
    second = await make_student(client, ctx, "Nisha Kapoor")
    for student_id in (first, second):
        await client.post(
            "/api/v1/academy/enrollments",
            json={"student_id": student_id, "batch_id": ctx["batch_id"], "duration": "3m"},
            headers=ctx["headers"],
        )

    created = await client.post(
        "/api/v1/academy/sessions",
        json={"batch_id": ctx["batch_id"], "starts_at": session_at(2, 6)},
        headers=ctx["headers"],
    )
    session_id = created.json()["id"]
    assert created.json()["students_enrolled"] == 2
    assert created.json()["present"] == 0

    await client.post(
        f"/api/v1/academy/sessions/{session_id}/attendance",
        json={
            "marks": [
                {"student_id": first, "status": "present"},
                {"student_id": second, "status": "absent"},
            ]
        },
        headers=ctx["headers"],
    )

    sessions = await client.get("/api/v1/academy/sessions", headers=ctx["headers"])
    row = sessions.json()[0]
    assert row["present"] == 1
    assert row["absent"] == 1
    assert row["students_enrolled"] == 2
    # Taking the register completes the session.
    assert row["status"] == "completed"


async def test_attendance_percentage_ignores_unmarked_sessions(
    client: AsyncClient, tenant_a: TenantFixture
) -> None:
    """A batch whose register has not been taken must not drag percentages down."""
    ctx = await build_academy(client, tenant_a)
    student_id = await make_student(client, ctx, "Aryan Mehta")
    await client.post(
        "/api/v1/academy/enrollments",
        json={"student_id": student_id, "batch_id": ctx["batch_id"], "duration": "3m"},
        headers=ctx["headers"],
    )

    for day, mark in ((3, "present"), (4, "present"), (5, "absent")):
        created = await client.post(
            "/api/v1/academy/sessions",
            json={"batch_id": ctx["batch_id"], "starts_at": session_at(day, 6)},
            headers=ctx["headers"],
        )
        await client.post(
            f"/api/v1/academy/sessions/{created.json()['id']}/attendance",
            json={"marks": [{"student_id": student_id, "status": mark}]},
            headers=ctx["headers"],
        )

    # A fourth session with no register taken at all.
    await client.post(
        "/api/v1/academy/sessions",
        json={"batch_id": ctx["batch_id"], "starts_at": session_at(6, 6)},
        headers=ctx["headers"],
    )

    detail = await client.get(f"/api/v1/academy/students/{student_id}", headers=ctx["headers"])
    assert detail.json()["attendance_pct"] == 66.7  # 2 of 3 marked, not 2 of 4


async def test_coach_workload_is_derived(client: AsyncClient, tenant_a: TenantFixture) -> None:
    """`activeBatches` and `totalStudents` are counts, not stored columns."""
    ctx = await build_academy(client, tenant_a)
    student_id = await make_student(client, ctx, "Aryan Mehta")
    await client.post(
        "/api/v1/academy/enrollments",
        json={"student_id": student_id, "batch_id": ctx["batch_id"], "duration": "3m"},
        headers=ctx["headers"],
    )

    coaches = await client.get("/api/v1/academy/coaches", headers=ctx["headers"])
    coach = coaches.json()["items"][0]
    assert coach["active_batches"] == 1
    assert coach["total_students"] == 1
    assert coach["sport_ids"] == [ctx["sport_id"]]


async def test_academy_overview(client: AsyncClient, tenant_a: TenantFixture) -> None:
    ctx = await build_academy(client, tenant_a)
    student_id = await make_student(client, ctx, "Aryan Mehta")
    enrolled = await client.post(
        "/api/v1/academy/enrollments",
        json={"student_id": student_id, "batch_id": ctx["batch_id"], "duration": "3m"},
        headers=ctx["headers"],
    )
    await client.post(
        "/api/v1/payments",
        json={"invoice_id": enrolled.json()["invoice_id"], "amount": "2000", "method": "cash"},
        headers=ctx["headers"],
    )

    overview = await client.get("/api/v1/academy/overview", headers=ctx["headers"])
    body = overview.json()
    assert body["total_coaches"] == 1
    assert body["active_coaches"] == 1
    assert body["active_students"] == 1
    assert body["sports_offered"] == 1
    assert body["new_admissions_this_month"] == 1
    assert Decimal(body["fee_collected"]) == Decimal("2000.00")
    assert Decimal(body["fee_pending"]) > Decimal("0")


async def test_academy_data_does_not_cross_tenants(
    client: AsyncClient, tenant_a: TenantFixture, tenant_b: TenantFixture
) -> None:
    ctx_a = await build_academy(client, tenant_a)
    ctx_b = await build_academy(client, tenant_b)

    student_id = await make_student(client, ctx_a, "Alpha Student")

    assert (
        await client.get(f"/api/v1/academy/students/{student_id}", headers=ctx_b["headers"])
    ).status_code == 404
    assert (await client.get("/api/v1/academy/students", headers=ctx_b["headers"])).json()["total"] == 0

    # B cannot enrol A's student into B's batch either.
    attempt = await client.post(
        "/api/v1/academy/enrollments",
        json={"student_id": student_id, "batch_id": ctx_b["batch_id"], "duration": "3m"},
        headers=ctx_b["headers"],
    )
    assert attempt.status_code == 404
