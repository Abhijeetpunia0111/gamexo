"""Representative data for tenant #1, lifted from the frontend's own mock arrays.

Values come from `apps/web/src/data/mockData.ts` and the inline arrays in
`src/pages/*.tsx`, so the seeded academy renders as the frontend was designed
against rather than as generic placeholder text.

Idempotent: each block skips anything already present, so re-running adds only
what is missing.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.academy.models import Batch, Coach, CoachSport, Program, Student
from app.modules.advertising.models import AdContract, AdSpot, ContractStatus, SpotType
from app.modules.booking.models import (
    Court,
    Customer,
    Equipment,
    EquipmentCondition,
    Gender,
    MemberType,
    MembershipTier,
    Sport,
)
from app.modules.booking.service import initials
from app.modules.finance.models import CounterKind, MembershipPlan
from app.modules.finance.numbering import next_number

IST = ZoneInfo("Asia/Kolkata")

SPORTS = [
    # name, slug, icon, color, bg, duration, base, peak, weekend
    ("Tennis", "tennis", "🎾", "#C8A900", "#FFFBDC", 60, 800, 1200, 1000),
    ("Pickleball", "pickleball", "🏓", "#00884B", "#DCFFF0", 60, 600, 900, 750),
    ("Badminton", "badminton", "🏸", "#7B2FBE", "#F5EDFF", 60, 500, 800, 650),
    ("Swimming", "swimming", "🏊", "#0077CC", "#E0F4FF", 60, 700, 1000, 850),
    ("Football", "football", "⚽", "#333333", "#F0F0F0", 90, 2500, 3500, 3000),
    ("Cricket Nets", "cricket", "🏏", "#8B2500", "#FFF0E8", 60, 600, 900, 750),
]

COURTS = [
    # code, name, sport slug, hourly, peak, open, close, amenities
    ("court-1", "Court 1", "tennis", 800, 1200, "06:00", "22:00", ["Floodlights", "Seating", "Water Station"]),
    ("court-2", "Court 2", "tennis", 800, 1200, "06:00", "22:00", ["Floodlights", "Seating"]),
    ("court-3", "Court 3", "pickleball", 600, 900, "06:00", "22:00", ["Floodlights"]),
    ("court-4", "Court 4", "badminton", 500, 800, "06:00", "22:00", ["AC", "Seating"]),
    ("pool-1", "Swimming Pool", "swimming", 700, 1000, "05:30", "21:00", ["Changing Rooms", "Lockers", "Showers"]),
    ("ground-1", "Football Ground", "football", 2500, 3500, "06:00", "22:00", ["Floodlights", "Seating", "Changing Rooms"]),
    ("net-1", "Cricket Net 1", "cricket", 600, 900, "06:00", "21:00", ["Bowler Mat", "Safety Net"]),
    ("net-2", "Cricket Net 2", "cricket", 600, 900, "06:00", "21:00", ["Bowler Mat", "Safety Net"]),
]

EQUIPMENT = [
    # name, category, barcode, rental, deposit, condition, stock
    ("Tennis Racket", "Tennis", "TEN-RAC-001", 100, 500, "good", 12),
    ("Pickleball Paddle", "Pickleball", "PIK-PAD-001", 80, 400, "excellent", 8),
    ("Tennis Balls (3 pack)", "Tennis", "TEN-BAL-001", 50, 0, "good", 30),
    ("Badminton Racket", "Badminton", "BAD-RAC-001", 70, 350, "good", 16),
    ("Shuttlecocks (6 pack)", "Badminton", "BAD-SHU-001", 40, 0, "excellent", 40),
    ("Swimming Kit", "Swimming", "SWI-KIT-001", 150, 700, "good", 20),
    ("Locker Key", "General", "GEN-LOK-001", 30, 200, "excellent", 50),
    ("Cricket Bat", "Cricket", "CRI-BAT-001", 120, 600, "good", 6),
    ("Cricket Ball", "Cricket", "CRI-BAL-001", 30, 0, "good", 20),
]

CUSTOMERS = [
    # name, email, phone, gender, member type, tier, favourite sport
    ("Arjun Mehta", "arjun.mehta@example.com", "9876543210", "male", "member", "gold", "tennis"),
    ("Priya Sharma", "priya.sharma@example.com", "9823456789", "female", "member", "silver", "badminton"),
    ("Rohan Kapoor", "rohan.k@example.com", "9911223344", "male", "non-member", None, "football"),
    ("Sneha Iyer", "sneha.iyer@example.com", "9845671234", "female", "member", "bronze", "swimming"),
    ("Kiran Patel", "kiran.patel@example.com", "9765432109", "male", "member", "gold", "tennis"),
    ("Ananya Reddy", "ananya.r@example.com", "9955667788", "female", "non-member", None, "pickleball"),
    ("Vikram Singh", "vikram.s@example.com", "9800112233", "male", "member", "silver", "cricket"),
    ("Meera Nair", "meera.nair@example.com", "9888776655", "female", "member", "gold", "badminton"),
]

PLANS = [
    # name, category, description, color, bg, 1m, 3m, 6m, 12m, joining, discount, max visits, benefits
    ("Tennis Elite", "Tennis", "Unlimited tennis court access with priority booking", "#C8A900", "#FFFBDC",
     3500, 9500, 17000, 30000, 1000, 15, None,
     ["Unlimited Court Hours", "15% Discount on Rentals", "Priority Booking", "Free Coaching (2/month)", "Locker Access"]),
    ("Swim Pro", "Swimming", "Full pool access including lanes and group sessions", "#0077CC", "#E0F4FF",
     2500, 7000, 12500, 22000, 500, 10, None,
     ["Unlimited Pool Access", "10% Discount on Equipment", "Lane Priority", "Group Classes (4/month)"]),
    ("Badminton Club", "Badminton", "Regular badminton access with shuttlecock perks", "#7B2FBE", "#F5EDFF",
     2000, 5500, 10000, 18000, 500, 12, 24,
     ["24 Sessions/Month", "Free Shuttlecocks", "12% Discount", "Racket Storage"]),
    ("Family Sports", "Multi-Sport", "Sports access for up to 4 family members", "#FF6600", "#FFF0E0",
     8000, 22000, 40000, 70000, 2000, 20, None,
     ["4 Members Included", "All Sports Access", "20% Discount", "Guest Passes (2/month)", "Priority Booking"]),
    ("Corporate Gold", "Corporate", "Bulk access for office teams", "#002E25", "#E8F4EC",
     25000, 70000, 130000, 240000, 5000, 25, None,
     ["Up to 20 Employees", "All Sports Access", "25% Discount", "Dedicated Coordinator", "Monthly Reports"]),
]

COACHES = [
    # name, phone, email, gender, sport slug, specialization, type, years, certs, languages, salary, hourly, morning, evening, rating
    ("Rahul Sharma", "9876500001", "rahul@xcourtsports.com", "Male", "tennis",
     "Baseline Game & Serve Technique", "full-time", 8, ["AITA Level 3", "ITF Coaches Certificate"],
     ["Hindi", "English"], 55000, 1500, True, True, "4.8"),
    ("Priya Nair", "9876500002", "priya.n@xcourtsports.com", "Female", "swimming",
     "Competitive Swimming & Technique", "full-time", 6, ["SWIM India Level 2", "Lifeguard Certified"],
     ["Malayalam", "English", "Hindi"], 48000, 1200, True, False, "4.9"),
    ("Amit Verma", "9876500003", "amit@xcourtsports.com", "Male", "badminton",
     "Singles & Doubles Strategy", "full-time", 10, ["BAI Level 3", "SAI Certified Coach"],
     ["Hindi", "English"], 60000, 1800, False, True, "4.7"),
    ("Sneha Kapoor", "9876500004", "sneha.k@xcourtsports.com", "Female", "pickleball",
     "Pickleball & Junior Development", "part-time", 4, ["PPA Certified Coach"],
     ["English", "Hindi"], 30000, 1000, True, True, "4.6"),
    ("Carlos Mendes", "9876500005", "carlos@xcourtsports.com", "Male", "tennis",
     "Pro-level Conditioning & Advanced Tactics", "guest", 15, ["PTR Professional", "ITF High Performance"],
     ["English", "Portuguese", "Spanish"], 0, 5000, False, True, "5.0"),
]

PROGRAMS = [
    # name, sport slug, level, age group, duration, max, freq, session len, coach index, location, fees, color, bg
    ("Tennis Beginners", "tennis", "Beginner", "6–14 yrs", "3 Months", 12, "3 sessions/week", "60 min", 0,
     "Court 1 & 2", (3500, 9500, 17000, 30000), "#C8A900", "#FFFBDC"),
    ("Tennis Advanced", "tennis", "Advanced", "14+ yrs", "12 Months", 6, "5 sessions/week", "120 min", 4,
     "Court 1", (8000, 22000, 42000, 78000), "#FF6600", "#FFF0E0"),
    ("Swim Beginners", "swimming", "Beginner", "5–12 yrs", "3 Months", 15, "5 sessions/week", "45 min", 1,
     "Pool Lane 1–3", (2800, 7800, 14000, 25000), "#0077CC", "#E0F4FF"),
    ("Badminton Club", "badminton", "Intermediate", "All ages", "6 Months", 16, "3 sessions/week", "90 min", 2,
     "Badminton Courts", (2500, 7000, 12500, 22000), "#7B2FBE", "#F5EDFF"),
]

BATCHES = [
    # name, program index, capacity, schedule, time label, location, color
    ("Tennis A – Morning", 0, 12, "Mon · Wed · Fri", "6:30 AM – 7:30 AM", "Court 1", "#C8A900"),
    ("Tennis B – Evening", 0, 12, "Tue · Thu · Sat", "5:00 PM – 6:00 PM", "Court 2", "#C8A900"),
    ("Elite Tennis – Pro", 1, 6, "Mon–Fri", "4:30 PM – 6:30 PM", "Court 1", "#FF6600"),
    ("Swim Kids – Morning", 2, 15, "Mon–Fri", "6:00 AM – 6:45 AM", "Pool Lane 1–3", "#0077CC"),
    ("Badminton Club – Eve", 3, 16, "Mon · Wed · Fri", "6:00 PM – 7:30 PM", "Badminton Courts", "#7B2FBE"),
]

STUDENTS = [
    # name, parent, phone, gender, dob, blood group, achievements, skills
    ("Aryan Mehta", "Suresh Mehta", "9811000001", "Male", date(2014, 5, 12), "O+",
     ["Best Newcomer – Apr 2024"],
     [("Forehand", 7), ("Backhand", 6), ("Serve", 5), ("Footwork", 8), ("Fitness", 7), ("Strategy", 6)]),
    ("Nisha Kapoor", "Ravi Kapoor", "9811000002", "Female", date(2016, 2, 3), "A+",
     ["Best Swimmer – Jun 2024", "Freestyle Record Holder"],
     [("Freestyle", 9), ("Backstroke", 8), ("Breaststroke", 7), ("Stamina", 9), ("Flip Turn", 8), ("Starts", 7)]),
    ("Rohit Jain", "Prem Jain", "9811000003", "Male", date(2010, 8, 21), "B+", [],
     [("Smash", 8), ("Drop Shot", 7), ("Footwork", 7), ("Net Play", 6), ("Serve", 8), ("Stamina", 7)]),
    ("Kavya Reddy", "Anand Reddy", "9811000004", "Female", date(2012, 11, 9), "AB+",
     ["Junior District Champion 2024"],
     [("Forehand", 8), ("Backhand", 7), ("Serve", 8), ("Footwork", 9), ("Fitness", 8), ("Strategy", 7)]),
    ("Dev Sharma", "Rajesh Sharma", "9811000005", "Male", date(2007, 3, 30), "O-",
     ["State U-19 Champion", "National Qualifier 2024"],
     [("Forehand", 9), ("Backhand", 9), ("Serve", 10), ("Footwork", 9), ("Fitness", 10), ("Strategy", 9)]),
]

AD_SPOTS = [
    # code, name, zone, location, dimensions, type, display, visibility, monthly, quarterly, yearly
    ("Z1-B01", "Main Entrance Banner", "Zone A – Entrance", "Main Gate, left side pillar", "8ft × 4ft",
     "outdoor", "Vinyl Banner", "9.5", 15000, 42000, 150000),
    ("Z1-B02", "Reception Wall Display", "Zone A – Entrance", "Reception area, behind counter", "6ft × 3ft",
     "indoor", "LED Display", "9.2", 12000, 34000, 120000),
    ("Z2-T01", "Tennis Court Hoarding", "Zone B – Courts", "Court 1 & 2 boundary wall", "20ft × 6ft",
     "outdoor", "Hoarding", "8.8", 25000, 70000, 250000),
    ("Z3-P01", "Swimming Pool Deck Banner", "Zone C – Aquatic", "Pool deck, north wall", "12ft × 4ft",
     "indoor", "Flex Banner", "8.1", 18000, 50000, 180000),
    ("Z4-C01", "Cafeteria Digital Screen", "Zone D – Common Areas", "Cafeteria ceiling mount", '75" Display',
     "indoor", "Digital Screen", "9.0", 20000, 56000, 200000),
    ("Z5-O01", "Parking Area Standee", "Zone E – Parking", "Main parking entrance", "2ft × 5ft",
     "outdoor", "Standee Frame", "7.0", 5000, 14000, 50000),
]


async def _existing(session: AsyncSession, model, column) -> set[str]:
    return set((await session.execute(select(column))).scalars().all())


async def seed_domain_data(session: AsyncSession, prefix: str) -> dict[str, int]:
    """Fill tenant #1 with representative data. Returns what was created."""
    created: dict[str, int] = {}

    # ── Sports and courts ───────────────────────────────────────────────────
    known = await _existing(session, Sport, Sport.slug)
    for name, slug, icon, color, bg, duration, base, peak, weekend in SPORTS:
        if slug in known:
            continue
        session.add(
            Sport(
                name=name, slug=slug, icon=icon, color=color, bg_color=bg,
                default_duration_min=duration,
                price_base=Decimal(base), price_peak=Decimal(peak), price_weekend=Decimal(weekend),
                display_order=len(known),
            )
        )
        known.add(slug)
    await session.flush()
    created["sports"] = len(known)

    sport_ids = {
        slug: sid
        for slug, sid in (await session.execute(select(Sport.slug, Sport.id))).all()
    }

    known_courts = await _existing(session, Court, Court.code)
    for code, name, slug, hourly, peak, opens, closes, amenities in COURTS:
        if code in known_courts or slug not in sport_ids:
            continue
        session.add(
            Court(
                code=code, name=name, sport_id=sport_ids[slug],
                hourly_rate=Decimal(hourly), peak_rate=Decimal(peak),
                operating_hours={"open": opens, "close": closes},
                amenities=amenities,
            )
        )
    await session.flush()
    created["courts"] = len(COURTS)

    # ── Equipment ───────────────────────────────────────────────────────────
    known_barcodes = await _existing(session, Equipment, Equipment.barcode)
    for name, category, barcode, rental, deposit, condition, stock in EQUIPMENT:
        if barcode in known_barcodes:
            continue
        session.add(
            Equipment(
                name=name, category=category, barcode=barcode,
                rental_price=Decimal(rental), deposit=Decimal(deposit),
                condition=EquipmentCondition(condition),
                qty_stock=stock, qty_available=stock,
            )
        )
    await session.flush()
    created["equipment"] = len(EQUIPMENT)

    # ── Customers ───────────────────────────────────────────────────────────
    known_phones = await _existing(session, Customer, Customer.phone)
    for name, email, phone, gender, member_type, tier, favourite in CUSTOMERS:
        if phone in known_phones:
            continue
        session.add(
            Customer(
                name=name, email=email, phone=phone,
                gender=Gender(gender),
                member_type=MemberType(member_type),
                membership_tier=MembershipTier(tier) if tier else None,
                favorite_sport_id=sport_ids.get(favourite),
                avatar_initials=initials(name),
                join_date=date.today() - timedelta(days=400),
            )
        )
    await session.flush()
    created["customers"] = len(CUSTOMERS)

    # ── Membership plans ────────────────────────────────────────────────────
    known_plans = await _existing(session, MembershipPlan, MembershipPlan.name)
    for (name, category, description, color, bg, p1, p3, p6, p12,
         joining, discount, max_visits, benefits) in PLANS:
        if name in known_plans:
            continue
        session.add(
            MembershipPlan(
                name=name, category=category, description=description,
                color=color, bg_color=bg,
                price_1m=Decimal(p1), price_3m=Decimal(p3),
                price_6m=Decimal(p6), price_12m=Decimal(p12),
                joining_fee=Decimal(joining), discount_pct=discount,
                max_visits=max_visits, benefits=benefits,
            )
        )
    await session.flush()
    created["membership_plans"] = len(PLANS)

    # ── Coaches ─────────────────────────────────────────────────────────────
    known_coaches = await _existing(session, Coach, Coach.name)
    coach_ids: list[uuid.UUID] = []
    for (name, phone, email, gender, slug, specialization, coach_type, years,
         certs, languages, salary, hourly, morning, evening, rating) in COACHES:
        if name in known_coaches:
            continue
        coach = Coach(
            coach_no=await next_number(session, CounterKind.COACH, prefix=prefix),
            name=name, phone=phone, email=email, gender=gender,
            specialization=specialization, type=coach_type,
            experience_years=years, certifications=certs, languages=languages,
            joining_date=date.today() - timedelta(days=800),
            salary=Decimal(salary), hourly_rate=Decimal(hourly),
            morning_available=morning, evening_available=evening,
            rating=Decimal(rating), avatar_initials=initials(name),
        )
        session.add(coach)
        await session.flush()
        if slug in sport_ids:
            session.add(CoachSport(coach_id=coach.id, sport_id=sport_ids[slug]))
        coach_ids.append(coach.id)
    await session.flush()
    created["coaches"] = len(coach_ids)

    if not coach_ids:  # already seeded — reuse what is there
        coach_ids = list((await session.execute(select(Coach.id).order_by(Coach.coach_no))).scalars())

    # ── Programmes and batches ──────────────────────────────────────────────
    known_programs = await _existing(session, Program, Program.name)
    program_ids: list[uuid.UUID] = []
    for (name, slug, level, age_group, duration, max_students, freq, session_len,
         coach_index, location, fees, color, bg) in PROGRAMS:
        if name in known_programs:
            continue
        program = Program(
            name=name, sport_id=sport_ids.get(slug), level=level, age_group=age_group,
            duration_label=duration, max_students=max_students,
            session_freq=freq, session_duration=session_len,
            coach_id=coach_ids[coach_index] if coach_index < len(coach_ids) else None,
            location=location,
            fee_1m=Decimal(fees[0]), fee_3m=Decimal(fees[1]),
            fee_6m=Decimal(fees[2]), fee_12m=Decimal(fees[3]),
            color=color, bg_color=bg,
        )
        session.add(program)
        await session.flush()
        program_ids.append(program.id)
    created["programs"] = len(program_ids)

    if not program_ids:
        program_ids = list((await session.execute(select(Program.id).order_by(Program.name))).scalars())

    known_batches = await _existing(session, Batch, Batch.name)
    for name, program_index, capacity, schedule, time_label, location, color in BATCHES:
        if name in known_batches or program_index >= len(program_ids):
            continue
        program = await session.get(Program, program_ids[program_index])
        session.add(
            Batch(
                name=name, program_id=program.id, sport_id=program.sport_id,
                coach_id=program.coach_id, capacity=capacity,
                schedule=schedule, time_label=time_label, location=location,
                start_date=date.today() - timedelta(days=60),
                end_date=date.today() + timedelta(days=120),
                color=color,
            )
        )
    await session.flush()
    created["batches"] = len(BATCHES)

    # ── Students ────────────────────────────────────────────────────────────
    known_students = await _existing(session, Student, Student.name)
    for name, parent, phone, gender, dob, blood, achievements, skills in STUDENTS:
        if name in known_students:
            continue
        session.add(
            Student(
                student_no=await next_number(session, CounterKind.STUDENT, prefix=prefix),
                name=name, parent_name=parent, phone=phone, gender=gender,
                date_of_birth=dob, blood_group=blood,
                achievements=achievements,
                skills=[{"name": skill, "score": score} for skill, score in skills],
                avatar_initials=initials(name),
            )
        )
    await session.flush()
    created["students"] = len(STUDENTS)

    # ── Advertising ─────────────────────────────────────────────────────────
    known_spots = await _existing(session, AdSpot, AdSpot.code)
    spot_ids: dict[str, uuid.UUID] = {}
    for (code, name, zone, location, dimensions, spot_type, display,
         visibility, monthly, quarterly, yearly) in AD_SPOTS:
        if code in known_spots:
            continue
        spot = AdSpot(
            code=code, name=name, zone=zone, location=location, dimensions=dimensions,
            type=SpotType(spot_type), display_type=display,
            visibility_rating=Decimal(visibility),
            price_monthly=Decimal(monthly), price_quarterly=Decimal(quarterly),
            price_yearly=Decimal(yearly),
        )
        session.add(spot)
        await session.flush()
        spot_ids[code] = spot.id
    created["ad_spots"] = len(spot_ids)

    if spot_ids.get("Z1-B01"):
        start = date.today() - timedelta(days=60)
        session.add(
            AdContract(
                spot_id=spot_ids["Z1-B01"],
                spot_name="Main Entrance Banner",
                zone="Zone A – Entrance",
                company="Decathlon India", brand="Decathlon",
                contact_name="Rahul Gupta", phone="9800011223",
                email="rahul@decathlon.example.com", gst="27AABCX1234Z1ZV",
                start_date=start,
                end_date=start + timedelta(days=180),
                duration_label="6 Months",
                total=Decimal("90000"), paid=Decimal("90000"),
                deposit=Decimal("15000"), installation_fee=Decimal("5000"),
                status=ContractStatus.ACTIVE,
                payment_status="paid",
                timeline=[
                    {"time": start.strftime("%-d %b %Y"), "label": "Contract Created", "type": "created"},
                    {"time": start.strftime("%-d %b %Y"), "label": "Full Payment Received · ₹90,000", "type": "payment"},
                    {"time": start.strftime("%-d %b %Y"), "label": "Banner Installed", "type": "installed"},
                ],
            )
        )
        created["ad_contracts"] = 1

    await session.flush()
    return created
