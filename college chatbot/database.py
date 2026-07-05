"""
database.py  ---  builds college.db
4 courses (MBA, MCA, BBA, BCA), 50 students each = 200 dummy Indian students,
with fees, hostel, subjects, exams, results, notices, faqs, ask-admin tickets.
Run once:  python database.py     (safe to re-run; it rebuilds)
All student logins use password: 1234
"""

import sqlite3
import random
from datetime import date, timedelta

random.seed(42)  # reproducible data ("in order")

conn = sqlite3.connect("college.db")
cur = conn.cursor()

for t in ["results", "exams", "subjects", "hostel", "fees",
          "notices", "tickets", "faqs", "students", "courses", "admin"]:
    cur.execute(f"DROP TABLE IF EXISTS {t}")

# ----------------------- SCHEMA ----------------------- #
cur.execute("""CREATE TABLE courses(
    course_id TEXT PRIMARY KEY, course_name TEXT, total_sems INTEGER, annual_fee INTEGER)""")

cur.execute("""CREATE TABLE students(
    student_id     TEXT PRIMARY KEY,
    name           TEXT,
    email          TEXT,
    phone          TEXT,
    password       TEXT,
    course_id      TEXT,
    current_sem    INTEGER,
    gender         TEXT,
    dob            TEXT,
    category       TEXT,        -- General/OBC/SC/ST/EWS
    city           TEXT,
    state          TEXT,
    admission_year INTEGER,
    blood_group    TEXT,
    guardian_name  TEXT,
    guardian_phone TEXT,
    attendance     INTEGER,     -- % (for at-risk analytics)
    cgpa           REAL,
    status         TEXT,        -- Active/Inactive
    father_name    TEXT,
    address        TEXT,
    batch          TEXT,        -- e.g. 2024-2027
    division       TEXT,        -- A / B / C
    FOREIGN KEY(course_id) REFERENCES courses(course_id))""")

cur.execute("""CREATE TABLE fees(
    id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT, semester INTEGER,
    total_fee INTEGER, paid_fee INTEGER, pending_fee INTEGER, last_pay_date TEXT)""")

cur.execute("""CREATE TABLE hostel(
    id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT, hostel_name TEXT,
    room_no TEXT, hostel_fee INTEGER, allotment_date TEXT, status TEXT)""")

cur.execute("""CREATE TABLE subjects(
    id INTEGER PRIMARY KEY AUTOINCREMENT, course_id TEXT, semester INTEGER,
    subject_code TEXT, subject_name TEXT)""")

cur.execute("""CREATE TABLE exams(
    id INTEGER PRIMARY KEY AUTOINCREMENT, course_id TEXT, semester INTEGER,
    subject_id INTEGER, exam_date TEXT, exam_type TEXT)""")

cur.execute("""CREATE TABLE results(
    id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT, semester INTEGER,
    subject_id INTEGER, marks INTEGER, grade TEXT, declared INTEGER DEFAULT 0,
    result_date TEXT)""")

cur.execute("""CREATE TABLE notices(
    id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, body TEXT,
    course_id TEXT, created_at TEXT)""")

cur.execute("""CREATE TABLE faqs(
    id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT, answer TEXT)""")

cur.execute("""CREATE TABLE tickets(
    id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT, question TEXT,
    answer TEXT, status TEXT DEFAULT 'pending', created_at TEXT, answered_at TEXT)""")

cur.execute("""CREATE TABLE admin(
    id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, password TEXT)""")

# ----------------------- COURSES ----------------------- #
courses = [
    ("MBA", "Master of Business Administration", 4, 120000),
    ("MCA", "Master of Computer Applications",   4,  95000),
    ("BBA", "Bachelor of Business Administration",6, 70000),
    ("BCA", "Bachelor of Computer Applications", 6,  75000),
]
cur.executemany("INSERT INTO courses VALUES(?,?,?,?)", courses)

