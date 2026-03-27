.PHONY: install install-backend install-frontend dev backend frontend

APP_PORT ?= 8080
APP_HOST ?= 0.0.0.0
TORCH_INDEX ?= https://download.pytorch.org/whl/cu128

# ── Install ──

install: install-backend install-frontend

install-backend:
	uv sync
	uv pip install "torch==2.10.0+cu128" "torchaudio==2.10.0+cu128" "torchcodec==0.10.0+cu128" --index-url $(TORCH_INDEX)
	uv sync --extra gpu

install-frontend:
	cd web && npm install

# ── Dev ──

dev:
	@$(MAKE) -j2 backend frontend

backend:
	uv run uvicorn src.main:app --host $(APP_HOST) --port $(APP_PORT) --reload

frontend:
	cd web && npm run dev
