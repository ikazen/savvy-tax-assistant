# savvy-tax-assistant

세무사 본인의 업무 보조용 agentic RAG 챗봇 (Python · FastAPI · Postgres+pgvector).

## 구조

```
src/savvy/
├── llm/          # LLMProvider 프로토콜 + 구현체 (Ollama, Gemini)
├── embedding/    # EmbeddingProvider 프로토콜 + 구현체
├── vectorstore/  # VectorStore 프로토콜 + 구현체 (pgvector, Qdrant 등)
└── config.py     # 환경 설정
data/
├── laws/         # 세법 PDF 원본 (시행일자별)
└── cases/        # 판례 PDF 원본
```

## 개발 환경

```bash
# 의존성 설치
uv sync

# Postgres + pgvector
docker compose up -d

# 환경 변수
cp .env.example .env

# DB 스키마 초기화 (멱등)
uv run python -m savvy.storage.init_db

# 테스트
uv run pytest
```
