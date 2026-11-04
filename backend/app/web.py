"""The public website: server-rendered pages built from the real curriculum, plus sitemap, robots.txt and llms.txt.

Search engines (SEO), answer engines (AEO) and AI assistants (GEO) read these pages, so each page is plain HTML that
states its answer first, has one H1, a canonical URL, Open Graph tags and schema.org JSON-LD that matches what is on the page.
The interactive app lives under /app/ and is kept out of search results.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from . import __version__
from .config import settings
from .content import BOARDS, SUBJECTS, Curriculum, get_curriculum

HERE = Path(__file__).resolve().parent
env = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape(["html"]))
env.filters["tojson_ld"] = lambda o: Markup(json.dumps(o, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))
router = APIRouter(include_in_schema=False)

BOARD_SLUG = {"CBSE": "cbse", "ICSE": "icse", "TELANGANA": "telangana"}
SLUG_BOARD = {v: k for k, v in BOARD_SLUG.items()}
SITE_NAME = "Sahayak"

FAQ = [
    ("What is Sahayak?",
     "Sahayak is a free adaptive learning web app for students in Classes 6 to 10. It covers Maths and Science for CBSE (NCERT), ICSE and the Telangana State Board. It reads which mistake a student made, follows it back through earlier topics, and practises that gap."),
    ("Which classes, subjects and boards does it cover?",
     "Classes 6 to 10, Maths and Science, for CBSE (NCERT), ICSE and the Telangana State Board. All three boards share one prerequisite graph of topics, and each board has its own chapter list."),
    ("How does Sahayak find what a student is missing?",
     "Every wrong answer option is written to match one specific misunderstanding, and some point to an earlier topic. When a student picks one, Sahayak moves to that earlier topic, practises it until the student is steady, and then returns to the original chapter. The estimate for each topic uses Bayesian knowledge tracing."),
    ("Does it work without internet?",
     "Yes, after the first visit. The syllabus and questions are stored on the phone, and the same engine runs there. Answers are saved on the phone and sent to the server when the phone is next online. The first visit needs a connection, and teachers and parents need a connection to sign in."),
    ("Is Sahayak free?",
     "Yes. There is no charge, no advertising and no tracking script."),
    ("How does a student join a school?",
     "The teacher creates a school account and gets a school code. The student types that code when creating a profile, or later from the home screen. The student then appears on that teacher's dashboard. Students who skip the code can still study on their own."),
    ("What does a teacher see?",
     "A heatmap of the class by chapter and topic, groups to teach next (extend, practise, basics), a morning briefing, worksheets built from the class's gaps, and a test-readiness column for the test the teacher sets. A teacher sees only students who joined with their school's code."),
    ("What does a parent see?",
     "A plain note about their own child in English, Hindi or Telugu, the test date, and minutes practised each day. No marks, no rank, and no other child. The parent links a child with the family code on the child's screen, and the child can remove access at any time."),
    ("What data does Sahayak collect?",
     "Students: first name, board, class, language, a hashed PIN, answers and study time. Teachers and parents: name, email and a hashed password. The contact form stores the message. Sahayak does not collect phone numbers, location or photos. See the privacy page for the full list."),
    ("Does Sahayak replace a teacher?",
     "No. It finds gaps and gives practice. The teacher decides what to teach, sets the test and moves students between groups. Teachers should read the questions and lessons before using them with a class."),
    ("How were the questions made and checked?",
     "Each topic has at least six multiple-choice questions at three levels, written for this project, with every wrong option tagged with the mistake it represents. An automated check confirms every question has exactly one right answer and that every tagged earlier topic really is a prerequisite. A teacher should still review them, and Hindi and Telugu text is a draft."),
    ("Which languages does it support?",
     "The app and topic names work in English, Hindi and Telugu, and parent notes are in all three. The questions themselves are in English."),
]


def site(request: Request) -> str:
    return settings.site_url or str(request.base_url).rstrip("/")


def cur() -> Curriculum:
    return get_curriculum()


def nice(s: str) -> str:
    return s


def render(request: Request, template: str, *, title: str, description: str, path: str, jsonld: list | None = None,
           status: int = 200, noindex: bool = False, **ctx) -> HTMLResponse:
    c = cur()
    base = site(request)
    html = env.get_template(template).render(
        site=base, title=title, description=description, path=path, jsonld=jsonld or [], noindex=noindex,
        asset_v=__version__, n_topics=len(c.T), n_questions=c.n_questions, contact_email=settings.contact_email,
        subjects=SUBJECTS, faq=FAQ, **ctx)
    hdr = {"Cache-Control": "public, max-age=300"} if status == 200 else {}
    return HTMLResponse(html, status_code=status, headers=hdr)


def crumbs_ld(base: str, items: list[tuple[str, str]]) -> dict:
    return {"@context": "https://schema.org", "@type": "BreadcrumbList",
            "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": n, "item": base + p} for i, (n, p) in enumerate(items)]}


def org_ld(base: str) -> list[dict]:
    return [
        {"@context": "https://schema.org", "@type": "Organization", "name": SITE_NAME, "url": base + "/",
         "logo": base + "/app/icon.svg", "sameAs": ["https://github.com/VarunKaushik-2104/Sahayak"]},
        {"@context": "https://schema.org", "@type": "WebSite", "name": SITE_NAME, "url": base + "/", "inLanguage": ["en", "hi", "te"]},
        {"@context": "https://schema.org", "@type": "WebApplication", "name": SITE_NAME, "url": base + "/app/",
         "applicationCategory": "EducationalApplication", "operatingSystem": "Any (web browser, installable)",
         "browserRequirements": "Requires JavaScript", "inLanguage": ["en", "hi", "te"], "isAccessibleForFree": True,
         "offers": {"@type": "Offer", "price": "0", "priceCurrency": "INR"},
         "audience": {"@type": "EducationalAudience", "educationalRole": "student", "audienceType": "Classes 6 to 10"},
         "description": "Adaptive practice for Classes 6 to 10 Maths and Science that traces mistakes back to earlier topics. Works offline."},
    ]


def faq_ld(items) -> dict:
    return {"@context": "https://schema.org", "@type": "FAQPage",
            "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in items]}


def topic_ref(c: Curriculum, tid: str) -> dict:
    t = c.T[tid]
    return {"id": tid, "name": t["name"], "cls": t["cls"], "sub": t["sub"]}


def trace_example(c: Curriculum) -> dict:
    """A real item from the question bank for the home page: a wrong option that points to an earlier topic."""
    for tid in ("m10_quad", "m9_poly", "m8_alg"):
        t = c.T.get(tid)
        for q in (t or {}).get("qs", []):
            wrong = next((o for o in q["o"] if o.get("g") and not o.get("ok")), None)
            if wrong:
                g = c.T[wrong["g"]]
                return {"topic": t["name"], "cls": t["cls"], "q": q["q"], "right": next(o["t"] for o in q["o"] if o.get("ok")),
                        "wrong": wrong["t"], "misconception": wrong["m"], "gap": g["name"], "gap_cls": g["cls"]}
    raise RuntimeError("no traceable question found")


# ---------------------------------------------------------------------------------------------------- pages
@router.get("/")
def home(request: Request):
    base = site(request)
    return render(request, "home.html", path="/", ex=trace_example(cur()),
                  title="Sahayak: adaptive learning for Classes 6 to 10, Maths and Science",
                  description="Free adaptive practice for Classes 6 to 10 (CBSE, ICSE, Telangana). Sahayak traces a wrong answer back to the earlier topic behind it, works offline, and gives teachers and parents a clear view.",
                  jsonld=org_ld(base))


@router.get("/how-it-works")
def how(request: Request):
    base, c = site(request), cur()
    per = min(len(t["qs"]) for t in c.T.values())
    return render(request, "how.html", path="/how-it-works", per_topic=per,
                  title="How Sahayak finds a student's learning gaps",
                  description="A prerequisite map of topics, questions written around specific mistakes, and a mastery estimate that traces a wrong answer back to the earlier topic behind it.",
                  og_type="article",
                  jsonld=[{"@context": "https://schema.org", "@type": "TechArticle", "headline": "How Sahayak finds a student's learning gaps",
                           "url": base + "/how-it-works", "inLanguage": "en", "about": "Adaptive learning, knowledge tracing, prerequisite concept graph",
                           "author": {"@type": "Organization", "name": "Team WIN R"}, "publisher": {"@type": "Organization", "name": SITE_NAME}},
                          crumbs_ld(base, [("Home", "/"), ("How it works", "/how-it-works")])])


@router.get("/curriculum")
def curriculum_index(request: Request):
    base, c = site(request), cur()
    boards = [{"slug": BOARD_SLUG[b], "label": c.B[b]["label"],
               "counts": {n: {s: len(c.chapters(b, n, s)) for s in SUBJECTS} for n in range(6, 11)}} for b in BOARDS]
    return render(request, "curriculum.html", path="/curriculum", boards=boards,
                  title="Syllabus: Classes 6 to 10 Maths and Science chapters for CBSE, ICSE and Telangana",
                  description=f"Chapter lists for CBSE (NCERT), ICSE and Telangana State Board, Classes 6 to 10, Maths and Science, mapped to {len(c.T)} prerequisite-linked topics.",
                  jsonld=[crumbs_ld(base, [("Home", "/"), ("Syllabus", "/curriculum")])])


@router.get("/curriculum/{board}/class-{cls}/{subject}")
def class_page(request: Request, board: str, cls: int, subject: str):
    b, s, c = SLUG_BOARD.get(board), subject.capitalize(), cur()
    if not b or s not in SUBJECTS or not 6 <= cls <= 10:
        raise HTTPException(404)
    base = site(request)
    chs = [{"name": ch["name"], "topics": [{**topic_ref(c, t)} for t in ch["topics"]]} for ch in c.chapters(b, cls, s)]
    label = c.B[b]["label"]
    path = f"/curriculum/{board}/class-{cls}/{subject.lower()}"
    ld = {"@context": "https://schema.org", "@type": "ItemList", "name": f"{label} Class {cls} {s} chapters",
          "numberOfItems": len(chs), "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": ch["name"]} for i, ch in enumerate(chs)]}
    return render(request, "classpage.html", path=path, board={"slug": board, "label": label}, cls=cls, subject=s,
                  other_subject=[x for x in SUBJECTS if x != s][0], chapters=chs,
                  title=f"{label} Class {cls} {s}: all {len(chs)} chapters and topics",
                  description=f"Chapters of {label} Class {cls} {s}: " + ", ".join(ch["name"] for ch in chs[:6]) + (", and more." if len(chs) > 6 else "."),
                  jsonld=[ld, crumbs_ld(base, [("Home", "/"), ("Syllabus", "/curriculum"), (f"{label} Class {cls} {s}", path)])])


@router.get("/topics")
def topics_index(request: Request):
    base, c = site(request), cur()
    groups = {s: {n: [topic_ref(c, k) for k in c.class_topics(n, s)] for n in range(6, 11)} for s in SUBJECTS}
    return render(request, "topics.html", path="/topics", groups=groups,
                  title=f"All {len(c.T)} Maths and Science topics for Classes 6 to 10",
                  description="Every topic in Sahayak's prerequisite graph, by subject and class, with what each builds on and the mistakes students commonly make.",
                  jsonld=[crumbs_ld(base, [("Home", "/"), ("Topics", "/topics")])])


def _used_in(c: Curriculum, tid: str) -> list[dict]:
    out = []
    for b in BOARDS:
        for n in range(6, 11):
            for s in SUBJECTS:
                for ch in c.chapters(b, n, s):
                    if tid in ch["topics"]:
                        out.append({"board": c.B[b]["label"], "cls": n, "chapter": ch["name"], "url": f"/curriculum/{BOARD_SLUG[b]}/class-{n}/{s.lower()}"})
    return out


@router.get("/topics/{tid}")
def topic_page(request: Request, tid: str):
    c = cur()
    t = c.T.get(tid)
    if not t:
        raise HTTPException(404)
    base = site(request)
    lesson = t.get("lesson") or {"points": []}
    pre = [topic_ref(c, p) for p in t["pre"]]
    nxt = [topic_ref(c, k) for k, v in c.T.items() if tid in v["pre"]]
    mistakes = list(dict.fromkeys(o["m"] for q in t["qs"] for o in q["o"] if o.get("m")))[:8]
    q = next((x for x in t["qs"] if x["lvl"] == 2), t["qs"][0])
    sample = {"q": q["q"], "o": q["o"], "right": next(o["t"] for o in q["o"] if o.get("ok")), "why": q["why"]}
    summary = lesson["points"][0] if lesson["points"] else t["name"]
    path = f"/topics/{tid}"
    qa = [(f"What is {t['name'].lower()}?", summary)]
    qa.append((f"What should I know before learning {t['name'].lower()}?",
               ("Know " + ", ".join(f"{p['name']} (Class {p['cls']})" for p in pre) + ".") if pre else "It is a starting point; no earlier topic is needed."))
    jsonld = [{"@context": "https://schema.org", "@type": "LearningResource", "name": t["name"], "url": base + path, "inLanguage": "en",
               "educationalLevel": f"Class {t['cls']}", "learningResourceType": "Lesson and practice questions", "teaches": t["name"],
               "about": t["sub"], "isAccessibleForFree": True,
               "competencyRequired": [p["name"] for p in pre], "description": summary,
               "provider": {"@type": "Organization", "name": SITE_NAME}},
              faq_ld(qa), crumbs_ld(base, [("Home", "/"), ("Topics", "/topics"), (t["name"], path)])]
    return render(request, "topic.html", path=path, t=t, lesson=lesson, pre=pre, nxt=nxt, mistakes=mistakes, sample=sample,
                  summary=summary, chapters=_used_in(c, tid),
                  title=f"{t['name']}, Class {t['cls']} {t['sub']}: key ideas, example and common mistakes",
                  description=(summary[:150] + ("…" if len(summary) > 150 else "")) + f" Class {t['cls']} {t['sub']} with prerequisites and practice.",
                  jsonld=jsonld)


@router.get("/for-teachers")
def teachers(request: Request):
    base = site(request)
    return render(request, "teachers.html", path="/for-teachers",
                  title="Sahayak for teachers: class heatmap, groups and worksheets",
                  description="See which students are ready for your test and which basics are missing. Create a school, share a code, and students appear on your dashboard.",
                  jsonld=[crumbs_ld(base, [("Home", "/"), ("For teachers", "/for-teachers")])])


@router.get("/for-parents")
def parents(request: Request):
    base = site(request)
    return render(request, "parents.html", path="/for-parents",
                  title="Sahayak for parents: a plain weekly note in English, Hindi or Telugu",
                  description="A short note about your own child's preparation, the test date and practice minutes. No marks, no rank, no other children.",
                  jsonld=[crumbs_ld(base, [("Home", "/"), ("For parents", "/for-parents")])])


@router.get("/faq")
def faq(request: Request):
    base = site(request)
    return render(request, "faq.html", path="/faq", title="Sahayak questions and answers",
                  description="What Sahayak is, how it finds learning gaps, whether it works offline, what teachers and parents see, and what data it keeps.",
                  jsonld=[faq_ld(FAQ), crumbs_ld(base, [("Home", "/"), ("FAQ", "/faq")])])


@router.get("/about")
def about(request: Request):
    base = site(request)
    return render(request, "about.html", path="/about", title="About Sahayak: what is built and what is not yet proven",
                  description="Sahayak is built by Team WIN R for the Adaptive Learning for Classes 6 to 10 challenge. What the project includes and its honest limits.",
                  jsonld=[crumbs_ld(base, [("Home", "/"), ("About", "/about")])])


@router.get("/privacy")
def privacy(request: Request):
    base = site(request)
    return render(request, "privacy.html", path="/privacy", title="Sahayak privacy and data: what is stored and who sees it",
                  description="Exactly what Sahayak stores about students, teachers and parents, where it lives, who can see it, and how to delete it.",
                  jsonld=[crumbs_ld(base, [("Home", "/"), ("Privacy and data", "/privacy")])])


@router.get("/contact")
def contact(request: Request):
    base = site(request)
    return render(request, "contact.html", path="/contact", title="Contact Sahayak",
                  description="Send a question, a correction to a chapter or question, or ask about a trial in your school.",
                  jsonld=[{"@context": "https://schema.org", "@type": "ContactPage", "name": "Contact Sahayak", "url": base + "/contact"},
                          crumbs_ld(base, [("Home", "/"), ("Contact", "/contact")])])


# ------------------------------------------------------------------------------------- crawlers and machines
def all_paths() -> list[str]:
    c = cur()
    p = ["/", "/how-it-works", "/curriculum", "/topics", "/for-teachers", "/for-parents", "/faq", "/about", "/privacy", "/contact"]
    p += [f"/curriculum/{BOARD_SLUG[b]}/class-{n}/{s.lower()}" for b in BOARDS for n in range(6, 11) for s in SUBJECTS]
    p += [f"/topics/{k}" for k in c.T]
    return p


@router.get("/sitemap.xml")
def sitemap(request: Request):
    base, today = site(request), date.today().isoformat()
    rows = "".join(f"<url><loc>{base}{p}</loc><lastmod>{today}</lastmod></url>" for p in all_paths())
    xml = f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{rows}</urlset>'
    return Response(xml, media_type="application/xml", headers={"Cache-Control": "public, max-age=3600"})


AI_BOTS = ["GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-SearchBot", "Claude-User", "PerplexityBot",
           "Google-Extended", "Applebot-Extended", "Bingbot"]


@router.get("/robots.txt")
def robots(request: Request):
    base = site(request)
    lines = ["# Sahayak is open to search engines and AI assistants. The signed-in app and the API are not for crawling.",
             "User-agent: *", "Allow: /", "Disallow: /api/", "Disallow: /app/", ""]
    for b in AI_BOTS:
        lines += [f"User-agent: {b}", "Allow: /", "Disallow: /api/", "Disallow: /app/", ""]
    lines += [f"Sitemap: {base}/sitemap.xml", f"# Machine-readable summary: {base}/llms.txt"]
    return PlainTextResponse("\n".join(lines) + "\n", headers={"Cache-Control": "public, max-age=3600"})


@router.get("/llms.txt")
def llms(request: Request):
    base, c = site(request), cur()
    body = f"""# Sahayak

