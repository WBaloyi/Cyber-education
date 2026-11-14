# Cyber Education

## 1. Project title and overview

**Cyber Education** is a full-stack web application for online IT courses. Learners can browse courses, compare them, take a quiz to find a good fit, enroll for a start date, share testimonials, and contact the team.

The platform's goal is to make practical technology education flexible and accessible, so anyone can build skills for a career in tech.

Built for **WST 262 (Web Systems and Technologies), Semester Project 3** by Wesani Baloyi.

## 2. Technologies used

| Area | Technologies |
|------|--------------|
| Front end | HTML5 (semantic elements, Jinja templates), CSS3, **Bootstrap 5.3** (CSS and JS), JavaScript (Fetch API) |
| Back end (main) | **Python, Flask**, SQLite |
| Back end (API) | **Node.js, Express.js** |
| Data | JSON files (`course-data.json`, `feedback.json`), SQLite database (`cyber_education.db`) |
| Fonts | Google Fonts (Plus Jakarta Sans, DM Serif Display) |

## 3. Features

### Pages
| Page | URL | What it does |
|------|-----|--------------|
| Home | `/` | Hero, three steps, how we teach, learn with experts, learner reviews, call to action |
| About us | `/about` | Mission and vision, values, team and lecturers |
| Courses | `/courses` | Course cards loaded from the API, live filters, links to each course page |
| Contact us | `/contact` | Contact details and an inquiry form handled by Flask |
| Course detail | `/courses/<course>` | Hero with enroll button, and Bootstrap tabs for overview, syllabus, lecturer and reviews |
| Enroll | `/courses/<course>/enroll` | Pick a start date. The confirmation shows a countdown, next steps, and "Add to calendar" (`.ics` download or Google Calendar) |
| Also | `/compare`, `/quiz`, `/testimonials`, `/faq`, `/courses/<course>/enroll`, `/admin` | Compare two courses, course quiz, testimonials, FAQ, enrollment, admin dashboard |

### Bootstrap integration
- **Navbar** with a collapsing menu button on phones and tablets (`navbar`, `navbar-expand-lg`, `collapse`).
- **Grid system** (`row`, `col-md-*`, `col-lg-*`) on the Courses, About, Contact and Compare pages.
- **Cards** for courses, features and team members.
- **Tabs** on each course page: overview, syllabus, lecturer and reviews.
- **Forms and validation**: `form-control`, `form-select`, `is-invalid` / `invalid-feedback` messages.
- **Alerts, badges, spinners and list groups** for status messages and loading states.
- Fully responsive on mobile, tablet and desktop.
- **Dark mode toggle** (sun/moon button in the navbar). It follows the device's light/dark setting until the visitor picks one, and remembers their choice.

### API integration and dynamic content
- **Flask API `GET /api/courses`**: returns courses as JSON, including the upcoming start dates and whether each is full. The Courses page fetches it with JavaScript, renders the cards, filters them as you type, and refreshes the data every 60 seconds **without reloading the page**.
- **Node.js API `GET /api/courses`**: the Express server reads **`course-data.json`** and returns each course's title, duration, delivery and lecturer. Open <http://localhost:3000/api/courses> to see the JSON it returns.
- **Node.js API `GET/POST /api/feedback`**: reads and saves learner feedback in **`feedback.json`**. Try it at <http://localhost:3000/api/feedback>.
- **Flask API `GET /api/testimonials`**: approved testimonials as JSON.

### Form handling (Flask)
- The **contact form** posts to Flask, which validates every field and stores the inquiry in SQLite. The admin reads inquiries in the dashboard.
- **Enrollment**: choose a start date and enroll. Every course starts on the **first day of each quarter** (1 January, 1 April, 1 July and 1 October), and each start date has a limited number of places.
- **Testimonials** with star ratings, shown as sliding cards that rotate automatically (arrows, dots, keyboard and swipe), next to the share form. New testimonials appear straight away as the first card; admins can hide or delete them from the dashboard.

### Security
CSRF tokens on Flask forms, hidden honeypot fields against spam bots, login lockout after 5 failed admin attempts, security headers, a CORS allow-list and rate limit on the Node.js API, and all user text is inserted into pages as text (never as HTML).

