"""
app.py  ---  Phase 2: auth + login -> chatbot flow
Student logs in (ID + password) -> lands directly in the chatbot.
The Socket.IO 'message' handler is the hook the AI engine plugs into (Phase 3).

Run:  python app.py     ->  http://127.0.0.1:5000
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_socketio import SocketIO
from werkzeug.security import check_password_hash
from functools import wraps
from datetime import datetime
import sqlite3
import ai_engine
import mailer

app = Flask(__name__)
app.config['SECRET_KEY'] = 'change-this-in-production'

socketio = SocketIO(app, cors_allowed_origins="*")

DB = "college.db"


def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def verify_password(stored, given):
    """Works with both werkzeug hashes and the plaintext demo seed (1234)."""
    if not stored:
        return False
    if stored.startswith(("pbkdf2:", "scrypt:")):
        try:
            return check_password_hash(stored, given)
        except Exception:
            return False
    return stored == given


# ---------------- STUDENT LOGIN ---------------- #
@app.route('/', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        sid = request.form.get('student_id', '').strip().upper()
        pw = request.form.get('password', '')

        conn = db()
        row = conn.execute(
            "SELECT student_id, name, password, status FROM students WHERE student_id=?",
            (sid,)).fetchone()
        conn.close()

        if row and verify_password(row['password'], pw):
            if row['status'] != 'Active':
                error = "This account is inactive. Please contact the office."
            else:
                session['student_id'] = row['student_id']
                session['name'] = row['name']
                return redirect(url_for('chat'))
        else:
            error = "Wrong student ID or password."

    return render_template('login.html', error=error)


# ---------------- CHATBOT PAGE ---------------- #
@app.route('/chat')
def chat():
    if 'student_id' not in session:
        return redirect(url_for('login'))
    return render_template('chat.html',
                           name=session['name'],
                           student_id=session['student_id'])


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ---------------- BOT (AI engine — Phase 3) ---------------- #
def get_response(student_id, message):
    """Delegates to the sentence-transformers intent engine."""
    return ai_engine.get_ai_response(student_id, message)


@socketio.on('message')
def handle_message(msg):
    sid = session.get('student_id')
    if not sid:
        socketio.send("Your session expired. Please log in again.")
        return
    socketio.send(get_response(sid, msg))


# ==================================================================
#  ADMIN PANEL  (Phase 4)
# ==================================================================

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('admin'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return wrapper


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        u = request.form.get('username', '').strip()
        p = request.form.get('password', '')
        conn = db()
        row = conn.execute("SELECT username, password FROM admin WHERE username=?", (u,)).fetchone()
        conn.close()
        if row and verify_password(row['password'], p):
            session['admin'] = row['username']
            return redirect(url_for('admin_dashboard'))
        error = "Wrong username or password."
    return render_template('admin/login.html', error=error)


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('admin_login'))


def compute_stats():
    conn = db()
    g = lambda q, *a: conn.execute(q, a).fetchall()
    one = lambda q, *a: conn.execute(q, a).fetchone()[0]

    stats = {
        'total_students': one("SELECT COUNT(*) FROM students"),
        'pending_fees': one("SELECT COALESCE(SUM(pending_fee),0) FROM fees"),
        'collected_fees': one("SELECT COALESCE(SUM(paid_fee),0) FROM fees"),
        'open_tickets': one("SELECT COUNT(*) FROM tickets WHERE status='pending'"),
        'hostel_allotted': one("SELECT COUNT(*) FROM hostel WHERE status='allotted'"),
        'at_risk': one("SELECT COUNT(*) FROM students WHERE attendance < 75"),
        'by_course': {r['course_id']: r['c'] for r in
                      g("SELECT course_id, COUNT(*) c FROM students GROUP BY course_id")},
        'by_gender': {r['gender']: r['c'] for r in
                      g("SELECT gender, COUNT(*) c FROM students GROUP BY gender")},
        'by_category': {r['category']: r['c'] for r in
                        g("SELECT category, COUNT(*) c FROM students GROUP BY category ORDER BY c DESC")},
    }
    conn.close()
    return stats


@app.route('/admin')
@admin_required
def admin_dashboard():
    return render_template('admin/dashboard.html', s=compute_stats())


# ---------------- STUDENTS ---------------- #
@app.route('/admin/students')
@admin_required
def admin_students():
    q = request.args.get('q', '').strip()
    course = request.args.get('course', '').strip()
    conn = db()
    sql = "SELECT student_id,name,email,course_id,current_sem,attendance,cgpa,status FROM students WHERE 1=1"
    params = []
    if q:
        sql += " AND (student_id LIKE ? OR name LIKE ? OR email LIKE ?)"
        params += [f"%{q}%", f"%{q}%", f"%{q}%"]
    if course:
        sql += " AND course_id=?"
        params.append(course)
    sql += " ORDER BY student_id LIMIT 300"
    rows = conn.execute(sql, params).fetchall()
    courses = [r['course_id'] for r in conn.execute("SELECT course_id FROM courses").fetchall()]
    conn.close()
    return render_template('admin/students.html', rows=rows, q=q, course=course, courses=courses)


@app.route('/admin/students/add', methods=['GET', 'POST'])
@admin_required
def admin_student_add():
    conn = db()
    courses = [r['course_id'] for r in conn.execute("SELECT course_id FROM courses").fetchall()]
    if request.method == 'POST':
        f = request.form
        try:
            conn.execute("""INSERT INTO students
                (student_id, name, email, phone, password, course_id, current_sem,
                 gender, dob, category, city, state, admission_year, blood_group,
                 guardian_name, guardian_phone, attendance, cgpa, status,
                 father_name, address, batch, division)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (f['student_id'].strip().upper(),
                 f['name'],
                 f['email'],
                 f.get('phone', ''),
                 '1234',
                 f['course_id'],
                 int(f['current_sem']),
                 f.get('gender', 'Male'),
                 f.get('dob', ''),
                 f.get('category', 'General'),
                 f.get('city', ''),
                 f.get('state', ''),
                 int(f.get('admission_year', 2024)),
                 f.get('blood_group', ''),
                 f.get('guardian_name', ''),
                 f.get('guardian_phone', ''),
                 int(f.get('attendance', 75)),
                 0.0,
                 'Active',
                 f.get('father_name', ''),
                 f.get('address', ''),
                 f.get('batch', ''),
                 f.get('division', 'A')))
            conn.commit()
            conn.close()
            flash(f"Student {f['student_id'].upper()} added.", "ok")
            return redirect(url_for('admin_students'))
        except Exception as e:
            conn.close()
            return render_template('admin/student_form.html', courses=courses,
                                   student=None, error=str(e))
    conn.close()
    return render_template('admin/student_form.html', courses=courses, student=None, error=None)


