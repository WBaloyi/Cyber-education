import json
import os
import re
import secrets
import sqlite3
import time
from datetime import date, timedelta
from urllib.parse import urlencode
from functools import wraps
from pathlib import Path

from flask import (Flask, Response, abort, jsonify, redirect, render_template, request, send_from_directory,
                   session, url_for)

from database import close_db, get_db, init_db

BASE_DIR = Path(__file__).parent
COURSES_FILE = BASE_DIR / "course-data.json"
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

# Form limits (kept in sync with the maxlength attributes in the templates).
# The Node.js (Express) feedback API that the About page talks to. See server.js.
NODE_API_URL = os.environ.get("NODE_API_URL", "http://localhost:3000").rstrip("/")

TESTIMONIAL_NAME_MAX = 60
TESTIMONIAL_MESSAGE_MIN = 10
TESTIMONIAL_MESSAGE_MAX = 500
CONTACT_MESSAGE_MAX = 2000


def _local_secret(file_name, env_name, generate):
    """Use the environment variable if set, otherwise a value generated once and kept in a local file."""
    value = os.environ.get(env_name)
    if value:
        return value
    path = BASE_DIR / file_name
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    value = generate()
    path.write_text(value, encoding="utf-8")
    return value


app = Flask(__name__, static_url_path='/static')
app.secret_key = _local_secret(".secret_key", "SECRET_KEY", lambda: secrets.token_hex(32))
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")
ADMIN_PASSWORD = _local_secret(".admin_password", "ADMIN_PASSWORD", lambda: secrets.token_urlsafe(12))

app.teardown_appcontext(close_db)
init_db()


# ---------- Security helpers ----------

def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(32)
    return session["_csrf"]


@app.before_request
def check_csrf():
    if request.method == "POST":
        expected = session.get("_csrf")
        if not expected or not secrets.compare_digest(expected, request.form.get("csrf_token", "")):
            abort(400, "Your form session expired. Please go back, refresh the page and try again.")


@app.after_request
def security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


# Failed admin logins per client address: [failure count, time of first failure].
_failed_logins = {}
LOGIN_LOCKOUT_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 600


# ---------- Template helpers ----------

NAV_ITEMS = [
    ("home", "Home"),
    ("about", "About us"),
    ("course", "Courses"),
    ("testimonials_page", "Testimonials"),
    ("faq", "FAQ"),
    ("contact", "Contact us"),
]
# Pages that highlight a nav item other than their own.
NAV_SECTIONS = {"enroll": "course", "compare": "course", "course_detail": "course", "quiz": "course"}


@app.context_processor
def template_globals():
    return {
        "csrf_token": csrf_token,
        "nav_items": NAV_ITEMS,
        "active_nav": NAV_SECTIONS.get(request.endpoint, request.endpoint),
        "node_api_url": NODE_API_URL,
        "footer": footer_info,
    }


def footer_info():
    """Course links and the next start date for the site footer (read from the JSON file, no database)."""
    with COURSES_FILE.open("r", encoding="utf-8") as file:
        titles = [item["title"] for item in json.load(file)]
    next_start = upcoming_quarter_starts(date.today(), 1)[0]
    return {
        "courses": [{"title": title, "slug": slugify(title)} for title in titles],
        "next_start": format_date(next_start),
        "year": date.today().year,
    }


def format_date(iso_date):
    day = date.fromisoformat(iso_date)
    return f"{day.day} {day.strftime('%b %Y')}"


app.jinja_env.filters["nice_date"] = format_date


# ---------- Course data ----------

def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def split_detail(text):
    """'Course duration: 12 weeks' -> ('Course duration:', '12 weeks')."""
    label, separator, value = text.partition(":")
    return (label + ":", value.strip()) if separator else ("", text)


# Every course starts on the first day of each quarter (1 Jan, 1 Apr, 1 Jul, 1 Oct).
QUARTER_START_MONTHS = (1, 4, 7, 10)
INTAKES_SHOWN = 4  # how many upcoming quarters people can enroll for


