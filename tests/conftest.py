import pytest

from vibefinance.profiles.store import Store
from vibefinance.rag.retriever import Retriever


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "test.sqlite3")


@pytest.fixture
def retriever():
    return Retriever(embeddings=False)
