def test_secret_tokens_are_replaced_in_text() -> None:
    from app.services.redaction import redact

    secret_text = (
        "ghp_"
        + ("A" * 36)
        + " "
        + "github_pat_"
        + ("B" * 22)
        + "_"
        + ("C" * 59)
        + " "
        + "sk-"
        + ("D" * 32)
        + " "
        + "API_TOKEN="
        + "fakevalue123"
        + " "
        + "Authorization: Bearer "
        + "eyJfake.token.value"
    )
    secret_substrings = [
        "ghp_" + ("A" * 36),
        "github_pat_" + ("B" * 22) + "_" + ("C" * 59),
        "sk-" + ("D" * 32),
        "fakevalue123",
        "eyJfake.token.value",
    ]

    redacted = redact(secret_text)

    for secret in secret_substrings:
        assert secret not in redacted
    assert "[REDACTED]" in redacted


def test_non_secret_text_is_unchanged() -> None:
    from app.services.redaction import redact

    text = "Build passed in 1.2s on main at commit a1b2c3d"
    assert redact(text) == text


def test_words_ending_in_key_are_not_redacted() -> None:
    from app.services.redaction import redact

    text = "MONKEY=banana turkey=roast"
    assert redact(text) == text
