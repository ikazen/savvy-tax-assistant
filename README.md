# savvy-tax-assistant

세무사 본인 업무 보조용 agentic RAG 챗봇. Python 3.12+ · FastAPI · Postgres+pgvector.

## 빠른 시작

```bash
docker compose up -d                          # Postgres + pgvector
cp .env.example .env                          # OLLAMA_API_KEY / GEMINI_API_KEY 입력
uv sync
uv run python -m savvy.storage.init_db        # 스키마 초기화 (멱등)
uv run pytest                                 # 테스트 (live 제외)
uv run uvicorn savvy.api.app:app --port 8765  # API 서버
# Swagger: http://127.0.0.1:8765/docs
```

## 더 보기

- [`ROADMAP.md`](ROADMAP.md) — 진척 현황 및 핵심 결정 사항
- [`docs/README.md`](docs/README.md) — 폴더 구조 및 진입점
- [`docs/architecture.md`](docs/architecture.md) — 컴포넌트 + 데이터 흐름
- [`CLAUDE.md`](CLAUDE.md) — 코딩 컨벤션 및 황금 규칙