@app.route('/admin/students/edit/<sid>', methods=['GET', 'POST'])
@admin_required
def admin_student_edit(sid):
    conn = db()
    courses = [r['course_id'] for r in conn.execute("SELECT course_id FROM courses").fetchall()]
    if request.method == 'POST':
        f = request.form
        conn.execute("""UPDATE students SET
                        name=?, email=?, phone=?, course_id=?, current_sem=?, gender=?,
                        dob=?, category=?, city=?, state=?, blood_group=?,
                        guardian_name=?, guardian_phone=?, attendance=?, status=?,
                        father_name=?, address=?, batch=?, division=?
                        WHERE student_id=?""",
                     (f['name'],
                      f['email'],
                      f.get('phone', ''),
                      f['course_id'],
                      int(f['current_sem']),
                      f.get('gender', 'Male'),
                      f.get('dob', ''),
                      f.get('category', 'General'),
                      f.get('city', ''),
                      f.get('state', ''),
                      f.get('blood_group', ''),
                      f.get('guardian_name', ''),
                      f.get('guardian_phone', ''),
                      int(f.get('attendance', 75)),
                      f.get('status', 'Active'),
                      f.get('father_name', ''),
                      f.get('address', ''),
                      f.get('batch', ''),
                      f.get('division', 'A'),
                      sid))
        conn.commit()
        conn.close()
        flash(f"Student {sid} updated.", "ok")
        return redirect(url_for('admin_students'))
    student = conn.execute("SELECT * FROM students WHERE student_id=?", (sid,)).fetchone()
    conn.close()
    if not student:
        return redirect(url_for('admin_students'))
    return render_template('admin/student_form.html', courses=courses, student=student, error=None)


