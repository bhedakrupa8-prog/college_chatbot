"""
ai_engine.py  ---  Phase 3: the chatbot brain
- Understands intent with sentence-transformers (all-MiniLM-L6-v2), not keyword matching
- Routes to a handler that reads THIS student's data from college.db
- Falls back to general FAQ, then to an ask-admin ticket (emailed in Phase 4)

Public entry point:  get_ai_response(student_id, message) -> str

The model loads lazily on the first question (first call downloads ~80MB once),
so importing this module is cheap and the DB handlers stay unit-testable.
"""

import sqlite3

DB = "college.db"

# Tune these if routing feels too loose / too strict (cosine, 0..1)
INTENT_THRESHOLD = 0.42
FAQ_THRESHOLD = 0.40

# ---------------- intent training phrases ---------------- #
INTENT_PHRASES = {
    "greeting": ["hi", "hello", "hey", "good morning", "namaste", "kem cho", "how are you"],
    "fees": ["my fees", "pending fees", "how much fees do i have to pay", "fee details",
             "tuition fee", "how much do i owe", "last date to pay fees", "fee due date",
             "when is the last date to pay fees", "remaining fees", "how much have i paid"],
    "results": ["my results", "my marks", "my grades", "result date", "my cgpa",
                "when will results be declared", "semester result", "have results come out",
                "is my result declared", "exam result"],
    "exams": ["exam dates", "exam schedule", "when is my exam", "exam timetable",
              "when are exams", "end sem exam date", "my exam time table"],
    "subjects": ["my subjects", "subjects this semester", "what subjects do i have",
                 "subject list", "semester subjects", "which subjects am i studying"],
    "hostel": ["hostel details", "my hostel", "hostel room", "room number", "hostel fee",
               "am i allotted hostel", "my hostel room number"],
    "notices": ["notices", "any notice", "announcements", "latest notice", "college notice",
                "any new notice for me"],
    "attendance": ["my attendance", "attendance percentage", "how much attendance do i have",
                   "am i short on attendance"],
    "profile": ["my details", "my profile", "my information", "who am i", "my course",
                "which semester am i in", "my department", "my email"],
}

# lazy-loaded globals
_model = None
_intent_labels = None
_intent_emb = None
_faq_questions = None
_faq_answers = None
_faq_emb = None
_util = None


def _db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def _init():
    """Load the model + precompute embeddings once, on first use."""
    global _model, _intent_labels, _intent_emb, _util
    global _faq_questions, _faq_answers, _faq_emb
    if _model is not None:
        return

    from sentence_transformers import SentenceTransformer, util
    _util = util
    _model = SentenceTransformer('all-MiniLM-L6-v2')

    labels, texts = [], []
    for label, phrases in INTENT_PHRASES.items():
        for p in phrases:
            labels.append(label)
            texts.append(p)
    _intent_labels = labels
    _intent_emb = _model.encode(texts, convert_to_tensor=True, normalize_embeddings=True)

    conn = _db()
    rows = conn.execute("SELECT question, answer FROM faqs").fetchall()
    conn.close()
    _faq_questions = [r["question"] for r in rows]
    _faq_answers = [r["answer"] for r in rows]
    _faq_emb = _model.encode(_faq_questions, convert_to_tensor=True, normalize_embeddings=True)


def _detect(query):
    """Return (intent, intent_score, faq_index, faq_score)."""
    q = _model.encode(query, convert_to_tensor=True, normalize_embeddings=True)

    isims = _util.cos_sim(q, _intent_emb)[0]
    ii = int(isims.argmax())
    intent, iscore = _intent_labels[ii], float(isims[ii])

    fsims = _util.cos_sim(q, _faq_emb)[0]
    fi = int(fsims.argmax())
    fscore = float(fsims[fi])

    return intent, iscore, fi, fscore


# ======================= HANDLERS ======================= #
# Each handler reads the logged-in student's own rows.

def _student(sid):
    conn = _db()
    row = conn.execute("SELECT * FROM students WHERE student_id=?", (sid,)).fetchone()
    conn.close()
    return row


def h_greeting(sid):
    s = _student(sid)
    first = s["name"].split(" ")[0] if s else "there"
    return (f"Hi {first}! You can ask me about your fees, results, exam dates, "
            f"subjects, hostel or college notices. What would you like to know?")


def h_fees(sid):
    conn = _db()
    f = conn.execute(
        "SELECT semester,total_fee,paid_fee,pending_fee,last_pay_date "
        "FROM fees WHERE student_id=? ORDER BY semester DESC LIMIT 1", (sid,)).fetchone()
    conn.close()
    if not f:
        return "I couldn't find any fee record for your account. Please contact the accounts office."
    if f["pending_fee"] > 0:
        return (f"For semester {f['semester']}, your total fee is ₹{f['total_fee']:,}. "
                f"You've paid ₹{f['paid_fee']:,}, and ₹{f['pending_fee']:,} is still pending. "
                f"The last date to pay is {f['last_pay_date']}.")
    return (f"Your semester {f['semester']} fees of ₹{f['total_fee']:,} are fully paid. "
            f"Nothing is pending.")


