import pytest
from services.delivery.main import get_theme, group_by_themes
from services.collector.filter import is_relevant

def test_get_theme_logic():
    # Test mapping specific topics to high-level themes
    assert get_theme(["llm", "python"]) == "🧠 Generative AI"
    assert get_theme(["postgres", "security"]) == "🛡️ Security & Infra"
    # New logic: Fallback to the first topic formatted as "📌 Topic"
    assert get_theme(["cooking", "sports"]) == "📌 Cooking"
    assert get_theme([]) == "🌐 General Tech"

def test_group_by_themes():
    articles = [
        {"title": "AI stuff", "topics": ["llm"]},
        {"title": "Dev stuff", "topics": ["python"]},
        {"title": "Random stuff", "topics": ["news"]}
    ]
    grouped = group_by_themes(articles)
    assert "🧠 Generative AI" in grouped
    assert "🛠️ Dev Tools" in grouped
    assert "📌 News" in grouped
    assert len(grouped["🧠 Generative AI"]) == 1

def test_is_relevant_filter(mocker):
    # Mock the get_filter_config to avoid DB hits during unit tests
    mocker.patch("services.collector.filter.get_cached_config", return_value={
        "allowed": ["ai", "python"],
        "blocked": ["crypto"]
    })
    
    assert is_relevant("Top AI Breakthroughs") is True
    assert is_relevant("Best Python tutorials") is True
    assert is_relevant("Crypto price spike") is False
    assert is_relevant("Random irrelevant title") is False
