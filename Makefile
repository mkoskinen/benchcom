.PHONY: help build up down restart logs clean db-shell api-shell test client-deps lint format check

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
	@echo "  Development:"
	@echo "    make db-shell   - Connect to PostgreSQL shell"
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

# API shell
api-shell:
	podman exec -it benchcom-api /bin/bash

# Run benchmark and submit to local API
benchmark:
	./benchcom.sh --api-url http://localhost:8000

# Install Python client dependencies
client-deps:
	pip3 install --user -r client/requirements.txt

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