# ----------------------- SUBJECTS ----------------------- #
SUBJECTS = {
 "MBA": {
   1:["Principles of Management","Managerial Economics","Financial Accounting","Business Statistics","Organizational Behavior"],
   2:["Marketing Management","Financial Management","Human Resource Management","Operations Management","Business Research Methods"],
   3:["Strategic Management","Consumer Behavior","Business Analytics","Project Management","Entrepreneurship Development"],
   4:["International Business","Corporate Governance","Supply Chain Management","Digital Marketing","Business Ethics"]},
 "MCA": {
   1:["Programming with C","Discrete Mathematics","Computer Organization","Digital Logic","Communication Skills"],
   2:["Data Structures","Object Oriented Programming","Database Management Systems","Operating Systems","Software Engineering"],
   3:["Web Technologies","Computer Networks","Design and Analysis of Algorithms","Java Programming","Python Programming"],
   4:["Machine Learning","Cloud Computing","Mobile Application Development","Information Security","Big Data Analytics"]},
 "BBA": {
   1:["Principles of Management","Business Economics","Financial Accounting","Business Communication","Business Mathematics"],
   2:["Marketing Management","Cost Accounting","Organizational Behavior","Business Environment","Business Statistics"],
   3:["Human Resource Management","Financial Management","Production Management","Business Law","Management Information Systems"],
   4:["Entrepreneurship","Consumer Behavior","Banking and Insurance","Income Tax","Research Methodology"],
   5:["Strategic Management","International Business","E-Commerce","Retail Management","Project Work I"],
   6:["Corporate Governance","Business Analytics","Supply Chain Management","Digital Marketing","Project Work II"]},
 "BCA": {
   1:["Fundamentals of Computers","Programming in C","Mathematics I","Digital Electronics","Communication Skills"],
   2:["Data Structures","Object Oriented Programming","Mathematics II","Database Management Systems","Operating Systems"],
   3:["Java Programming","Computer Networks","Web Technologies","Software Engineering","Discrete Mathematics"],
   4:["Python Programming","Design and Analysis of Algorithms","Computer Graphics",".NET Framework","Numerical Methods"],
   5:["Machine Learning","Cloud Computing","Mobile App Development","Information Security","Mini Project"],
   6:["Big Data Analytics","Internet of Things","Artificial Intelligence","Software Testing","Major Project"]},
}

subj_id = {}  # (course, sem) -> list of subject ids
for cid, sems in SUBJECTS.items():
    for sem, names in sems.items():
        ids = []
        for i, nm in enumerate(names, start=1):
            code = f"{cid}{sem}0{i}"
            cur.execute("INSERT INTO subjects(course_id,semester,subject_code,subject_name) VALUES(?,?,?,?)",
                        (cid, sem, code, nm))
            ids.append(cur.lastrowid)
        subj_id[(cid, sem)] = ids

# ----------------------- EXAMS (per course+sem) ----------------------- #
base = date(2026, 7, 20)
for cid, sems in SUBJECTS.items():
    for sem in sems:
        for k, sid in enumerate(subj_id[(cid, sem)]):
            cur.execute("INSERT INTO exams(course_id,semester,subject_id,exam_date,exam_type) VALUES(?,?,?,?,?)",
                        (cid, sem, sid, (base + timedelta(days=2*k)).isoformat(), "End-Sem"))

# ----------------------- NAME / DATA POOLS ----------------------- #
male = ["Aarav","Vivaan","Aditya","Arjun","Rohan","Karan","Rahul","Ankur","Pratham","Yash",
        "Harsh","Raj","Aman","Nikhil","Sahil","Dev","Kabir","Ishaan","Siddharth","Manish",
        "Gaurav","Akash","Varun","Tushar","Mohit","Saurabh","Ritik","Parth","Naveen","Vikram",
        "Deepak","Sandeep","Rajesh","Imran","Faizan","Anand","Suresh","Ramesh","Abhishek","Kunal"]
