# Sahayak content spec

Topics are listed in /tmp/claude-0/-home-claude/f8bb6f52-0b56-5b6e-b8bb-28bd236a4d28/scratchpad/s2/skeleton.json
(id, subject, class, name, prereqs). Prereq ids can belong to earlier classes.

## Content file (one per subject+class), JSON, UTF-8
Write to content/<M|S><class>.json, as an object keyed by topic id:

{
 "m7_eq": {
  "lesson": {
    "title": "Keeping the balance",              // short, plain
    "points": ["2-4 short sentences, language a Class N student can read", "..."],
    "story": "One everyday Indian-context analogy (market, cricket, roti, bus, kirana, festival...) in 1-3 sentences",
    "example": {"q": "worked problem or worked case", "steps": ["step 1", "step 2", "step 3"]}
  },
  "questions": [
    {"lvl":1, "q":"...", "why":"1-2 sentence explanation of the right answer",
     "o":[
       {"t":"right answer","ok":1},
       {"t":"wrong 1","m":"the specific misconception that leads to this answer, written as a short past-tense description of what the student did wrongly","g":"<optional prereq topic id the misconception points back to>"},
       {"t":"wrong 2","m":"..."},
       {"t":"wrong 3","m":"..."}
     ]}
  ]
 }
}

Rules for questions:
- Exactly 8 per topic: lvl 1 (x2, recall / direct), lvl 2 (x3, one step of reasoning), lvl 3 (x3, multi-step or application).
- Exactly 4 options, exactly one with "ok":1. Every wrong option MUST have "m" (a real, specific misconception, not "wrong answer"). Use "g" only when the misconception genuinely comes from a weak prerequisite and the id is in that topic's prereq list (or the topic's own id is NOT allowed as g).
- Options must be distinct, plausible, and similar in length. Do not put the right answer in the same position every time.
- Plain text only. Maths: use unicode (², ³, √, ×, ÷, −, π, ≤, ≥, θ, °, fractions like 3/4). No LaTeX, no markdown, no emojis.
- No question that needs a figure/diagram. Describe the situation in words instead.
- Questions must be correct. Compute every answer twice. Science facts must match standard NCERT / state-board textbooks. If unsure of a fact, choose a different question. Never invent data.
- Use Indian contexts (rupees, km, kg, litres, Indian names/places) where natural.
- Level should match the class: ages 11-16.

Maths topics ALSO get "steps": ONE three-mark structured question:
 "steps": {"q":"Solve ... Show your steps.", "parts":[
   {"label":"Method","prompt":"What is the first step?","o":[{"t":"...","ok":1},{"t":"...","m":"..."},{"t":"...","m":"..."}]},
   {"label":"Working","prompt":"...","o":[3 options, one ok]},
   {"label":"Answer","prompt":"...","o":[3 options, one ok]}]}
 3 options each, exactly one ok, wrong ones have "m".
Science topics get "steps" = null.

Also add a "tags" field per topic: {"te": "<topic name in Telugu>", "hi": "<topic name in Hindi>"}  (name only; use standard textbook terminology).

Output must be valid JSON. After writing, validate it by running python3 -c "import json;json.load(open(path))" and a quick script that checks the counts and the one-ok rule.
