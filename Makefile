.PHONY: setup run test docker-up docker-down docker-build lint clean help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup: ## Install dependencies and setup environment
	cd backend && pip install -r requirements.txt
	cp -n .env.example backend/.env 2>/dev/null || true
	@echo "Setup complete. Run 'make run' to start the server."

run: ## Run the backend server locally
	cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

test: ## Run all tests
	cd backend && python -m pytest tests/ -v --tb=short

test-cov: ## Run tests with coverage
	cd backend && python -m pytest tests/ -v --cov=app --cov-report=term-missing

test-features: ## Run feature engineering tests
	cd backend && python -m pytest tests/test_features.py -v

test-rules: ## Run rule detector tests
	cd backend && python -m pytest tests/test_rules.py -v

test-ml: ## Run ML detector tests
	cd backend && python -m pytest tests/test_ml.py -v

test-custom: ## Run custom detector tests
	cd backend && python -m pytest tests/test_custom_detectors.py -v

test-scoring: ## Run scoring engine tests
	cd backend && python -m pytest tests/test_scoring.py -v

test-integration: ## Run integration tests
	cd backend && python -m pytest tests/test_integration.py -v

test-synthetic: ## Run synthetic data tests
	cd backend && python -m pytest tests/test_synthetic.py -v

docker-build: ## Build Docker images
	docker-compose build

docker-up: ## Start all services with Docker
	docker-compose up -d

docker-down: ## Stop all Docker services
	docker-compose down

docker-logs: ## View Docker logs
	docker-compose logs -f backend

docker-test: ## Run tests inside Docker
	docker-compose exec backend python -m pytest tests/ -v

clean: ## Clean up generated files
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf backend/.pytest_cache backend/htmlcov backend/.coverage

train: ## Train ML models with synthetic data
	cd backend && python -c "import asyncio; from app.detectors.ml.trainer import MLTrainer; t = MLTrainer(); asyncio.run(t.train_all(n_samples=2000))"
