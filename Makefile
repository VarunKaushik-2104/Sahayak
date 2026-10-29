.PHONY: install run test e2e content docker
install:
	pip install -r backend/requirements-dev.txt
run:
	cd backend && uvicorn app.main:app --reload --port 8000
test:
	cd backend && python -m pytest -q
content:
	python scripts/build_curriculum.py && cd backend && python -m app.cli check-content
e2e:       # server must be running on :8000 with SEED_DEMO=1
	node scripts/e2e.js http://localhost:8000
docker:
	docker compose up --build