@app.route('/admin/students/delete/<sid>', methods=['POST'])
@admin_required
def admin_student_delete(sid):
    conn = db()
    conn.execute("DELETE FROM students WHERE student_id=?", (sid,))
    conn.execute("DELETE FROM fees WHERE student_id=?", (sid,))
    conn.execute("DELETE FROM hostel WHERE student_id=?", (sid,))
    conn.execute("DELETE FROM results WHERE student_id=?", (sid,))
    conn.commit()
    conn.close()
    flash(f"Student {sid} deleted.", "ok")
    return redirect(url_for('admin_students'))


# ---------------- NOTICES ---------------- #
@app.route('/admin/notices', methods=['GET', 'POST'])
@admin_required
def admin_notices():
    conn = db()
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        body = request.form.get('body', '').strip()
        course = request.form.get('course_id', '').strip() or None
        if title and body:
            conn.execute("INSERT INTO notices(title,body,course_id,created_at) VALUES(?,?,?,?)",
                         (title, body, course, datetime.now().date().isoformat()))
            conn.commit()
            flash("Notice posted.", "ok")
        conn.close()
        return redirect(url_for('admin_notices'))
    rows = conn.execute("SELECT * FROM notices ORDER BY id DESC").fetchall()
    courses = [r['course_id'] for r in conn.execute("SELECT course_id FROM courses").fetchall()]
    conn.close()
    return render_template('admin/notices.html', rows=rows, courses=courses)


