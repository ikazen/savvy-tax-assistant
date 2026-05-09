# 아키텍처

## 3개의 독립 추상화 (왜)

LLM·Embedding·VectorStore는 **각자 별개의 Protocol**. 한 벤더의 LLM과 Embed가 다른 모델로 운영될 수 있고 실제로 그러함 — Ollama Cloud는 chat만 제공하고 embed는 Gemini로 보냄.

```
LLMProvider          ← OllamaLLM (Cloud + local 한 클래스, base_url로 분기)
EmbeddingProvider    ← OllamaEmbedding | GeminiEmbedding
VectorStore          ← PgVectorStore | (Qdrant/Milvus 추가 가능)
```

각 도메인은 동일 패턴: `src/savvy/{도메인}/base.py` (Protocol) + `{vendor}.py` (구현) + `factory.py` (settings 기반 분기). 비즈니스 로직은 항상 factory를 통해서만 인스턴스 받는다 (`CLAUDE.md` 황금 규칙).

## Chat 요청 라이프사이클

```
POST /api/v1/chat-sessions/{id}/chat
  ├─ 사용자 메시지 영속화 (commit) ← LLM 실패해도 사용자 입력 보존
  ├─ 세션 히스토리 chronological 로드
  ├─ [system_prompt, ...history, user_msg] 로 LLM.chat()
  ├─ assistant 메시지 영속화 (model_id, token_usage 포함)
  └─ ChatMessageOut 반환
```

LLM 실패 시 502 + 사용자 메시지만 남음. Tools/streaming 없음 (Phase 4에서 agent loop으로 교체).

## 지식베이스 ingest 흐름 (Phase 3+)

```
PDF (data/laws/)
  → 텍스트 추출 + 조문 단위 구조화
  → Law / LawVersion (시행일자별, prev_version_id 체인)
       └→ LawChunk (article_no/paragraph_no nullable, fallback=토큰 윈도우)
            └→ EmbeddingProvider.embed
                 └→ VectorStore.upsert(namespace="tax_law", id=LawChunk.id)
```

Case도 동일 (`case_law` namespace). 청킹은 hierarchical 미지원 — 필요해지면 `parent_chunk_id`/`level` 컬럼 ALTER로 추가 가능 (현재 flat은 호환됨).

## VectorStore namespace 격리

상수: `src/savvy/vectorstore/namespaces.py`

| Namespace | 격리 단위 | 매핑 대상 |
|---|---|---|
| `tax_law` | 글로벌 | `LawChunk.id` |
| `case_law` | 글로벌 | `CaseChunk.id` |
| `client_history:{entity_id}` | 사업체 | `ClientCommunicationChunk.id` |

법령·판례는 모든 사용자가 공유. 고객 커뮤니케이션은 사업체별로 namespace 분리 — 다른 고객 데이터가 절대 검색되지 않게.

## 도메인 모델 (왜)

- **Person ↔ Entity 분리**: 한 사람이 여러 사업체 운영 가능 (`entities.owner_person_id`). 세무사 업무 단위는 사업체이므로 ChatSession/Communication은 Entity에 연결.
- **chat_messages vs client_communications 분리**: 전자는 챗봇 대화 (LLM 컨텍스트), 후자는 실제 카톡/전화/메일 (RAG 인풋). 데이터 성격이 다르므로 분리.
- **LawVersion = 풀 텍스트 스냅샷**: 시행일자별 전문을 통째로 저장. diff는 `difflib.unified_diff(v_old.text, v_new.text)`로 즉석 생성 (Phase 6). git-style patch 저장 대비 단순하고 검색에도 유리.

## 멀티테넌트 대비

- `tenant_id` 컬럼이 사용자 도메인 테이블 전체에 존재. 현재 `'default'` 단일값 (`get_settings().default_tenant_id`)
- 법령/판례 테이블은 tenant 무관 (글로벌 자료)
- 인증은 Phase 8+에서 (현재 localhost 가정, prefix `/api/v1`은 버저닝용)