def h_results(sid):
    s = _student(sid)
    cur = s["current_sem"]
    conn = _db()
    declared = conn.execute(
        "SELECT declared, result_date FROM results WHERE student_id=? AND semester=? LIMIT 1",
        (sid, cur)).fetchone()
    parts = []
    if declared and declared["declared"] == 0:
        parts.append(f"Your semester {cur} results are not declared yet. "
                     f"They are expected on {declared['result_date']}.")
    elif declared:
        rows = conn.execute(
            "SELECT sub.subject_name, r.grade, r.marks FROM results r "
            "JOIN subjects sub ON r.subject_id=sub.id "
            "WHERE r.student_id=? AND r.semester=?", (sid, cur)).fetchall()
        lines = "\n".join(f"  • {r['subject_name']}: {r['grade']} ({r['marks']})" for r in rows)
        parts.append(f"Your semester {cur} results:\n{lines}")
    if s["cgpa"] and s["cgpa"] > 0:
        parts.append(f"Your CGPA so far is {s['cgpa']}.")
    conn.close()
    return " ".join(parts) if parts else "No result information is available yet."


def h_exams(sid):
    s = _student(sid)
    conn = _db()
    rows = conn.execute(
        "SELECT sub.subject_name, e.exam_date, e.exam_type FROM exams e "
        "JOIN subjects sub ON e.subject_id=sub.id "
        "WHERE e.course_id=? AND e.semester=? ORDER BY e.exam_date",
        (s["course_id"], s["current_sem"])).fetchall()
    conn.close()
    if not rows:
        return f"No exam schedule is published yet for semester {s['current_sem']}."
    lines = "\n".join(f"  • {r['exam_date']} — {r['subject_name']} ({r['exam_type']})" for r in rows)
    return f"Your semester {s['current_sem']} exam schedule:\n{lines}"


def h_subjects(sid):
    s = _student(sid)
    conn = _db()
    rows = conn.execute(
        "SELECT subject_code, subject_name FROM subjects WHERE course_id=? AND semester=? ORDER BY id",
        (s["course_id"], s["current_sem"])).fetchall()
    conn.close()
    if not rows:
        return f"No subjects are listed for semester {s['current_sem']}."
    lines = "\n".join(f"  • {r['subject_code']} — {r['subject_name']}" for r in rows)
    return f"Your subjects for {s['course_id']} semester {s['current_sem']}:\n{lines}"


def h_hostel(sid):
    conn = _db()
    h = conn.execute(
        "SELECT hostel_name, room_no, hostel_fee, status FROM hostel WHERE student_id=?",
        (sid,)).fetchone()
    conn.close()
    if not h or h["status"] != "allotted":
        return ("You don't have a hostel room allotted. If you'd like one, please apply at "
                "the hostel office.")
    return (f"You're allotted in {h['hostel_name']}, room {h['room_no']}. "
            f"The hostel fee is ₹{h['hostel_fee']:,} per year.")


def h_notices(sid):
    s = _student(sid)
    conn = _db()
    rows = conn.execute(
        "SELECT title, body FROM notices WHERE course_id IS NULL OR course_id=? "
        "ORDER BY id DESC LIMIT 5", (s["course_id"],)).fetchall()
    conn.close()
    if not rows:
        return "There are no notices right now."
    lines = "\n".join(f"  • {r['title']}: {r['body']}" for r in rows)
    return f"Latest notices:\n{lines}"


def h_attendance(sid):
    s = _student(sid)
    a = s["attendance"]
    warn = "" if a >= 75 else " You're below the 75% requirement — please attend regularly."
    return f"Your attendance is {a}%.{warn}"


def h_profile(sid):
    s = _student(sid)
    return (f"You are {s['name']} ({s['student_id']}), enrolled in {s['course_id']}, "
            f"semester {s['current_sem']}. Registered email: {s['email']}.")


HANDLERS = {
    "greeting": h_greeting, "fees": h_fees, "results": h_results, "exams": h_exams,
    "subjects": h_subjects, "hostel": h_hostel, "notices": h_notices,
    "attendance": h_attendance, "profile": h_profile,
}


def _create_ticket(sid, message):
    from datetime import datetime
    conn = _db()
    conn.execute(
        "INSERT INTO tickets(student_id, question, created_at) VALUES(?,?,?)",
        (sid, message, datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    email = conn.execute("SELECT email FROM students WHERE student_id=?", (sid,)).fetchone()["email"]
    conn.close()
    return ("I don't have a ready answer for that, so I've forwarded your question to the admin. "
            f"You'll receive the reply by email at {email}.")


# ======================= ENTRY POINT ======================= #
def get_ai_response(student_id, message):
    try:
        _init()
        intent, iscore, fi, fscore = _detect(message)
        if iscore >= INTENT_THRESHOLD and iscore >= fscore:
            return HANDLERS[intent](student_id)
        if fscore >= FAQ_THRESHOLD:
            return _faq_answers[fi]
        return _create_ticket(student_id, message)
    except Exception as e:
        return ("Something went wrong while answering that. Please try again. "
                f"(debug: {type(e).__name__})")


def warmup():
    """Load the model + embeddings up front so the first chat reply is instant."""
    _init()
    _model.encode(["warmup"], normalize_embeddings=True)