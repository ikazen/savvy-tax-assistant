# Changelog

사용자(개발자) 영향 변경 이력. 한 줄/항목 단위.

## 미릴리스 (main)

### Phase 2 — 도메인 스키마 + 기본 API
- chat: `POST /api/v1/chat-sessions/{id}/chat` 가동 — Ollama Cloud LLM 직접 호출, 시스템 프롬프트 + 전체 히스토리, 사용자 메시지 우선 영속화
- ingest: `POST /api/v1/entities/{id}/communications` — 외부 채널(카톡/전화/메일) 메시지 저장, `source_id` 기반 dedup
- crud: persons / entities / chat-sessions API (`/api/v1/...`, limit/offset 페이지네이션)
- schema: persons·entities(owner_person_id)·chat 계열·client_communications + 지식베이스(laws/versions/chunks, cases/chunks)

### Phase 1 — 추상화 인프라
- abstraction: LLM/Embedding/VectorStore 3개 Protocol + factory
- embedding: Gemini Embedding 2 도입 (768d). pgvector 차원 768로 재생성 — Ollama Cloud는 chat만 제공
- bootstrap: alembic 제거 → `python -m savvy.storage.init_db` 단일 멱등 부트스트랩
