from __future__ import annotations

import uuid

from savvy.vectorstore import namespaces


def test_static_namespaces_are_distinct() -> None:
    assert namespaces.TAX_LAW != namespaces.CASE_LAW
    assert ":" not in namespaces.TAX_LAW
    assert ":" not in namespaces.CASE_LAW


def test_client_history_includes_entity_id() -> None:
    eid = uuid.uuid4()
    ns = namespaces.client_history(eid)
    assert ns == f"client_history:{eid}"


def test_client_history_isolation_per_entity() -> None:
    a = uuid.uuid4()
    b = uuid.uuid4()
    assert namespaces.client_history(a) != namespaces.client_history(b)


def test_client_history_accepts_str_id() -> None:
    assert namespaces.client_history("abc-123") == "client_history:abc-123"
