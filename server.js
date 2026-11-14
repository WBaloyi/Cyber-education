// Cyber Education: Node.js / Express API
//
// Runs next to the Flask app (app.py). The About page calls this server from the browser to
// show and submit learner feedback, which is stored in feedback.json.
//
//   GET  /api/feedback   -> list of feedback (newest first)
//   POST /api/feedback   -> add feedback { name, topic, message }
//   GET  /api/courses    -> course list read from course-data.json
//   GET  /api/health     -> { status: "ok" }
//
// Start with:  npm start   (http://localhost:3000)

const express = require('express');
const path = require('path');
const fs = require('fs');

const app = express();
const port = process.env.PORT || 3000;
const feedbackFile = path.join(__dirname, 'feedback.json');
const coursesFile = path.join(__dirname, 'course-data.json');

// Pages served by Flask that are allowed to call this API from the browser (CORS).
const allowedOrigins = (process.env.ALLOWED_ORIGINS || 'http://127.0.0.1:5000,http://localhost:5000')
    .split(',')
    .map(origin => origin.trim());

const TOPICS = ['Course suggestion', 'Learning experience', 'Website', 'Other'];
const LIMITS = { name: 60, message: 400 };
const MAX_STORED = 500;

app.use(express.json({ limit: '10kb' }));

app.use((req, res, next) => {
    const origin = req.get('Origin');
    if (origin && allowedOrigins.includes(origin)) {
        res.set('Access-Control-Allow-Origin', origin);
        res.set('Vary', 'Origin');
        res.set('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
        res.set('Access-Control-Allow-Headers', 'Content-Type');
    }
    res.set('X-Content-Type-Options', 'nosniff');
    if (req.method === 'OPTIONS') return res.sendStatus(204);
    return next();
});

// ---------- JSON file helpers ----------

const readJsonArray = file => {
    if (!fs.existsSync(file)) return [];
    const data = JSON.parse(fs.readFileSync(file, 'utf8'));
    if (!Array.isArray(data)) throw new TypeError(`${path.basename(file)} must contain a JSON array.`);
    return data;
};

const writeJsonArray = (file, data) => {
    // Write to a temporary file first so a crash can't leave half-written JSON behind.
    const temp = `${file}.tmp`;
    fs.writeFileSync(temp, JSON.stringify(data, null, 2), 'utf8');
    fs.renameSync(temp, file);
};

// ---------- Simple rate limit for submissions (per IP address) ----------

const recentPosts = new Map();
const RATE_LIMIT = { max: 5, windowMs: 10 * 60 * 1000 };

const isRateLimited = ip => {
    const now = Date.now();
    const times = (recentPosts.get(ip) || []).filter(time => now - time < RATE_LIMIT.windowMs);
    if (times.length >= RATE_LIMIT.max) {
        recentPosts.set(ip, times);
        return true;
    }
    times.push(now);
    recentPosts.set(ip, times);
    return false;
};

// ---------- Routes ----------

app.get('/', (req, res) => {
    res.json({
        name: 'Cyber Education API (Node.js)',
        routes: ['GET /api/health', 'GET /api/courses', 'GET /api/feedback', 'POST /api/feedback'],
    });
});

app.get('/api/health', (req, res) => res.json({ status: 'ok' }));

// "Course duration: 12 weeks" -> "12 weeks"
const afterLabel = text => (typeof text === 'string' && text.includes(':') ? text.split(':').slice(1).join(':').trim() : text || '');
// "Web development" -> "web-development" (same rule as slugify() in app.py, so links match the Flask pages)
const slugify = text => String(text).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');

// Used by the "Our courses at a glance" strip on the About page.
app.get('/api/courses', (req, res, next) => {
    try {
        const courses = readJsonArray(coursesFile).map(course => ({
            slug: slugify(course.title),
            title: course.title,
            description: course.description,
            duration: afterLabel(course.duration),
            delivery: /self/i.test(course.modeOfDelivery || '') ? 'Self-paced' : 'Instructor-paced',
            lecturer: afterLabel(course.lecturer),
            image: course.image,
            featured: Boolean(course.featured),
        }));
        return res.json(courses);
    } catch (error) {
        return next(error);
    }
});

app.get('/api/feedback', (req, res, next) => {
    try {
        const feedback = readJsonArray(feedbackFile);
        return res.json(feedback.slice().reverse());
    } catch (error) {
        return next(error);
    }
});

app.post('/api/feedback', (req, res, next) => {
    const body = req.body && typeof req.body === 'object' ? req.body : {};
    if (body.website) return res.status(201).json({}); // honeypot field, hidden from people

    const name = typeof body.name === 'string' ? body.name.trim() : '';
    const topic = typeof body.topic === 'string' ? body.topic.trim() : '';
    const message = typeof body.message === 'string' ? body.message.trim() : '';

    const errors = {};
    if (name.length < 2 || name.length > LIMITS.name) errors.name = `Please enter a name between 2 and ${LIMITS.name} characters.`;
    if (!TOPICS.includes(topic)) errors.topic = 'Please choose a topic.';
    if (message.length < 10 || message.length > LIMITS.message) errors.message = `Please enter between 10 and ${LIMITS.message} characters.`;
    if (Object.keys(errors).length) return res.status(400).json({ errors });

    if (isRateLimited(req.ip)) {
        return res.status(429).json({ errors: { form: 'You have sent a lot of feedback. Please try again in a few minutes.' } });
    }

    try {
        const feedback = readJsonArray(feedbackFile);
        const entry = { id: Date.now(), name, topic, message, createdAt: new Date().toISOString() };
        feedback.push(entry);
        writeJsonArray(feedbackFile, feedback.slice(-MAX_STORED));
        return res.status(201).json(entry);
    } catch (error) {
        return next(error);
    }
});

app.use((req, res) => res.status(404).json({ error: 'Not found' }));

app.use((error, req, res, next) => {
    if (res.headersSent) return next(error);
    if (error.type === 'entity.parse.failed') return res.status(400).json({ error: 'Invalid JSON.' });
    if (error.type === 'entity.too.large') return res.status(413).json({ error: 'Request is too large.' });
    console.error('Request failed:', error);
    return res.status(500).json({ error: 'The request could not be completed. Please try again later.' });
});

app.listen(port, () => {
    console.log(`Cyber Education API (Node.js) running on http://localhost:${port}`);
    console.log(`Accepting browser requests from: ${allowedOrigins.join(', ')}`);
});