def upcoming_quarter_starts(today, count=INTAKES_SHOWN):
    """The next `count` quarter start dates on or after `today`, as ISO strings."""
    starts = []
    year = today.year
    while len(starts) < count:
        for month in QUARTER_START_MONTHS:
            start = date(year, month, 1)
            if start >= today and len(starts) < count:
                starts.append(start.isoformat())
        year += 1
    return starts


def load_courses():
    with COURSES_FILE.open("r", encoding="utf-8") as file:
        courses = json.load(file)

    counts = {
        (row["course_slug"], row["intake_date"]): row["taken"]
        for row in get_db().execute(
            "SELECT course_slug, intake_date, COUNT(*) AS taken FROM enrollments GROUP BY course_slug, intake_date")
    }
    quarter_starts = upcoming_quarter_starts(date.today())

    for course in courses:
        course["slug"] = slugify(course["title"])
        weeks = re.search(r"\d+", course.get("duration", ""))
        course["weeks"] = int(weeks.group()) if weeks else 0
        course["duration_text"] = split_detail(course.get("duration", ""))[1]
        course["self_paced"] = "self" in course.get("modeOfDelivery", "").lower()
        course["delivery"] = "Self-paced" if course["self_paced"] else "Instructor-paced"
        course["details"] = [split_detail(course[key])
                             for key in ("modeOfDelivery", "lecturer", "prerequisite", "courseOutline")
                             if course.get(key)]
        course["has_prerequisite"] = "none" not in course.get("prerequisite", "").lower()

        intakes = []
        for start in quarter_starts:
            intake = {"start": start, "capacity": course.get("capacity", 0)}
            spots_left = max(intake["capacity"] - counts.get((course["slug"], intake["start"]), 0), 0)
            intakes.append({**intake, "spots_left": spots_left, "full": spots_left == 0})
        course["upcoming_intakes"] = intakes
        course["next_intake"] = next((intake for intake in intakes if not intake["full"]), None)
    return courses


def find_course(slug):
    return next((course for course in load_courses() if course["slug"] == slug), None)


def length_group(weeks):
    if weeks <= 12:
        return "short"
    return "medium" if weeks <= 16 else "long"


def outline_modules(course):
    """'Intro, Basics, Functions and Data structures' -> ['Intro', 'Basics', 'Functions', 'Data structures']."""
    outline = split_detail(course.get("courseOutline", ""))[1]
    parts = [part.strip() for part in outline.split(",") if part.strip()]
    if parts and " and " in parts[-1]:
        head, _, tail = parts[-1].rpartition(" and ")
        parts[-1:] = [head.strip(), tail.strip()]
    return parts


def parse_iso_date(text):
    try:
        return date.fromisoformat(text) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text or "") else None
    except ValueError:
        return None


def calendar_links(course_info, start):
    """Download link for an .ics file and a Google Calendar link for a course start date."""
    end = start + timedelta(days=1)
    google = "https://calendar.google.com/calendar/render?" + urlencode({
        "action": "TEMPLATE",
        "text": f"{course_info['title']} starts (Cyber Education)",
        "dates": f"{start:%Y%m%d}/{end:%Y%m%d}",
        "details": f"Week 1 of {course_info['title']} opens today. Course duration: {course_info['duration_text']}.",
    })
    ics = url_for("course_calendar", slug=course_info["slug"], start=start.isoformat())
    return {"ics": ics, "google": google}


# ---------- Static script and data routes ----------

@app.get("/Java.js")
def javascript():
    return send_from_directory(BASE_DIR, "Java.js")


@app.get("/Testimonial.js")
def testimonial_javascript():
    return send_from_directory(BASE_DIR, "Testimonial.js")


@app.get("/course-data.json")
def course_data():
    return send_from_directory(BASE_DIR, "course-data.json")


# ---------- Pages ----------

