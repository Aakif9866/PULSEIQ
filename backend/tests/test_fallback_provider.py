import pytest

from app.ai.providers.base import AIProvider, ProviderMessage
from app.ai.providers.fallback import FallbackProvider
from app.core.exceptions import AiResponseError


class _FakeProvider(AIProvider):
    def __init__(self, outcome: ProviderMessage | Exception) -> None:
        self._outcome = outcome
        self.call_count = 0

    def chat(self, *, messages, tools=None, json_mode=False, temperature=0.1) -> ProviderMessage:
        self.call_count += 1
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome


def test_returns_the_first_providers_successful_response():
    primary = _FakeProvider(ProviderMessage(content="from primary"))
    backup = _FakeProvider(ProviderMessage(content="from backup"))
    fallback = FallbackProvider([primary, backup])

    message = fallback.chat(messages=[])

    assert message.content == "from primary"
    assert primary.call_count == 1
    assert backup.call_count == 0  # never touched — the primary succeeded


def test_falls_back_to_the_next_provider_when_the_first_fails():
    primary = _FakeProvider(AiResponseError("primary is down"))
    backup = _FakeProvider(ProviderMessage(content="from backup"))
    fallback = FallbackProvider([primary, backup])

    message = fallback.chat(messages=[])

    assert message.content == "from backup"
    assert primary.call_count == 1
    assert backup.call_count == 1


def test_raises_the_last_providers_error_when_every_provider_fails():
    primary = _FakeProvider(AiResponseError("primary is down"))
    backup = _FakeProvider(AiResponseError("backup is also down"))
    fallback = FallbackProvider([primary, backup])

    with pytest.raises(AiResponseError, match="backup is also down"):
        fallback.chat(messages=[])


def test_a_single_provider_behaves_like_using_it_directly():
    only = _FakeProvider(ProviderMessage(content="only answer"))
    fallback = FallbackProvider([only])
    assert fallback.chat(messages=[]).content == "only answer"


def test_rejects_an_empty_provider_list_at_construction():
    with pytest.raises(ValueError, match="at least one"):
        FallbackProvider([])


def test_three_providers_falls_through_to_the_third():
    first = _FakeProvider(AiResponseError("1 down"))
    second = _FakeProvider(AiResponseError("2 down"))
    third = _FakeProvider(ProviderMessage(content="from third"))
    fallback = FallbackProvider([first, second, third])

    message = fallback.chat(messages=[])

    assert message.content == "from third"
    assert [p.call_count for p in (first, second, third)] == [1, 1, 1]
