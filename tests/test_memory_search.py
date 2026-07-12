"""Ranked memory retrieval (RAG): relevance ranking over cards. Offline."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.config import AgentConfig
from agent.memory import MemoryStore, _tokenize


def _store():
    return MemoryStore(AgentConfig(memory_root=tempfile.mkdtemp()))


def test_tokenize_drops_stopwords():
    assert _tokenize("The quick brown fox") == ["quick", "brown", "fox"]
    assert _tokenize("I am with you") == ["am"]


def test_search_ranks_relevant_card_first():
    s = _store()
    s.append("Giovanni lifts weights and does calisthenics", target="user")
    s.append("The pendant enclosure needs an antenna cutout", target="user")
    s.append("Giovanni is studying philosophy", target="user")
    top = s.search("what sport does he do", target="user", limit=2)
    assert top and "calisthenics" in top[0].lower()
    print("OK search surfaces the relevant card first")


def test_search_empty_query_returns_recent():
    s = _store()
    for i in range(5):
        s.append(f"card {i}", target="agent")
    assert s.search("", target="agent", limit=2) == ["card 3", "card 4"]
    print("OK empty query falls back to recency")


def test_recall_with_query_ranks_over_recency():
    s = _store()
    s.append("the ring reports HR and SpO2 over BLE", target="agent")
    for i in range(10):
        s.append(f"unrelated note {i}", target="agent")
    # newest 8 are all "unrelated"; a relevant query must still surface the ring
    rec = s.recall(target="agent", limit=8, query="heart rate ring")
    assert "ring reports HR" in rec
    print("OK recall(query) beats pure recency for relevant memory")


def test_recall_no_query_is_recency_as_before():
    s = _store()
    for i in range(12):
        s.append(f"note {i}", target="agent")
    rec = s.recall(target="agent", limit=3)
    assert "note 11" in rec and "note 9" in rec and "note 0" not in rec
    print("OK recall() without a query keeps recency behaviour")