# Short profile for each lecturer on the About page. Edit the text here.
LECTURER_PROFILES = {
    "Lesile Kalbling": ("AI and programming", "Makes machine learning approachable, starting from Python basics."),
    "Cecilia Palmer": ("Web", "Teaches front-end and full-stack development through real projects."),
    "Robyn Ally": ("Security", "Focuses on threats, risk and practical network defence."),
    "Karabo Motaung": ("Data", "Turns large datasets into clear insights with Python, R and Tableau."),
}


def lecturers_from(courses):
    """Lecturers in the order they first appear, each with the courses they teach and a short profile."""
    lecturers = {}
    for item in courses:
        name = split_detail(item.get("lecturer", ""))[1]
        if not name:
            continue
        if name not in lecturers:
            area, bio = LECTURER_PROFILES.get(name, ("", ""))
            lecturers[name] = {"name": name, "area": area, "bio": bio, "courses": [],
                               "initials": name.split()[0][0] + name.split()[-1][0],
                               "avatar": len(lecturers) % 4 + 1}
        lecturers[name]["courses"].append({"title": item["title"], "slug": item["slug"]})
    return list(lecturers.values())


@app.route('/')
def home():
    courses = load_courses()
    courses.sort(key=lambda item: not item.get("featured"))
    testimonials = approved_testimonials()
    highlights = [row for row in reversed(testimonials) if row["rating"] and row["rating"] >= 4][:2]
    return render_template('Index.html', courses=courses, highlights=highlights,
                           rating_summary=rating_summary(testimonials))


@app.route('/about')
def about():
    courses = load_courses()
    return render_template('About.html', courses=courses, lecturers=lecturers_from(courses),
                           rating_summary=rating_summary(approved_testimonials()))


@app.route('/courses')
def course():
    # The course cards are loaded by JavaScript from /api/courses (see Course.html).
    filters = {key: request.args.get(key, "").strip() for key in ("q", "delivery", "length")}
    return render_template('Course.html', courses=load_courses(), filters=filters)


@app.get('/api/courses')
def api_courses():
    """Course data as JSON for the Courses page, including live spots left per start date."""
    courses = load_courses()
    courses.sort(key=lambda item: not item.get("featured"))  # featured course first
    return jsonify([{
        "slug": item["slug"],
        "title": item["title"],
        "description": item.get("description", ""),
        "outline": split_detail(item.get("courseOutline", ""))[1],
        "image": item["image"],
        "badge": item.get("badge", ""),
        "featured": bool(item.get("featured")),
        "duration": item["duration_text"],
        "weeks": item["weeks"],
        "length_group": length_group(item["weeks"]),
        "delivery": item["delivery"],
        "self_paced": item["self_paced"],
        "details": [{"label": label.rstrip(":"), "value": value} for label, value in item["details"]],
        "intakes": [{"start": intake["start"], "label": format_date(intake["start"]), "full": intake["full"]}
                    for intake in item["upcoming_intakes"]],
        "next_intake": ({"start": item["next_intake"]["start"], "label": format_date(item["next_intake"]["start"])}
                        if item["next_intake"] else None),
        "enroll_url": url_for('enroll', slug=item["slug"]),
        "detail_url": url_for('course_detail', slug=item["slug"]),
    } for item in courses])


@app.route('/compare')
def compare():
    courses = load_courses()
    slugs = [course["slug"] for course in courses]
    first = request.args.get("a") if request.args.get("a") in slugs else slugs[0]
    second = request.args.get("b") if request.args.get("b") in slugs else slugs[1]
    by_slug = {course["slug"]: course for course in courses}
    return render_template('Compare.html', courses=courses, first=by_slug[first], second=by_slug[second])