female = ["Aanya","Diya","Aadhya","Saanvi","Ananya","Priya","Neha","Pooja","Sneha","Kavya",
          "Riya","Isha","Meera","Aishwarya","Divya","Shreya","Nisha","Tanvi","Ayesha","Fatima",
          "Sana","Simran","Komal","Anjali","Swati","Deepika","Sakshi","Disha","Aarohi","Nidhi",
          "Megha","Ritika","Bhavna","Kiran","Pallavi","Jyoti","Sonal","Heena","Zoya","Pari"]
last = ["Sharma","Verma","Patel","Gupta","Singh","Kumar","Reddy","Nair","Iyer","Menon",
        "Desai","Joshi","Shah","Mehta","Chauhan","Yadav","Mishra","Pandya","Trivedi","Bhatt",
        "Rao","Naidu","Pillai","Das","Banerjee","Mukherjee","Kapoor","Malhotra","Khan","Sheikh",
        "Ansari","Multani","Solanki","Parmar","Chaudhary","Jain","Agarwal","Saxena","Ghosh","Pawar"]
places = [("Mumbai","Maharashtra"),("Pune","Maharashtra"),("Ahmedabad","Gujarat"),("Surat","Gujarat"),
          ("Bengaluru","Karnataka"),("Chennai","Tamil Nadu"),("New Delhi","Delhi"),("Lucknow","Uttar Pradesh"),
          ("Jaipur","Rajasthan"),("Kolkata","West Bengal"),("Hyderabad","Telangana"),("Kochi","Kerala"),
          ("Indore","Madhya Pradesh"),("Ludhiana","Punjab"),("Patna","Bihar")]
categories = ["General","General","General","OBC","OBC","SC","ST","EWS"]
bloods = ["O+","O+","A+","A+","B+","B+","AB+","O-","A-","B-"]

def grade_for(m):
    if m >= 90: return ("A+", 10)
    if m >= 80: return ("A", 9)
    if m >= 70: return ("B+", 8)
    if m >= 60: return ("B", 7)
    if m >= 50: return ("C", 6)
    if m >= 40: return ("D", 5)
    return ("F", 0)

