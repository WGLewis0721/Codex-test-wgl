.PHONY: setup dev-all test clean

AGENTS := support-triage knowledge-copilot lead-qualification customer-profile interview-fit workbench-gateway

setup:
	@echo "Installing shared dependencies..."
	pip install pydantic pydantic-settings httpx
	@for agent in $(AGENTS); do \
		echo "Installing $$agent dependencies..."; \
		pip install -r agents/$$agent/requirements.txt; \
	done

dev-all:
	docker compose up --build

dev-ollama:
	docker compose up ollama

test:
	@echo "Running all agent tests..."
	@cd agents/support-triage && python -m pytest tests/ -v
	@cd agents/knowledge-copilot && python -m pytest tests/ -v
	@cd agents/lead-qualification && python -m pytest tests/ -v
	@cd agents/customer-profile && python -m pytest tests/ -v
	@cd agents/interview-fit && python -m pytest tests/ -v
	@cd agents/workbench-gateway && python -m pytest tests/ -v

test-agent:
	@if [ -z "$(AGENT)" ]; then echo "Usage: make test-agent AGENT=support-triage"; exit 1; fi
	cd agents/$(AGENT) && python -m pytest tests/ -v

logs:
	docker compose logs -f

clean:
	docker compose down -v
	find . -depth -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -depth -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true

pull-model:
	docker compose exec ollama ollama pull phi3:medium
	docker compose exec ollama ollama pull nomic-embed-text

status:
	@echo "=== Agent Health Checks ==="
	@curl -s http://localhost:8001/health | python3 -m json.tool 2>/dev/null || echo "support-triage: offline"
	@curl -s http://localhost:8002/health | python3 -m json.tool 2>/dev/null || echo "knowledge-copilot: offline"
	@curl -s http://localhost:8003/health | python3 -m json.tool 2>/dev/null || echo "lead-qualification: offline"
	@curl -s http://localhost:8004/health | python3 -m json.tool 2>/dev/null || echo "customer-profile: offline"
	@curl -s http://localhost:8005/health | python3 -m json.tool 2>/dev/null || echo "interview-fit: offline"
	@curl -s http://localhost:8006/health | python3 -m json.tool 2>/dev/null || echo "workbench-gateway: offline"
