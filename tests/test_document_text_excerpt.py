from app.services.document_text_excerpt import extract_text_excerpts


def test_extract_text_excerpts_returns_matching_fragments():
    full_text = (
        "Преамбула договора. "
        "Срок возврата кредита составляет 36 месяцев с даты выдачи. "
        "Процентная ставка 12% годовых."
    )
    text, excerpt_count, truncated = extract_text_excerpts(
        full_text,
        "срок возврата",
        max_chars=5000,
    )
    assert excerpt_count >= 1
    assert "36 месяцев" in text
    assert truncated is False


def test_extract_text_excerpts_truncates_long_text_without_query():
    full_text = "А" * 20000
    text, excerpt_count, truncated = extract_text_excerpts(full_text, None, max_chars=1000)
    assert len(text) == 1000
    assert excerpt_count == 0
    assert truncated is True