@app.get('/courses/<slug>')
def course_detail(slug):
    courses = load_courses()
    course_info = next((item for item in courses if item["slug"] == slug), None)
    if course_info is None:
        abort(404)
    lecturer = split_detail(course_info.get("lecturer", ""))[1]
    profile = next((person for person in lecturers_from(courses) if person["name"] == lecturer), None)
    other_courses = [item for item in courses
                     if item["slug"] != slug and split_detail(item.get("lecturer", ""))[1] == lecturer]
    testimonials = approved_testimonials()
    reviews = [row for row in reversed(testimonials) if row["rating"]][:3]
    return render_template('CourseDetail.html', course=course_info, modules=outline_modules(course_info),
                           lecturer=lecturer, profile=profile, other_courses=other_courses, reviews=reviews,
                           rating_summary=rating_summary(testimonials))


@app.get('/courses/<slug>/calendar.ics')
def course_calendar(slug):
    """An all-day calendar event for the course start date."""
    course_info = find_course(slug)
    start = parse_iso_date(request.args.get("start", ""))
    if course_info is None or start is None:
        abort(404)
    end = start + timedelta(days=1)
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Cyber Education//Course start//EN", "CALSCALE:GREGORIAN",
        "BEGIN:VEVENT",
        f"UID:{slug}-{start:%Y%m%d}@cybereducation",
        f"DTSTAMP:{date.today():%Y%m%d}T000000Z",
        f"DTSTART;VALUE=DATE:{start:%Y%m%d}",
        f"DTEND;VALUE=DATE:{end:%Y%m%d}",
        f"SUMMARY:{course_info['title']} starts (Cyber Education)",
        f"DESCRIPTION:Week 1 of {course_info['title']} opens today.",
        "END:VEVENT", "END:VCALENDAR",
    ]
    return Response("\r\n".join(lines) + "\r\n", mimetype="text/calendar",
                    headers={"Content-Disposition": f'attachment; filename="{slug}-{start:%Y-%m-%d}.ics"'})


@app.route('/courses/<slug>/enroll', methods=['GET', 'POST'])
def enroll(slug):
    course_info = find_course(slug)
    if course_info is None:
        abort(404)

    errors, values = {}, {}
    if request.method == 'POST':
        values = {key: request.form.get(key, "").strip() for key in ("name", "email", "intake")}
        if request.form.get("website"):  # honeypot field, hidden from people
            return redirect(url_for('enroll', slug=slug, enrolled=values["intake"]))
        if not 2 <= len(values["name"]) <= 100:
            errors["name"] = "Please enter your full name."
        if not EMAIL_PATTERN.match(values["email"]) or len(values["email"]) > 254:
            errors["email"] = "Please enter a valid email address."
        intake = next((item for item in course_info["upcoming_intakes"] if item["start"] == values["intake"]), None)
        if intake is None:
            errors["intake"] = "Please choose a start date."

        if not errors:
            db = get_db()
            # BEGIN IMMEDIATE locks writers, so two people can't take the last spot at once.
            db.execute("BEGIN IMMEDIATE")
            try:
                taken = db.execute(
                    "SELECT COUNT(*) FROM enrollments WHERE course_slug = ? AND intake_date = ?",
                    (slug, intake["start"])).fetchone()[0]
                if taken >= intake["capacity"]:
                    errors["intake"] = "Sorry, that start date has just filled up. Please choose another."
                else:
                    db.execute(
                        "INSERT INTO enrollments (course_slug, intake_date, name, email) VALUES (?, ?, ?, ?)",
                        (slug, intake["start"], values["name"], values["email"].lower()))
                db.execute("COMMIT")
            except sqlite3.IntegrityError:
                db.execute("ROLLBACK")
                errors["email"] = "This email address is already enrolled for that start date."
            except Exception:
                db.execute("ROLLBACK")
                raise
            if not errors:
                session["last_enrollment"] = {"slug": slug, "start": intake["start"],
                                              "email": values["email"].lower()}
                return redirect(url_for('enroll', slug=slug, enrolled=intake["start"]))
            course_info = find_course(slug)  # refresh spots left

    confirmation = None
    start = parse_iso_date(request.args.get("enrolled", ""))
    if start and not errors:
        last = session.get("last_enrollment") or {}
        days_left = (start - date.today()).days
        confirmation = {
            "start": start,
            "start_long": f"{start:%A}, {start.day} {start:%B %Y}",
            "start_label": f"{start.day} {start:%B %Y}",
            "days_left": days_left,
            "welcome_by": format_date((start - timedelta(days=14)).isoformat()) if days_left > 14 else "",
            "email": last.get("email") if last.get("slug") == slug and last.get("start") == start.isoformat() else "",
            **calendar_links(course_info, start),
        }
    return render_template('Enroll.html', course=course_info, errors=errors, values=values,
                           confirmation=confirmation), (400 if errors else 200)


