# savvy-tax-assistant — 프로젝트 컨텍스트

세무사 본인 업무 보조용 agentic RAG 챗봇. 단일 사용자 시작, 멀티테넌트 확장 대비.

## 진척 상황
세부 진척과 다음 phase는 `ROADMAP.md` 참조. 새 작업 시작 시 먼저 확인.

## 황금 규칙
- LLM/Embedding/VectorStore는 **항상 factory 통해서**:
  `make_llm(settings)`, `make_embedding(settings)`, `make_vector_store(...)`.
  `OllamaLLM(...)` 등 직접 인스턴스화 금지 (테스트 mock 제외).
- `tenant_id`는 **항상 `get_settings().default_tenant_id`** 에서. 하드코딩 금지.
- 새 도메인 ORM 추가 시 `models.py`에 같이. `__table_args__`에 인덱스 명시.
- VectorStore namespace는 `src/savvy/vectorstore/namespaces.py`의 상수/함수만 사용.
  문자열 직접 작성 금지.
- pgvector 차원은 `EMBED_DIMENSION` 단일 source. embedding 모델 바꾸면 차원
  맞추고 DB drop+recreate 필요 (init_db.py 멱등).

## API 컨벤션
- prefix `/api/v1`, async 라우터, Pydantic v2 schemas (`Base/Create/Update/Out`)
- PATCH는 `model_dump(exclude_unset=True)` 로 보낸 필드만 반영
- 페이지네이션 `limit`/`offset` (Annotated + Query)
- 에러: 404 (없음), 409 (충돌), 502 (LLM 실패), 422 (validation, FastAPI 자동)

## 테스트
- DB 필요 테스트: `pytestmark = requires_db`
- 외부 API 호출 테스트: `pytest.mark.live` + `requires_ollama` / `requires_gemini`,
  기본 deselect (opt-in `pytest -m live`)
- API 테스트는 conftest의 `session_factory`를 `app.state.session_factory`에
  주입해서 lifespan 우회 (엔진 중복 방지)

## 기타
- 글로벌 코딩 스타일: `~/.claude/CLAUDE.md` 따름 (타입힌트, 함수 우선,
  점진 구현, 자동 커밋 등)
- 상세 결정 사항: `ROADMAP.md` 의 "핵심 결정 사항"
- 폴더 구조/진입점: `README.md`
- 컴포넌트 + 데이터 흐름: `architecture.md`
- 사용자 영향 변경 이력: `changelog.md`
