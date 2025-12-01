.PHONY: help build up down restart logs clean db-shell api-shell test test-up test-down dev-deps client-deps lint format check db-dump deploy-frontend deploy-api deploy

# Default target
help:
	@echo "╔═══════════════════════════════════════════════════════════════╗"
	@echo "║                          BENCHCOM                            ║"
	@echo "╚═══════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "Available targets:"
	@echo "  Server:"
	@echo "    make build      - Build all containers"
	@echo "    make up         - Start all services"
	@echo "    make down       - Stop all services"
	@echo "    make restart    - Restart all services"
	@echo "    make logs       - Show logs from all services"
	@echo "    make clean      - Remove containers and volumes"
	@echo ""
	@echo "  Client:"
	@echo "    make benchmark  - Run benchmark and submit to local API"
	@echo "    make client-deps - Install Python client dependencies"
	@echo ""
	@echo "  Testing:"
	@echo "    make test       - Run API tests (starts test containers)"
	@echo "    make test-up    - Start test containers only"
	@echo "    make test-down  - Stop test containers"
	@echo "    make dev-deps   - Install development dependencies"
	@echo ""
	@echo "  Deployment:"
	@echo "    make deploy-frontend - Rebuild and redeploy frontend (no cache)"
	@echo "    make deploy-api      - Rebuild and redeploy API (no cache)"
	@echo "    make deploy          - Redeploy all services (no cache)"
	@echo ""
	@echo "  Development:"
	@echo "    make db-shell   - Connect to PostgreSQL shell"
	@echo "    make db-dump    - Dump database to SQL (zstd compressed)"
	@echo "    make api-shell  - Connect to API container shell"
	@echo "    make lint       - Run linters (ruff, eslint)"
	@echo "    make format     - Format code (ruff, prettier)"
	@echo "    make check      - Run all checks"

# Build containers
build:
	podman-compose build

# Start services
up:
	podman-compose up -d
	@echo "Waiting for services to start..."
	@sleep 5
	@echo "Services started!"
	@echo "API: http://localhost:8000"
	@echo "Frontend: http://localhost:3000"
	@echo "API Docs: http://localhost:8000/docs"

# Stop services
down:
	podman-compose down

# Restart services
restart: down up

# Show logs
logs:
	podman-compose logs -f

# Clean up everything
clean:
	podman-compose down -v
	podman volume prune -f

# Database shell
db-shell:
	podman exec -it benchcom-db psql -U benchcom -d benchcom

# Dump database to SQL file (zstd compressed)
db-dump:
	@TIMESTAMP=$$(date +%Y%m%d_%H%M%S); \
	DUMPFILE="benchcom_dump_$$TIMESTAMP.sql.zst"; \
	echo "Dumping database to $$DUMPFILE..."; \
	podman exec benchcom-db pg_dump -U benchcom -d benchcom | zstd -19 > $$DUMPFILE; \
	echo "Done: $$DUMPFILE ($$(du -h $$DUMPFILE | cut -f1))"

# API shell
api-shell:
	podman exec -it benchcom-api /bin/bash

# Run benchmark and submit to local API
benchmark:
	./benchcom.sh --api-url http://localhost:8000

# Install Python client dependencies
client-deps:
	pip3 install --user -r client/requirements.txt

# Install development dependencies
dev-deps:
	pip3 install --user -r requirements-dev.txt

# Start test containers
test-up:
	podman-compose --profile test up -d db-test api-test
	@echo "Waiting for test services to start..."
	@sleep 5
	@cat api/schema.sql | podman exec -i benchcom-db-test psql -U benchcom -d benchcom_test
	@echo "Test services ready on port 8001"

# Stop test containers
test-down:
	podman-compose --profile test down

# Run API tests
test: test-up
	@echo "Running API tests..."
	python -m pytest api/tests/test_api.py -v
	@$(MAKE) test-down

# Lint all code
lint:
	@echo "=== Python (ruff) ==="
	ruff check api/app/ client/benchcom.py
	@echo ""
	@echo "=== TypeScript (eslint) ==="
	cd frontend && npm run lint

# Format all code
format:
	@echo "=== Python (ruff) ==="
	ruff format api/app/ client/benchcom.py
	ruff check --fix api/app/ client/benchcom.py
	@echo ""
	@echo "=== TypeScript/CSS (prettier) ==="
	cd frontend && npm run format

# Run all checks
check: lint
	@echo ""
	@echo "=== TypeScript (tsc) ==="
	cd frontend && npm run typecheck
	@echo ""
	@echo "All checks passed!"

# Deploy frontend (rebuild with no cache, restart container)
deploy-frontend:
	@echo "=== Deploying frontend ==="
	podman stop benchcom-frontend 2>/dev/null || true
	podman rm benchcom-frontend 2>/dev/null || true
	podman rmi benchcom_frontend 2>/dev/null || true
	podman build --no-cache --build-arg CACHEBUST=$$(date +%s) -t benchcom_frontend -f frontend/Dockerfile frontend/
	podman-compose up -d frontend
	@echo "Frontend deployed! Clear browser cache (Ctrl+Shift+R) to see changes."

# Deploy API (rebuild with no cache, restart container)
deploy-api:
	@echo "=== Deploying API ==="
	podman stop benchcom-api 2>/dev/null || true
	podman rm benchcom-api 2>/dev/null || true
	podman rmi benchcom_api 2>/dev/null || true
	podman build --no-cache -t benchcom_api -f api/Dockerfile api/
	podman-compose up -d api
	@echo "API deployed!"

# Deploy all services (no cache rebuild)
deploy: deploy-api deploy-frontend
	@echo ""
	@echo "=== All services deployed ==="
	@echo "API: http://localhost:8000"
	@echo "Frontend: http://localhost:3000"
