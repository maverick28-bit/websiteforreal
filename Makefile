.PHONY: up down build logs test clean

## Build and start the entire stack
up:
	docker compose up --build -d
	@echo ""
	@echo "  Frontend: http://localhost:3000"
	@echo "  Backend:  http://localhost:8000"
	@echo "  API docs: http://localhost:8000/docs"

## Stop the stack
down:
	docker compose down

## Build images without starting
build:
	docker compose build

## Follow logs
logs:
	docker compose logs -f

## Run backend tests (requires venv)
test:
	cd backend && python -m pytest tests/ -v

## Clean containers, volumes, and images
clean:
	docker compose down -v --rmi all
