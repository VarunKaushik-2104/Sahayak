# Technical interview prep (10 minutes on Google Meet)

The organisers will ask: what you built and how it works, why this stack, how data is collected, processed and stored, what challenges you solved, and what makes yours different. They said AI help is fine but **understanding decides the winner**. So: read this, then open the files named below and read them once. If you can explain a file in your own words, you own it.

## 1. The 60-second pitch (say it in your own words)

"Sahayak finds the *reason* behind a wrong answer. Every wrong option in our 584 questions is tagged with the specific mistake it shows, and some point to an earlier topic. When a Class 10 student picks the wrong quadratic-equation option, we do not just mark it wrong: we follow the tag back through a 73-topic prerequisite graph to polynomials in Class 9, practise that, then return. It runs offline on the phone and syncs later, and the server re-marks every answer so nobody can fake mastery. Teachers get a class heatmap and groups; parents get a plain note in English, Hindi or Telugu with no marks or rank. For this round we removed all demo data and built real accounts, school codes, a family code for parents, and a public website with SEO, AEO and GEO."

## 2. Three-minute live demo (share the live site; do this once beforehand)

Before the call: open `/api/health` to wake Render (free tier sleeps), and create your own test accounts so you are not typing during the call. Keep `http://localhost:8000` running as a backup.

1. **Public site** `/`: show the hero (a real question from our data), then `/topics/m10_quad` (prerequisites, common mistakes), then `/sitemap.xml`, `/llms.txt`, view-source for JSON-LD.
2. **Teacher** `/app/` > Teacher > Create account > show the **school code**. Empty dashboard: "nothing is invented".
3. **Student** (second browser or private window) > New profile with the school code > placement check > practise > deliberately pick a tagged wrong answer and show the engine log line tracing back.
4. Toggle **Offline** > answer 2 questions > outbox shows items > **Online** > outbox empties.
5. **Teacher** window: the student appears in the heatmap. Move the test date, send practice to a group.
6. **Parent** > Create account with the student's **family code** > Telugu note.

## 3. Numbers to know cold

| Thing | Value |
|---|---|
| Topics / questions | 73 / 584 (at least 6 per topic, 3 levels) |
| Boards, classes, subjects | CBSE, ICSE, Telangana; 6 to 10; Maths and Science |
| BKT | prior 0.5, slip 0.10, guess 0.22, learn 0.12, damping 0.55, cap 0.98 (`engine/mastery.py`) |
| Level chosen | below 0.4 easy, 0.4 to 0.7 medium, 0.7 and up hard |
| Trace back | follow the tagged prerequisite if its mastery < 0.75; else the weakest prerequisite < 0.6; return at 0.7 (`engine/practice.py`) |
| Practice | up to 8 solve questions, then a 3-question check; placement is 5 questions |
| Lock-outs | 5 wrong PINs or passwords, locked 5 minutes |
| Tests | 72 pytest tests + a browser e2e on an empty database |
| Public URLs | 113 in the sitemap (10 pages + 30 syllabus + 73 topics) |

## 4. How data is collected, processed, stored (they will ask this)

- **Collected:** only what a screen asks for. Student: first name, board, class, language, 4-digit PIN, answers. Teacher/parent: name, email, password. Contact form: message. No phone numbers, location or photos. No analytics, no cookies.
- **On the phone:** the syllabus bundle and the student's profile and outbox live in `localStorage`; the PIN is kept as a salted hash so it can be checked offline.
- **Processed:** the phone computes the next question locally with the same engine (JavaScript). On sync (`POST /api/sync`), the server **ignores the phone's claims of right or wrong**, looks each pick up in its own question bank, re-marks, applies answers in time order to the stored mastery, clamps bad clocks, skips repeated event ids (idempotent), and returns the authoritative mastery.
- **Stored:** SQLAlchemy models in `models.py`: users, schools, attempts, mastery, mock results, misconception counts, study minutes, test plans, group overrides, assignments, parent-child links, feedback. SQLite locally, PostgreSQL on Render.
- **Who sees what:** teachers only their school's students (school code match); parents only linked children and a note with no marks or rank; students only themselves.
- **Deleting:** `DELETE /api/auth/me` removes the user and cascades to their rows.

## 5. Why these choices

- **FastAPI + SQLAlchemy:** typed request models (Pydantic), automatic `/docs`, simple dependency injection for role checks (`deps.py`), same code runs on SQLite and PostgreSQL.
- **Pure-Python engine with no I/O:** testable in isolation; the JavaScript copy is checked against it by a parity test (`tests/test_parity.py` runs the JS engine in Node and compares).
- **Offline-first PWA, no framework:** students have weak connectivity; a build step and a framework add weight and failure modes. Trade-off: `app.js` is long and string-templated.
- **BKT, not an LLM:** deterministic, explainable, free, works offline. An LLM could write explanations later but should not decide mastery.
- **Tagged distractors:** a wrong answer is evidence. This is the core idea and the main difference from a quiz app.
- **Email + password instead of OTP:** an SMS provider needs paid accounts and (in India) DLT registration. Showing the code on screen was a simulation, which the organisers said to avoid, so we removed it. Next step would be email verification and password reset.
- **Server-rendered pages for the public site:** crawlers and AI assistants read HTML; the app is a client-side shell, which is poor for SEO. So the site is Jinja2 pages built from the same curriculum data, and the app is under `/app/` with `noindex`.
- **School code + staff code + family code:** simple, works without email infrastructure, and each code grants exactly one thing (student joins school, teacher joins school, parent follows one child).

