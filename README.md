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

## 구조

```
src/savvy/
├── api/          # FastAPI (lifespan, 라우터, schemas, deps)
├── llm/          # LLMProvider Protocol + Ollama
├── embedding/    # EmbeddingProvider Protocol + Ollama / Gemini
├── vectorstore/  # VectorStore Protocol + pgvector + namespace 상수
├── storage/      # ORM 모델, 세션, init_db
└── config.py     # Pydantic Settings
data/             # PDF 원본 (laws/, cases/) — gitignore
tests/            # pytest. live 마커는 opt-in (`pytest -m live`)
```

## 작업별 진입점

| 작업 | 위치 |
|---|---|
| 새 라우터 | `src/savvy/api/routers/` + `app.py`에 등록 |
| 새 ORM 모델 | `src/savvy/storage/models.py` |
| 새 LLM/Embed/VectorStore 벤더 | `src/savvy/{도메인}/{vendor}.py` + `factory.py` 분기 |
| Namespace 추가 | `src/savvy/vectorstore/namespaces.py` |
| Live 외부 검증 | `tests/test_live.py` |
| 스키마 변경 | `models.py` 수정 → `init_db.py` 재실행 |

## 더 보기

- [`ROADMAP.md`](ROADMAP.md) — 진척 + 핵심 결정
- [`architecture.md`](architecture.md) — 컴포넌트 + 데이터 흐름
- [`changelog.md`](changelog.md) — 사용자 영향 변경 이력
- [`CLAUDE.md`](CLAUDE.md) — 코딩 컨벤션