@app.get('/courses/<slug>/enrol')
def old_enroll_url(slug):
    """Keep links that used the old spelling working."""
    return redirect(url_for('enroll', slug=slug), code=301)


@app.route('/quiz')
def quiz():
    return render_template('Quiz.html', courses=load_courses())


@app.route('/faq')
def faq():
    return render_template('Faq.html', courses=load_courses())


def approved_testimonials():
    return get_db().execute(
        "SELECT id, name, message, rating FROM testimonials WHERE approved = 1 ORDER BY id").fetchall()


def rating_summary(testimonials):
    ratings = [row["rating"] for row in testimonials if row["rating"]]
    return {"average": round(sum(ratings) / len(ratings), 1), "count": len(ratings)} if ratings else None


def render_testimonials(errors=None, values=None, status=200):
    testimonials = approved_testimonials()
    # Newest first, so a just-submitted testimonial is the first card in the carousel.
    return render_template('Testimonials.html', testimonials=list(reversed(testimonials)),
                           rating_summary=rating_summary(testimonials),
                           errors=errors or {}, values=values or {},
                           limits={"name": TESTIMONIAL_NAME_MAX, "message_min": TESTIMONIAL_MESSAGE_MIN,
                                   "message": TESTIMONIAL_MESSAGE_MAX}), status


@app.route('/testimonials')
def testimonials_page():
    return render_testimonials()


@app.post('/submit')
def submit_testimonial():
    values = {key: request.form.get(key, "").strip() for key in ("name", "message", "rating")}
    if request.form.get("website"):  # honeypot field, hidden from people
        return redirect(url_for('testimonials_page', sent=1, _anchor='testimonials'))

    errors = {}
    if not 2 <= len(values["name"]) <= TESTIMONIAL_NAME_MAX:
        errors["name"] = f"Please enter a name between 2 and {TESTIMONIAL_NAME_MAX} characters."
    if not TESTIMONIAL_MESSAGE_MIN <= len(values["message"]) <= TESTIMONIAL_MESSAGE_MAX:
        errors["message"] = (f"Your testimonial must be between {TESTIMONIAL_MESSAGE_MIN} and "
                             f"{TESTIMONIAL_MESSAGE_MAX} characters.")
    if values["rating"] not in {"1", "2", "3", "4", "5"}:
        errors["rating"] = "Please choose a star rating."
    if errors:
        return render_testimonials(errors, values, 400)

    # New testimonials are published straight away and appear first in the carousel.
    # Admins can still hide or delete them from the dashboard.
    get_db().execute("INSERT INTO testimonials (name, message, rating, approved) VALUES (?, ?, ?, 1)",
                     (values["name"], values["message"], int(values["rating"])))
    return redirect(url_for('testimonials_page', sent=1, _anchor='testimonials'))