> Sahayak is a free adaptive learning web app for students in Classes 6 to 10 in India. It covers Maths and Science for CBSE (NCERT), ICSE and the Telangana State Board. It traces a wrong answer back to the earlier topic behind it, works offline, and gives teachers a class heatmap and parents a plain note about their own child. It has {len(c.T)} topics and {c.n_questions} questions. Built by Team WIN R. Source: https://github.com/VarunKaushik-2104/Sahayak

## Key pages
- [How it works]({base}/how-it-works): prerequisite map, questions written around mistakes, mastery estimate, tracing back
- [Syllabus]({base}/curriculum): chapter lists by board, class and subject
- [All topics]({base}/topics): every topic with prerequisites, key ideas, worked example and common mistakes
- [For teachers]({base}/for-teachers): class heatmap, groups, briefing, worksheets
- [For parents]({base}/for-parents): weekly note in English, Hindi or Telugu
- [FAQ]({base}/faq): short answers
- [Privacy and data]({base}/privacy): exactly what is stored and who sees it
- [About]({base}/about): what is built and what is not yet proven
- [Full text of all topics]({base}/llms-full.txt)

## Facts
- Boards: CBSE (NCERT), ICSE, Telangana State Board. Classes 6 to 10. Subjects: Maths, Science.
- Free, no advertising, no tracking scripts. App: {base}/app/
- Limits: mastery model uses default parameters not yet fitted to classroom data; Hindi and Telugu text is a draft; chapter names need a teacher's check each year.
"""
    return PlainTextResponse(body, media_type="text/plain; charset=utf-8", headers={"Cache-Control": "public, max-age=3600"})


@router.get("/llms-full.txt")
def llms_full(request: Request):
    base, c = site(request), cur()
    out = [f"# Sahayak: all topics ({len(c.T)})\n", f"Site: {base}\n"]
    for s in SUBJECTS:
        for n in range(6, 11):
            for k in c.class_topics(n, s):
                t = c.T[k]
                pre = ", ".join(f"{c.T[p]['name']} (Class {c.T[p]['cls']})" for p in t["pre"]) or "none"
                out.append(f"## {t['name']} (Class {n} {s})\nURL: {base}/topics/{k}\nPrerequisites: {pre}")
                for p in (t.get("lesson") or {}).get("points", []):
                    out.append(f"- {p}")
                mist = list(dict.fromkeys(o["m"] for q in t["qs"] for o in q["o"] if o.get("m")))[:6]
                if mist:
                    out.append("Common mistakes: " + "; ".join(mist) + ".")
                out.append("")
    return PlainTextResponse("\n".join(out), media_type="text/plain; charset=utf-8", headers={"Cache-Control": "public, max-age=3600"})


_SW_CLEANUP = """/* The app moved from / to /app/. This worker removes the old one and its caches so the new home page shows. */
self.addEventListener('install',()=>self.skipWaiting());
self.addEventListener('activate',e=>e.waitUntil((async()=>{
  for(const k of await caches.keys())await caches.delete(k);
  await self.registration.unregister();
  for(const c of await self.clients.matchAll({type:'window'}))c.navigate(c.url);
})()));
"""


@router.get("/sw.js")
def old_service_worker():
    return Response(_SW_CLEANUP, media_type="application/javascript", headers={"Cache-Control": "no-cache"})


def not_found_page(request: Request) -> HTMLResponse:
    return render(request, "notfound.html", path=request.url.path, title="Page not found | Sahayak", description="This page does not exist.",
                  status=404, noindex=True)