@app.route('/admin/notices/delete/<int:nid>', methods=['POST'])
@admin_required
def admin_notice_delete(nid):
    conn = db()
    conn.execute("DELETE FROM notices WHERE id=?", (nid,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_notices'))


# ---------------- TICKETS (ask-admin queue -> email) ---------------- #
@app.route('/admin/tickets')
@admin_required
def admin_tickets():
    conn = db()
    rows = conn.execute("""
        SELECT t.*, s.name, s.email FROM tickets t
        JOIN students s ON t.student_id = s.student_id
        ORDER BY (t.status='pending') DESC, t.id DESC""").fetchall()
    conn.close()
    return render_template('admin/tickets.html', rows=rows, mail_ready=mailer.is_configured())


@app.route('/admin/tickets/answer/<int:tid>', methods=['POST'])
@admin_required
def admin_ticket_answer(tid):
    answer = request.form.get('answer', '').strip()
    if not answer:
        return redirect(url_for('admin_tickets'))

    conn = db()
    t = conn.execute("""SELECT t.*, s.name, s.email FROM tickets t
                        JOIN students s ON t.student_id=s.student_id
                        WHERE t.id=?""", (tid,)).fetchone()
    if not t:
        conn.close()
        return redirect(url_for('admin_tickets'))

    conn.execute("UPDATE tickets SET answer=?, status='answered', answered_at=? WHERE id=?",
                 (answer, datetime.now().isoformat(timespec='seconds'), tid))
    conn.commit()
    conn.close()

    body = (f"Dear {t['name']},\n\n"
            f"You asked: {t['question']}\n\n"
            f"Our reply: {answer}\n\n"
            f"Regards,\nCollege Administration")
    ok, info = mailer.send_email(t['email'], "Reply to your question", body)
    if ok:
        flash(f"Answered and emailed to {t['email']}.", "ok")
    else:
        flash(f"Answer saved, but email not sent: {info}", "warn")
    return redirect(url_for('admin_tickets'))


# ---------------- ACADEMICS: helpers ---------------- #
def _grade(m):
    if m is None:
        return (None, 0)
    if m >= 90: return ("A+", 10)
    if m >= 80: return ("A", 9)
    if m >= 70: return ("B+", 8)
    if m >= 60: return ("B", 7)
    if m >= 50: return ("C", 6)
    if m >= 40: return ("D", 5)
    return ("F", 0)


def _course_list():
    conn = db()
    rows = conn.execute("SELECT course_id, total_sems FROM courses ORDER BY course_id").fetchall()
    conn.close()
    return rows


# ---------------- SUBJECTS ---------------- #
@app.route('/admin/subjects', methods=['GET', 'POST'])
@admin_required
def admin_subjects():
    course = request.args.get('course', 'MBA')
    sem = int(request.args.get('sem', 1))
    conn = db()
    if request.method == 'POST':
        course = request.form['course']; sem = int(request.form['sem'])
        code = request.form.get('subject_code', '').strip()
        name = request.form.get('subject_name', '').strip()
        if code and name:
            conn.execute("INSERT INTO subjects(course_id,semester,subject_code,subject_name) VALUES(?,?,?,?)",
                         (course, sem, code, name))
            conn.commit()
            flash("Subject added.", "ok")
        conn.close()
        return redirect(url_for('admin_subjects', course=course, sem=sem))
    rows = conn.execute("SELECT * FROM subjects WHERE course_id=? AND semester=? ORDER BY id",
                        (course, sem)).fetchall()
    conn.close()
    return render_template('admin/subjects.html', rows=rows, course=course, sem=sem,
                           courses=_course_list())


@app.route('/admin/subjects/delete/<int:sid>', methods=['POST'])
@admin_required
def admin_subject_delete(sid):
    conn = db()
    row = conn.execute("SELECT course_id, semester FROM subjects WHERE id=?", (sid,)).fetchone()
    conn.execute("DELETE FROM subjects WHERE id=?", (sid,))
    conn.execute("DELETE FROM exams WHERE subject_id=?", (sid,))
    conn.execute("DELETE FROM results WHERE subject_id=?", (sid,))
    conn.commit()
    conn.close()
    if row:
        return redirect(url_for('admin_subjects', course=row['course_id'], sem=row['semester']))
    return redirect(url_for('admin_subjects'))


# ---------------- EXAM SCHEDULE ---------------- #
@app.route('/admin/exams', methods=['GET', 'POST'])
@admin_required
def admin_exams():
    course = request.args.get('course', 'MBA')
    sem = int(request.args.get('sem', 1))
    conn = db()
    if request.method == 'POST':
        course = request.form['course']; sem = int(request.form['sem'])
        subs = conn.execute("SELECT id FROM subjects WHERE course_id=? AND semester=?",
                            (course, sem)).fetchall()
        for s in subs:
            d = request.form.get(f"date_{s['id']}", '').strip()
            if not d:
                continue
            ex = conn.execute("SELECT id FROM exams WHERE subject_id=?", (s['id'],)).fetchone()
            if ex:
                conn.execute("UPDATE exams SET exam_date=? WHERE id=?", (d, ex['id']))
            else:
                conn.execute("INSERT INTO exams(course_id,semester,subject_id,exam_date,exam_type) "
                             "VALUES(?,?,?,?,'End-Sem')", (course, sem, s['id'], d))
        conn.commit()
        flash("Exam dates saved.", "ok")
        conn.close()
        return redirect(url_for('admin_exams', course=course, sem=sem))
    rows = conn.execute("""SELECT sub.id, sub.subject_name, e.exam_date
                           FROM subjects sub LEFT JOIN exams e ON e.subject_id=sub.id
                           WHERE sub.course_id=? AND sub.semester=? ORDER BY sub.id""",
                        (course, sem)).fetchall()
    conn.close()
    return render_template('admin/exams.html', rows=rows, course=course, sem=sem,
                           courses=_course_list())


# ---------------- RESULTS DECLARATION ---------------- #
@app.route('/admin/results', methods=['GET', 'POST'])
@admin_required
def admin_results():
    course = request.args.get('course', 'MBA')
    sem = int(request.args.get('sem', 1))
    conn = db()
    if request.method == 'POST':
        course = request.form['course']; sem = int(request.form['sem'])
        result_date = request.form.get('result_date', '').strip()
        students = conn.execute(
            "SELECT student_id FROM students WHERE course_id=? AND current_sem=?",
            (course, sem)).fetchall()
        subs = conn.execute("SELECT id FROM subjects WHERE course_id=? AND semester=?",
                            (course, sem)).fetchall()
        for st in students:
            for su in subs:
                raw = request.form.get(f"m_{st['student_id']}_{su['id']}", '').strip()
                marks = int(raw) if raw.isdigit() else None
                grade, _ = _grade(marks)
                conn.execute("""UPDATE results SET marks=?, grade=?, declared=1, result_date=?
                                WHERE student_id=? AND semester=? AND subject_id=?""",
                             (marks, grade, result_date, st['student_id'], sem, su['id']))
            pts = conn.execute("""SELECT marks FROM results
                                  WHERE student_id=? AND declared=1 AND marks IS NOT NULL""",
                               (st['student_id'],)).fetchall()
            gp = [_grade(r['marks'])[1] for r in pts]
            if gp:
                conn.execute("UPDATE students SET cgpa=? WHERE student_id=?",
                             (round(sum(gp)/len(gp), 2), st['student_id']))
        conn.commit()
        flash(f"Results declared for {course} semester {sem}.", "ok")
        conn.close()
        return redirect(url_for('admin_results', course=course, sem=sem))

    students = conn.execute(
        "SELECT student_id, name FROM students WHERE course_id=? AND current_sem=? ORDER BY student_id",
        (course, sem)).fetchall()
    subs = conn.execute("SELECT id, subject_code FROM subjects WHERE course_id=? AND semester=? ORDER BY id",
                        (course, sem)).fetchall()
    marks = {}
    for st in students:
        for su in subs:
            r = conn.execute("SELECT marks FROM results WHERE student_id=? AND semester=? AND subject_id=?",
                             (st['student_id'], sem, su['id'])).fetchone()
            marks[(st['student_id'], su['id'])] = (r['marks'] if r and r['marks'] is not None else '')
    declared = conn.execute("SELECT declared, result_date FROM results WHERE semester=? AND subject_id IN "
                            "(SELECT id FROM subjects WHERE course_id=? AND semester=?) LIMIT 1",
                            (sem, course, sem)).fetchone()
    conn.close()
    return render_template('admin/results.html', students=students, subs=subs, marks=marks,
                           course=course, sem=sem, courses=_course_list(),
                           declared=declared)


# ---------------- FEES ---------------- #
@app.route('/admin/fees', methods=['GET', 'POST'])
@admin_required
def admin_fees():
    conn = db()
    if request.method == 'POST':
        sid = request.form['student_id']
        total = int(request.form.get('total_fee', 0))
        paid = int(request.form.get('paid_fee', 0))
        last = request.form.get('last_pay_date', '').strip()
        conn.execute("""UPDATE fees SET total_fee=?, paid_fee=?, pending_fee=?, last_pay_date=?
                        WHERE student_id=?""",
                     (total, paid, max(total - paid, 0), last, sid))
        conn.commit()
        flash(f"Fees updated for {sid}.", "ok")
        conn.close()
        return redirect(url_for('admin_fees', q=request.args.get('q', '')))
    q = request.args.get('q', '').strip()
    sql = """SELECT s.student_id, s.name, s.course_id, f.semester, f.total_fee, f.paid_fee,
                    f.pending_fee, f.last_pay_date
             FROM students s JOIN fees f ON s.student_id=f.student_id WHERE 1=1"""
    params = []
    if q:
        sql += " AND (s.student_id LIKE ? OR s.name LIKE ?)"; params += [f"%{q}%", f"%{q}%"]
    sql += " ORDER BY s.student_id LIMIT 100"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return render_template('admin/fees.html', rows=rows, q=q)


# ---------------- MAIN ---------------- #
if __name__ == '__main__':
    print("Loading AI model (first run downloads ~80MB — please wait, do not press Ctrl+C)...")
    ai_engine.warmup()
    print("Model ready.")
    print("Server running on http://127.0.0.1:5000")
    socketio.run(app, host='127.0.0.1', port=5000,
                 debug=True, use_reloader=False, allow_unsafe_werkzeug=True)