@app.get('/api/testimonials')
def testimonials():
    return jsonify([dict(row) for row in approved_testimonials()])


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    errors, values = {}, {}
    if request.method == 'POST':
        values = {
            "name": request.form.get('name', '').strip(),
            "email": request.form.get('email', '').strip(),
            "course": request.form.get('courseOfIntrest', '').strip(),
            "message": request.form.get('message', '').strip(),
        }
        if request.form.get("website"):  # honeypot field, hidden from people
            return redirect(url_for('contact', sent=1))
        if not 3 <= len(values["name"]) <= 100:
            errors["name"] = "Please enter at least 3 characters."
        if not EMAIL_PATTERN.match(values["email"]) or len(values["email"]) > 254:
            errors["email"] = "Please enter a valid email address."
        if not 5 <= len(values["course"]) <= 100:
            errors["course"] = "Please enter at least 5 characters."
        if not 10 <= len(values["message"]) <= CONTACT_MESSAGE_MAX:
            errors["message"] = f"Please enter between 10 and {CONTACT_MESSAGE_MAX} characters."
        if not errors:
            get_db().execute(
                "INSERT INTO contact_submissions (name, email, course_of_interest, message) VALUES (?, ?, ?, ?)",
                (values["name"], values["email"], values["course"], values["message"]))
            return redirect(url_for('contact', sent=1))

    course_names = [item["title"] for item in load_courses()]
    return render_template('Contact.html', errors=errors, values=values, course_names=course_names,
                           message_max=CONTACT_MESSAGE_MAX), (400 if errors else 200)


# ---------- Admin ----------

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    error = ""
    next_page = request.values.get("next", "")
    if not next_page.startswith("/admin"):
        next_page = url_for("admin_dashboard")

    if request.method == 'POST':
        client = request.remote_addr or "unknown"
        failures, first_failure = _failed_logins.get(client, (0, time.time()))
        if time.time() - first_failure > LOGIN_LOCKOUT_SECONDS:
            failures, first_failure = 0, time.time()

        if failures >= LOGIN_LOCKOUT_ATTEMPTS:
            error = "Too many failed attempts. Please wait 10 minutes and try again."
        elif secrets.compare_digest(request.form.get("password", ""), ADMIN_PASSWORD):
            _failed_logins.pop(client, None)
            session.clear()
            session["is_admin"] = True
            return redirect(next_page)
        else:
            _failed_logins[client] = (failures + 1, first_failure)
            error = "Incorrect password."

    return render_template('admin/Login.html', error=error, next_page=next_page), (401 if error else 200)


@app.post('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('home'))


@app.get('/admin')
@admin_required
def admin_dashboard():
    db = get_db()
    courses = load_courses()
    titles = {course["slug"]: course["title"] for course in courses}
    return render_template(
        'admin/Dashboard.html',
        pending=db.execute("SELECT * FROM testimonials WHERE approved = 0 ORDER BY created_at DESC").fetchall(),
        published=db.execute("SELECT * FROM testimonials WHERE approved = 1 ORDER BY id DESC").fetchall(),
        submissions=db.execute("SELECT * FROM contact_submissions ORDER BY id DESC").fetchall(),
        enrollments=db.execute("SELECT * FROM enrollments ORDER BY intake_date, id").fetchall(),
        courses=courses, titles=titles)


@app.post('/admin/testimonials/<int:testimonial_id>/<action>')
@admin_required
def admin_testimonial(testimonial_id, action):
    db = get_db()
    if action == "approve":
        db.execute("UPDATE testimonials SET approved = 1 WHERE id = ?", (testimonial_id,))
    elif action == "hide":
        db.execute("UPDATE testimonials SET approved = 0 WHERE id = ?", (testimonial_id,))
    elif action == "delete":
        db.execute("DELETE FROM testimonials WHERE id = ?", (testimonial_id,))
    else:
        abort(404)
    return redirect(url_for('admin_dashboard', _anchor='testimonials'))


@app.get('/results')
@admin_required
def results():
    # Contact submissions are private; they now live in the admin dashboard.
    return redirect(url_for('admin_dashboard', _anchor='messages'))


# ---------- Errors ----------

@app.errorhandler(400)
@app.errorhandler(404)
def show_error(error):
    return render_template('Error.html', code=error.code, message=error.description), error.code


if __name__ == '__main__':
    if not os.environ.get("ADMIN_PASSWORD"):
        print(f" * Admin password is stored in {BASE_DIR / '.admin_password'}")
    app.run(debug=True)
