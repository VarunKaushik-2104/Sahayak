"""The public website: crawlable pages, structured data, sitemap, robots, llms.txt."""
import json
import re

import pytest

from app.web import FAQ, all_paths


def ld(html):
    return [json.loads(x) for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]


def test_home_is_server_rendered_with_seo_basics(client):
    r = client.get("/")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    h = r.text
    assert h.count("<h1") == 1 and "Find the gap behind the wrong answer" in h
    assert re.search(r'<title>[^<]{20,70}</title>', h)
    assert '<link rel="canonical" href="' in h and 'property="og:title"' in h and 'name="twitter:card"' in h
    types = {j["@type"] for j in ld(h)}
    assert {"Organization", "WebSite", "WebApplication"} <= types
    assert 'lang="en"' in h and '<a class="skip"' in h


def test_every_public_page_has_one_h1_a_canonical_and_valid_jsonld(client):
    for p in all_paths():
        r = client.get(p)
        assert r.status_code == 200, p
        assert r.text.count("<h1") == 1, p
        assert f'rel="canonical" href="http://testserver{p}"' in r.text, p
        for j in ld(r.text):
            assert j["@context"] == "https://schema.org"


def test_faq_jsonld_matches_the_visible_answers(client):
    h = client.get("/faq").text
    faq = next(j for j in ld(h) if j["@type"] == "FAQPage")
    assert len(faq["mainEntity"]) == len(FAQ)
    for q, a in FAQ:
        assert q in h and a.replace("&", "&amp;")[:40] in h.replace("&#39;", "'")


def test_topic_page_has_prerequisites_mistakes_and_learning_resource(client, cur):
    h = client.get("/topics/m10_quad").text
    assert "Quadratic equations" in h and "/topics/m9_poly" in h and "Mistakes students commonly make" in h
    types = {j["@type"] for j in ld(h)}
    assert {"LearningResource", "FAQPage", "BreadcrumbList"} <= types
    assert client.get("/topics/does_not_exist").status_code == 404


def test_class_pages_list_chapters_from_the_real_data(client, cur):
    h = client.get("/curriculum/cbse/class-8/maths").text
    for ch in cur.chapters("CBSE", 8, "Maths"):
        assert ch["name"].replace("&", "&amp;") in h or ch["name"] in h
    assert client.get("/curriculum/xyz/class-8/maths").status_code == 404
    assert client.get("/curriculum/cbse/class-11/maths").status_code == 404


def test_sitemap_lists_every_page_once(client, cur):
    x = client.get("/sitemap.xml")
    assert x.headers["content-type"].startswith("application/xml")
    locs = re.findall(r"<loc>(.*?)</loc>", x.text)
    assert len(locs) == len(set(locs)) == len(all_paths())
    assert len(cur.T) + 30 + 10 == len(locs)
    assert "http://testserver/topics/m10_quad" in locs


def test_robots_and_llms(client):
    r = client.get("/robots.txt").text
    assert "Sitemap: http://testserver/sitemap.xml" in r and "Disallow: /api/" in r
    for bot in ("GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended"):
        assert f"User-agent: {bot}" in r
    t = client.get("/llms.txt").text
    assert t.startswith("# Sahayak") and "73 topics" in t and "/how-it-works" in t
    full = client.get("/llms-full.txt").text
    assert full.count("\n## ") == 73 and "Prerequisites:" in full


def test_site_url_setting_is_used_for_canonicals(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "site_url", "https://example.org")
    assert 'href="https://example.org/faq"' in client.get("/faq").text
    assert "<loc>https://example.org/</loc>" in client.get("/sitemap.xml").text


def test_unknown_page_is_a_helpful_404_but_api_errors_stay_json(client):
    r = client.get("/nope")
    assert r.status_code == 404 and "Page not found" in r.text and "noindex" in r.text
    a = client.get("/api/nope")
    assert a.status_code == 404 and a.json()["detail"]


def test_app_lives_under_app_and_old_service_worker_cleans_up(client):
    r = client.get("/app/")
    assert r.status_code == 200 and "Sahayak" in r.text and r.headers.get("x-robots-tag") == "noindex"
    assert client.get("/app/js/engine.js").status_code == 200
    sw = client.get("/sw.js")
    assert sw.status_code == 200 and "unregister" in sw.text


def test_contact_page_has_a_working_form_target(client):
    h = client.get("/contact").text
    assert 'action="/api/feedback"' in h and 'name="website"' in h
