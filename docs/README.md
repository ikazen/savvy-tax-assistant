# 프로젝트 구조

세무사 업무 보조용 agentic RAG 챗봇. 단일 사용자 시작, 멀티테넌트 확장 대비.

## 폴더

```
src/savvy/
├── api/            # FastAPI 앱 (lifespan, 라우터, schemas, deps)
│   ├── app.py        # create_app + 라우터 등록
│   ├── deps.py       # SessionDep, LLMDep
│   ├── routers/      # 자원별 라우터
│   └── schemas/      # Pydantic Base/Create/Update/Out
├── llm/            # LLMProvider Protocol + 구현 + factory
├── embedding/      # EmbeddingProvider Protocol + 구현 + factory
├── vectorstore/    # VectorStore Protocol + 구현 + namespace 상수
├── storage/        # SQLAlchemy ORM (models.py), 세션, init_db
└── config.py       # Pydantic Settings (.env 로드)

data/               # PDF 원본 (laws/, cases/) — gitignore
docs/               # 문서 (이 폴더)
tests/              # pytest. live 마커는 opt-in (`pytest -m live`)
```

## 작업별 진입점

- **새 라우터** → `src/savvy/api/routers/{name}.py` + `app.py`에 `include_router` 등록
- **새 도메인 모델** → `src/savvy/storage/models.py` (단일 파일에 전체)
- **새 LLM/Embedding/VectorStore 벤더** → `src/savvy/{도메인}/{vendor}.py` + 같은 도메인 `factory.py` 분기
- **VectorStore namespace 추가** → `src/savvy/vectorstore/namespaces.py` 상수/함수
- **live 외부 API 검증** → `tests/test_live.py` (Ollama/Gemini 키 필요)
- **DB 스키마 변경** → `models.py` 수정 후 `uv run python -m savvy.storage.init_db` (멱등). 차원 변경 등 컬럼 타입 깨지면 drop+recreate

## 외부 자원

- Postgres: `docker-compose.yml` 의 `pgvector/pgvector:pg16`. 볼륨 `savvy-postgres-data`로 영속화
- Ollama Cloud: `https://ollama.com` (chat 전용, embed 없음)
- Google AI Studio (Gemini): `https://generativelanguage.googleapis.com` (embed 사용)
- Swagger UI: 서버 실행 중 `/docs`
