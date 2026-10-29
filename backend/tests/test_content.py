from app.content import BOARDS, SUBJECTS


def test_every_board_class_subject_has_chapters(cur):
    for b in BOARDS:
        for c in (6, 7, 8, 9, 10):
            for s in SUBJECTS:
                chs = cur.chapters(b, c, s)
                assert chs, (b, c, s)
                for ch in chs:
                    assert ch["topics"], (b, c, s, ch["name"])


def test_every_topic_has_a_lesson_levels_and_translations(cur):
    for tid, t in cur.T.items():
        assert t["lesson"]["points"] and t["lesson"]["story"] and t["lesson"]["example"]["steps"], tid
        assert {q["lvl"] for q in t["qs"]} >= {1, 2, 3}, tid
        assert t["te"] and t["hi"], tid


def test_maths_step_questions_have_three_parts(cur):
    steps = [t["steps"] for t in cur.T.values() if t.get("steps")]
    assert len(steps) >= 20
    for st in steps:
        assert len(st["parts"]) == 3
        for p in st["parts"]:
            assert sum(1 for o in p["o"] if o.get("ok")) == 1


def test_bundle_version_is_stable(cur):
    from app.content import Curriculum
    from app.config import settings
    assert Curriculum.load(settings.curriculum_path).version == cur.version