## 4. Setup instructions

### Requirements
- [Python 3.10+](https://www.python.org/downloads/)
- [Node.js 18+](https://nodejs.org/) (includes npm)

### Flask server (main website)

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux

# 2. Install Flask
pip install flask

# 3. Run the app
python app.py
```

Open <http://127.0.0.1:5000>. The database is created automatically on first run.

### Node.js server (feedback API)

Open a **second terminal** in the project folder:

```bash
npm install
npm start
```

The API runs on <http://localhost:3000>. The website itself doesn't depend on it; the Flask app works on its own.

Optional settings (environment variables):

| Variable | Used by | Default |
|----------|---------|---------|
| `NODE_API_URL` | Flask | `http://localhost:3000` |
| `PORT` | Node.js | `3000` |
| `ALLOWED_ORIGINS` | Node.js | `http://127.0.0.1:5000,http://localhost:5000` |
| `ADMIN_PASSWORD` | Flask | generated and saved in `.admin_password` |
| `SECRET_KEY` | Flask | generated and saved in `.secret_key` |

### Admin login

Go to <http://127.0.0.1:5000/admin>. If `ADMIN_PASSWORD` is not set, a password is generated on first run and saved in `.admin_password` (the path is printed when the app starts).

**Do not commit `.admin_password`, `.secret_key` or `cyber_education.db`.**

## 5. Folder structure

```
WST262_SS3_WesaniBaloyi/
├── app.py                  Flask back end: page routes, form handling, /api/courses, admin
├── database.py             SQLite setup (testimonials, contact messages, enrollments)
├── server.js               Node.js / Express API: /api/feedback, /api/courses
├── package.json            Node.js dependencies and the "npm start" script
├── course-data.json        Course data (title, description, lecturer, capacity, ...)
├── feedback.json           Learner feedback saved by the Node.js API
├── cyber_education.db      SQLite database (created automatically)
├── Java.js                 Shared front-end script (scroll animations)
├── Testimonial.js          Testimonials carousel and character counter
├── templates/              Jinja HTML templates (front end)
│   ├── base.html           Shared layout: Bootstrap navbar, footer, scripts
│   ├── Index.html          Home
│   ├── About.html          About us
│   ├── Course.html         Courses (cards and filters)
│   ├── CourseDetail.html   One course: hero and tabs
│   ├── Contact.html        Contact us
│   ├── Compare.html, Quiz.html, Testimonials.html, Faq.html, Enroll.html, Error.html
│   └── admin/              Admin login and dashboard
├── static/
│   ├── Style.css           Site styles (loaded after Bootstrap)
│   └── Pictures/           Images
├── mockups/                Design mockups for suggested future features
└── Video presentation/     Project video
```

### How the front end and back end communicate

```
Browser ──(page requests, form POST)──────► Flask (app.py, port 5000) ──► SQLite
Browser ──(fetch GET /api/courses)────────► Flask ──► course-data.json + SQLite
Any client ──(GET /api/courses)──────────► Node.js / Express (server.js, port 3000) ──► course-data.json
Any client ──(GET/POST /api/feedback)────► Node.js / Express (server.js, port 3000) ──► feedback.json
```

### Editing courses

Courses live in `course-data.json`. Each course has `image`, `title`, `description`, `duration`, `modeOfDelivery`, `lecturer`, `prerequisite`, `courseOutline` and `capacity`, and optionally `"featured": true` and `"badge"`. Start dates are worked out automatically (the next four quarter starts). To show more or fewer, change `INTAKES_SHOWN` in `app.py`.

## 6. Credits

- **Developer:** Wesani Baloyi
- [Bootstrap 5](https://getbootstrap.com/) (MIT licence): layout, components and validation styles
- [Flask](https://flask.palletsprojects.com/) (BSD licence): Python web framework
- [Express](https://expressjs.com/) (MIT licence): Node.js web framework
- [Google Fonts](https://fonts.google.com/): Plus Jakarta Sans and DM Serif Display (SIL Open Font Licence)
- Course and stock images in `static/Pictures/`

## Feature ideas

Suggested next features, each with three design mockups, are in [`mockups/`](mockups/index.html). Open `mockups/index.html` in a browser.
