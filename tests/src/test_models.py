from src.models import Article


def test_article():

    article = Article(
        id="hn_001",
        title="GPT New Model",
        url="https://example.com",
        source="hackernews",
        summary=None,
        author=None,
        published_at=None,
        score=100,
        tags=["LLM"],
        language="en"
    )


    assert article.title == "GPT New Model"

    