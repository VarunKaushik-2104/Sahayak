"""The weekly parent note in English, Hindi and Telugu.

Plain language, test date included. No marks, no rank, no other child's name.
Hindi and Telugu text is a draft that needs a native speaker's review before real use.
"""
from __future__ import annotations

from datetime import date

from ..content import Curriculum
from .mastery import get, mean

LANGS = ("en", "hi", "te")
MON_HI = ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"]
MON_TE = ["జనవరి", "ఫిబ్రవరి", "మార్చి", "ఏప్రిల్", "మే", "జూన్", "జులై", "ఆగస్టు", "సెప్టెంబర్", "అక్టోబర్", "నవంబర్", "డిసెంబర్"]
WD = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MON_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def fmt_date(d: date) -> str:
    return f"{WD[d.weekday()]} {d.day} {MON_EN[d.month - 1]}"


def plural(n: int, one: str, many: str) -> str:
    return one if n == 1 else many


def build_note(cur: Curriculum, *, name: str, subject: str, lang: str, P: dict[str, float], misc: dict[str, int],
               minutes_last7: list[int], test: dict | None, today: date) -> dict:
    if lang not in LANGS:
        raise ValueError("lang must be one of en, hi, te")
    T = cur.T
    days = sum(1 for m in minutes_last7 if m > 0)
    total = sum(minutes_last7)
    ts = test["topics"] if test else []
    known = sorted((t for t in P if T[t]["sub"] == subject), key=lambda t: -P[t])
    pool = ts or known
    best = known[0] if known else (ts[0] if ts else next(iter(T)))
    weakest = sorted(ts or known, key=lambda t: get(P, t))[0] if (ts or known) else best
    pre = sorted(cur.all_pre(weakest), key=lambda t: get(P, t))
    working = pre[0] if pre and get(P, pre[0]) < 0.55 else weakest
    slip = max(misc.items(), key=lambda kv: kv[1])[0] if misc else None
    ready = round(mean(get(P, t) for t in ts) * 100) if ts else None

    test_line = ""
    tdays = None
    if test:
        td = date.fromisoformat(test["date"])
        tdays = (td - today).days
        if tdays > 0:
            chl = ", ".join(test["chapters"])
            test_line = {
                "en": f"{test['name']} on {fmt_date(td)}, in {tdays} {plural(tdays, 'day', 'days')} ({chl}). {name} is about {ready}% ready. "
                      f"Two short sessions this week on {T[weakest]['name']} will help most.",
                "hi": f"{td.day} {MON_HI[td.month - 1]} को परीक्षा है, {tdays} दिन बाकी। {name} की तैयारी अभी लगभग {ready}% है। "
                      f"इस हफ़्ते {T[weakest]['hi']} पर दो छोटे सत्र सबसे ज़्यादा मदद करेंगे।",
                "te": f"పరీక్ష {MON_TE[td.month - 1]} {td.day}న ఉంది, {tdays} రోజులు మిగిలి ఉన్నాయి. {name} సిద్ధత ఇప్పుడు సుమారు {ready}%. "
                      f"ఈ వారం {T[weakest]['te']}పై రెండు చిన్న సెషన్లు చాలా ఉపయోగపడతాయి.",
            }[lang]

    text = {
        "en": f"Hello! This week {name} practised {subject} on {days} {plural(days, 'day', 'days')}, about {total} minutes in total. "
              f"Strongest topic: {T[best]['name']}. Now working on: {T[working]['name']}. "
              f"{f'One habit being fixed: {slip.lower()}. ' if slip else ''}{test_line} "
              f"Tonight, 10 minutes on the family phone is enough. Ask {name} to explain one answer out loud.",
        "hi": f"नमस्ते! इस हफ़्ते {name} ने {days} दिन अभ्यास किया, कुल लगभग {total} मिनट। सबसे मज़बूत विषय: {T[best]['hi']}। "
              f"अभी इस पर काम चल रहा है: {T[working]['hi']}। {test_line} आज रात परिवार के फ़ोन पर 10 मिनट काफ़ी हैं। "
              f"उनसे एक उत्तर ज़ोर से समझाने को कहें।",
        "te": f"నమస్కారం! ఈ వారం {name} {days} రోజులు సాధన చేశారు, మొత్తం సుమారు {total} నిమిషాలు. బాగా చేసిన అంశం: {T[best]['te']}. "
              f"ఇప్పుడు చేస్తున్నది: {T[working]['te']}. {test_line} ఈ రాత్రి కుటుంబ ఫోన్‌లో 10 నిమిషాలు చాలు. "
              f"ఒక సమాధానాన్ని గట్టిగా వివరించమని అడగండి.",
    }[lang]
    return {
        "lang": lang, "text": " ".join(text.split()), "days_practised": days, "total_minutes": total,
        "strongest": best, "working_on": working, "readiness_pct": ready, "days_to_test": tdays,
        "draft_translation": lang != "en",
    }