# ----------------------- STUDENTS + related ----------------------- #
seq = 0
for cid, cname, total_sems, annual in courses:
    for n in range(1, 51):                       # 50 per course
        seq += 1
        sid = f"{cid}{n:03d}"                     # MBA001 ... BCA050
        gender = random.choice(["Male", "Female"])
        first = random.choice(male if gender == "Male" else female)
        ln = random.choice(last)
        name = f"{first} {ln}"
        email = f"{first}.{ln}{n}@college.edu".lower()
        phone = "9" + "".join(random.choice("0123456789") for _ in range(9))
        cur_sem = random.randint(1, total_sems)
        adm_year = 2026 - ((cur_sem - 1) // 2)
        dob = date(2026 - random.randint(18, 24), random.randint(1, 12), random.randint(1, 28)).isoformat()
        cat = random.choice(categories)
        city, st = random.choice(places)
        blood = random.choice(bloods)
        gname = f"{random.choice(male)} {ln}"
        gphone = "9" + "".join(random.choice("0123456789") for _ in range(9))
        attendance = random.randint(55, 99)
        status = "Active" if random.random() > 0.05 else "Inactive"
        father_name = f"{random.choice(male)} {ln}"
        grad_year = adm_year + (total_sems // 2)
        batch = f"{adm_year}-{grad_year}"
        division = random.choice(["A", "B", "C"])
        house = random.randint(1, 280)
        areas = ["MG Road", "Civil Lines", "Gandhi Nagar", "Station Road", "Ring Road",
                 "Adajan", "Vesu", "Satellite", "Kothrud", "Banjara Hills"]
        address = f"{house}, {random.choice(areas)}, {city}, {st}"

        # results for all completed sems (declared) -> compute CGPA
        points = []
        for s in range(1, cur_sem):
            for su in subj_id[(cid, s)]:
                m = random.randint(38, 96)
                g, p = grade_for(m)
                points.append(p)
                cur.execute("INSERT INTO results(student_id,semester,subject_id,marks,grade,declared,result_date) "
                            "VALUES(?,?,?,?,?,1,?)", (sid, s, su, m, g, f"{adm_year}-12-15"))
        # current sem results -> NOT declared yet
        for su in subj_id[(cid, cur_sem)]:
            cur.execute("INSERT INTO results(student_id,semester,subject_id,marks,grade,declared,result_date) "
                        "VALUES(?,?,?,NULL,NULL,0,'2026-08-10')", (sid, cur_sem, su))
        cgpa = round(sum(points) / len(points), 2) if points else 0.0

        cur.execute("""INSERT INTO students VALUES
            (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (sid, name, email, phone, "1234", cid, cur_sem, gender, dob, cat,
             city, st, adm_year, blood, gname, gphone, attendance, cgpa, status,
             father_name, address, batch, division))

        # fees for current sem
        sem_fee = annual // 2
        paid = random.choice([sem_fee, sem_fee, int(sem_fee*0.75), int(sem_fee*0.5), int(sem_fee*0.25)])
        pending = sem_fee - paid
        cur.execute("INSERT INTO fees(student_id,semester,total_fee,paid_fee,pending_fee,last_pay_date) "
                    "VALUES(?,?,?,?,?,?)", (sid, cur_sem, sem_fee, paid, pending, "2026-07-15"))

        # hostel ~40%
        if random.random() < 0.40:
            hname = "Boys Hostel A" if gender == "Male" else "Girls Hostel B"
            room = f"{random.choice('AB')}-{random.randint(101,420)}"
            cur.execute("INSERT INTO hostel(student_id,hostel_name,room_no,hostel_fee,allotment_date,status) "
                        "VALUES(?,?,?,?,?,?)", (sid, hname, room, 50000, f"{adm_year}-07-01", "allotted"))
        else:
            cur.execute("INSERT INTO hostel(student_id,hostel_name,room_no,hostel_fee,allotment_date,status) "
                        "VALUES(?,?,?,?,?,?)", (sid, None, None, 0, None, "not allotted"))

# ----------------------- NOTICES / FAQS / ADMIN ----------------------- #
today = date.today().isoformat()
cur.executemany("INSERT INTO notices(title,body,course_id,created_at) VALUES(?,?,?,?)", [
    ("Fee Reminder", "Last date to pay semester fees is 15 July 2026.", None, today),
    ("Exam Schedule Released", "End-sem exams begin 20 July 2026.", None, today),
    ("Results", "Current semester results will be declared on 10 August 2026.", None, today),
])
cur.executemany("INSERT INTO faqs(question,answer) VALUES(?,?)", [
    ("admission", "Admissions are open from June to August."),
    ("library timing", "Library is open from 8 AM to 8 PM."),
    ("placement", "Placement cell is in Block C and conducts campus drives."),
    ("scholarship", "Scholarship details are available in the accounts office."),
    ("contact", "College email: admin@college.com, phone: 0261-1234567."),
])
cur.execute("INSERT INTO admin(username,password) VALUES('admin','admin123')")

conn.commit()

# ----------------------- SUMMARY ----------------------- #
def one(q, *a):
    cur.execute(q, a); return cur.fetchone()[0]
print("Database created successfully -> college.db")
print("Students      :", one("SELECT COUNT(*) FROM students"))
for c in ["MBA","MCA","BBA","BCA"]:
    print(f"  {c}         :", one("SELECT COUNT(*) FROM students WHERE course_id=?", c))
print("Subjects      :", one("SELECT COUNT(*) FROM subjects"))
print("Results rows  :", one("SELECT COUNT(*) FROM results"))
print("Hostel allotted:", one("SELECT COUNT(*) FROM hostel WHERE status='allotted'"))
print("Sample login  : BCA001 / 1234")
conn.close()