## 6. Challenges we hit (true stories to tell)

1. **Forged mastery:** early sync trusted the phone. Fix: phone sends the picked option text; the server marks it. Test: "a forged claim changes nothing".
2. **Offline then back online sessions:** the signing key was random per restart, so every restart signed everyone out. Fix: persisted key / `SECRET_KEY`, silent re-login with the PIN held in memory, offline PIN check with a JS SHA-256 fallback on plain-http phones.
3. **Create-profile bug:** the form was emptied by a re-render before it was read, and validation errors looked like "No connection". Fix: read values first, tag form errors with status 422.
4. **Replayed sync and clocks:** unique client ids per answer, placement answers stored as `<cid>:<n>`, future or two-week-old timestamps clamped.
5. **Students not showing on the teacher heatmap:** self-study students had no school. We first patched it with a "DEMO" school code. In Round 3 we replaced that with real schools: teacher creates one, gets a code, students enter it (or join later).
6. **Demo data vs real data:** removed demo seed from production, and wrote `purge_demo` so the already-deployed database was cleaned on the next start without deleting real users (tested against a database made by the old version).
7. **Moving the app to `/app/`:** the old service worker owned `/`, so we serve a cleanup worker at `/sw.js` that unregisters it and clears caches.

## 7. What makes it different

- Reads *which mistake*, not just right/wrong, and traces across **classes** through a graph shared by three boards.
- Works offline and cannot be gamed (server re-marks).
- Built for the teacher's reality: a test date, a chapter list per board, groups, worksheets.
- Parent note respects the child: no marks, no rank, child can revoke access.
- Honest limits are published on `/about` and in the README.

## 8. Hard questions, and honest answers

- **"Is the mastery model accurate?"** The structure is standard BKT with damping; the parameters are reasonable defaults, **not fitted** to real data, and we have not run a classroom trial. What we did verify: answer keys (blind review), engine behaviour (tests), and JS/Python parity.
- **"Who wrote the questions?"** Written for this project with AI assistance and checked by an independent blind re-solve of all keys plus automated validation (one correct option, tags point to real prerequisites). A teacher should still review. Say this plainly.
- **"Is this just a wrapper over an LLM?"** No. There is no LLM call anywhere. Adaptivity is BKT plus a prerequisite graph.
- **"What happens if two teachers share a school?"** The second uses the staff code at sign-up and sees the same students.
- **"Could a student join the wrong school?"** Only by typing its code; they can leave from the home screen; teachers see only names, class and mastery.
- **"Security?"** PBKDF2-hashed PIN and password, lock-out, identical error for unknown email and wrong password, signed JWT, role checks on every route, school scoping, parent isolation, server re-marking, rate-limited honeypot contact form. Not done: password reset, email verification, CSRF is not needed because we use bearer tokens, not cookies.
- **"What does it do with no internet?"** After one visit, everything student-side works; sign-in for teacher/parent and first-time sign-up need a connection.
- **"Scaling?"** Stateless FastAPI behind Render; all state in PostgreSQL; sync is batched. Known gaps: in-memory rate limits (per process), no migrations tool, free-tier sleep.
- **"What would you do next?"** Fit BKT parameters from real answers, add hints, email verification and reset, Alembic, teacher-approved content review workflow, more subjects.
- **"What did AI write vs you?"** Be truthful and specific: say what you designed (the tagged-distractor idea, the graph, the sync rules, the codes) and be ready to open `engine/mastery.py`, `services/sync.py`, `routers/auth.py` and explain them line by line.

## 9. Files to open once before the call

| File | Be able to say |
|---|---|
| `backend/app/engine/mastery.py` | the BKT formula and why we damp it |
| `backend/app/engine/practice.py` | `mark`, `pick`, trace-back thresholds, check questions |
| `backend/app/services/sync.py` | ordering, idempotency, clock clamping, re-marking |
| `backend/app/routers/auth.py` | the three sign-up paths and lock-out |
| `backend/app/models.py` | the tables and unique constraints (`ux_users_email_role`, `ux_users_link_code`) |
| `backend/app/web.py` | how pages, JSON-LD, sitemap, robots, llms.txt are produced |
| `backend/app/seed.py` | `purge_demo`: why demo data cannot reach production |
| `frontend/js/engine.js` | the offline engine and outbox |
| `backend/tests/test_accounts.py`, `test_site.py` | what the tests prove |

## 10. Checklist for the day

- [ ] Open the live site 2 minutes before the call so Render is awake.
- [ ] Teacher, student and parent test accounts already created; school code and family code written on paper.
- [ ] Localhost backup running (`uvicorn app.main:app` in `backend/`).
- [ ] Flowchart open in a tab; README open at the "What changed in Round 3" section.
- [ ] Whoever answers "challenges" and "data handling" has read sections 4 and 6 aloud once.
