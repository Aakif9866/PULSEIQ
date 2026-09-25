import time
import uuid

from app.ai.answer_cache import AnswerCache, cache_key


def test_cache_key_is_stable_for_the_same_dataset_and_question():
    dataset_id = uuid.uuid4()
    assert cache_key(dataset_id, "How many rows?") == cache_key(dataset_id, "How many rows?")


def test_cache_key_normalizes_whitespace_and_case():
    dataset_id = uuid.uuid4()
    assert cache_key(dataset_id, "How Many Rows?") == cache_key(dataset_id, "  how   many rows? ")


def test_cache_key_differs_across_datasets_for_the_identical_question():
    a, b = uuid.uuid4(), uuid.uuid4()
    assert cache_key(a, "How many rows?") != cache_key(b, "How many rows?")


def test_get_returns_none_for_an_unknown_key():
    cache: AnswerCache[str] = AnswerCache()
    assert cache.get("does-not-exist") is None


def test_set_then_get_returns_the_stored_value():
    cache: AnswerCache[str] = AnswerCache()
    cache.set("k", "an answer")
    assert cache.get("k") == "an answer"
    cache.clear()


def test_two_cache_instances_do_not_see_each_others_entries():
    # Different response shapes (AnalyzeResponse vs AskResponse) must
    # never collide even if a caller reused the same string key.
    cache_a: AnswerCache[str] = AnswerCache()
    cache_b: AnswerCache[str] = AnswerCache()
    cache_a.set("k", "from a")
    assert cache_b.get("k") is None
    cache_a.clear()


def test_expired_entry_is_treated_as_a_miss(monkeypatch):
    cache: AnswerCache[str] = AnswerCache()
    cache.set("k", "an answer")

    real_monotonic = time.monotonic
    monkeypatch.setattr("app.ai.answer_cache.time.monotonic", lambda: real_monotonic() + 10_000)
    assert cache.get("k") is None


def test_clear_only_removes_this_instances_own_entries():
    cache_a: AnswerCache[str] = AnswerCache()
    cache_b: AnswerCache[str] = AnswerCache()
    cache_a.set("k", "from a")
    cache_b.set("k", "from b")
    cache_a.clear()
    assert cache_a.get("k") is None
    assert cache_b.get("k") == "from b"
    cache_b.clear()
