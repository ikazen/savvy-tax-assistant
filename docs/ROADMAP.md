# savvy-tax-assistant — 진척 & 로드맵

세무사 본인 업무 보조용 agentic RAG 챗봇.

## 핵심 결정 사항

- **스택**: Python 3.12+, uv, FastAPI, Postgres + pgvector, async 전반
- **LLM**: Ollama Cloud (`gpt-oss:20b`) — 추상화로 교체 가능
- **Embedding**: Gemini Embedding 2 (768차원, Matryoshka) — 추상화로 교체 가능
- **Vector store**: pgvector — 추상화로 Qdrant/Milvus 가능
- **에이전트 프레임워크**: 자체 구현 (LangChain 등 미사용)
- **PK**: UUID v4 (단순)
- **tenant_id**: 사용자 데이터에만 (Person/Entity/ChatSession 등). 법령/판례는 글로벌
- **PII**: external_id 평문 저장 (단일 사용자 단계)
- **삭제 정책**: hard delete + FK CASCADE
- **법령 diff**: LawVersion 풀 텍스트 저장 + `prev_version_id` 체인
- **API**: `/api/v1` prefix, async 라우터, Pydantic v2, 인증 없음 (localhost)
- **자동 커밋**: 단계 완료 시 Conventional Commits 로 즉시 커밋

## 진척 현황

### Phase 1 — 추상화 인프라 ✅
- [x] LLM/Embedding/VectorStore 3개 Protocol + factory
- [x] OllamaLLM (local + cloud), OllamaEmbedding, GeminiEmbedding, PgVectorStore
- [x] `init_db.py` (alembic 제거)
- [x] vectorstore namespace 규약 (`tax_law`, `case_law`, `client_history:{entity_id}`)
- [x] live test: Ollama Cloud chat / Gemini embed / pgvector e2e

### Phase 2 — 도메인 스키마 + 기본 API ✅
- [x] **사용자 도메인**: persons, entities (owner_person_id), chat_sessions, chat_messages, client_communications, client_communication_chunks
- [x] **지식베이스**: laws, law_versions (prev_version_id 체인), law_chunks, cases, case_chunks
- [x] **API**:
  - `/api/v1/health`
  - `POST/GET/PATCH/DELETE /api/v1/{entities,persons,chat-sessions}[/{id}]`
  - `GET /api/v1/chat-sessions/{id}/messages`
  - `POST/GET /api/v1/entities/{id}/communications`
  - `GET/DELETE /api/v1/communications/{id}`
  - `POST /api/v1/chat-sessions/{id}/chat` — LLM 직접 호출, system prompt + 전체 히스토리, 사용자 메시지 우선 영속화
- [x] live e2e via FastAPI app

### Phase 3 — PDF ingestion 파이프라인 ⏳
법령/판례 PDF를 수동 업로드 → 텍스트 추출 → 청킹 → 임베딩 → pgvector
- [ ] PDF 파서 비교 (pypdf / pdfplumber / unstructured 등)
- [ ] 법령 → 조문 단위 구조화 (제13조 ① ② …)
- [ ] LawVersion 등록 + LawChunk 청킹 + 임베딩 → `tax_law` namespace
- [ ] Case 등록 + CaseChunk 청킹 → `case_law` namespace
- [ ] CLI 또는 admin endpoint (`POST /admin/laws`, `POST /admin/cases`)

### Phase 4 — Self-built Agent ⏳
`plan → tool_call → observe → answer` 루프
- [ ] tool 인터페이스 (`name`, `parameters`, `run`)
- [ ] 기본 tool 3개:
  - `search_tax_law(query)` — tax_law namespace 검색
  - `search_case_law(query)` — case_law namespace 검색
  - `search_client_history(entity_id, query)` — client_history namespace 검색
- [ ] Agent loop (max iterations, finish_reason 처리)
- [ ] 인용 포맷 (법명·조항·판례번호) — system prompt에 강제
- [ ] chat 엔드포인트를 agent로 교체

### Phase 5 — Client communication 수집 ⏳
이미 schema·API 준비됨. 인풋 파이프라인이 남음.
- [ ] 카톡 export (.txt) 파서 → POST /entities/{id}/communications 일괄
- [ ] 메일 IMAP 연동 (Gmail OAuth)
- [ ] 통화 녹음 → Whisper STT → POST
- [ ] 임베딩 파이프라인: ClientCommunication → 청킹 → 임베딩 → `client_history:{entity_id}` namespace

### Phase 6 — 법령 버전 관리 & diff tool ⏳
- [ ] `get_law_diff(law_name, from_date, to_date)` tool — `difflib.unified_diff(LawVersion.text)`
- [ ] LawVersion 자동 체인 연결 (시행일자 기반)
- [ ] 새 시행본 업로드 시 prev_version_id 자동 연결

### Phase 7 — 판례 ingestion 강화 ⏳
- [ ] 대법원/조세심판원 판례 정규화
- [ ] 판례별 카테고리 자동 분류 (LLM)

### Phase 8+ — 운영 강화 ⏳
- 자동 크롤링 (국가법령정보센터)
- 멀티테넌트 인증 (JWT 등)
- 평가셋 + 회귀 테스트
- 프론트엔드 (별도)

## 빠른 명령어

```bash
docker compose up -d                          # Postgres
uv run python -m savvy.storage.init_db        # 스키마 생성/갱신
uv run pytest                                 # 전체 (live 제외)
uv run pytest -m live                         # 라이브 (Ollama+Gemini 키 필요)
uv run uvicorn savvy.api.app:app --port 8765  # API 서버
# Swagger: http://127.0.0.1:8765/docs
```

## 핵심 파일 진입점

- `src/savvy/api/app.py` — 라우터 등록 + lifespan (engine, session_factory, llm 주입)
- `src/savvy/api/routers/chat.py` — chat 흐름 (사용자 → LLM → 영속화)
- `src/savvy/storage/models.py` — 전체 ORM 스키마 한 파일
- `src/savvy/{llm,embedding,vectorstore}/` — 각 추상화: `base.py` (Protocol) + `{vendor}.py` + `factory.py`
- `tests/test_live.py` — 외부 API 라이브 검증 (`pytest -m live`)
