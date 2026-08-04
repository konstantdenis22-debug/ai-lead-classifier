.PHONY: install run test test-api report clean

install:
	python -m venv .venv
	. .venv/bin/activate && pip install -r requirements.txt

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	python tests/test_runner.py

test-api:
	MOCK_LLM=true pytest tests/test_api.py -v

report:
	@ls -lt reports/ | head -5

clean:
	rm -rf logs/*.jsonl reports/*.json __pycache__ .pytest_cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
