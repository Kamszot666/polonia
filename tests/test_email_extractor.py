from app.extract.email_extractor import find_emails, score_email


def test_find_emails_extracts_valid_addresses():
    text = "Kontakt: biuro@fundacja.org.pl lub sekretariat@przyklad.pl."
    emails = find_emails(text)
    assert "biuro@fundacja.org.pl" in emails
    assert "sekretariat@przyklad.pl" in emails


def test_find_emails_ignores_invalid_syntax():
    text = "To nie jest e-mail: czlowiek@@blad, ani to: test@.pl"
    assert find_emails(text) == []


def test_find_emails_strips_trailing_punctuation():
    text = "Napisz na adres@example.com."
    assert find_emails(text) == ["adres@example.com"]


def test_score_email_low_value_local_part():
    assert score_email("noreply@example.com") < score_email("kontakt@example.com")


def test_score_email_high_value_local_part():
    assert score_email("biuro@example.com") > score_email("jan.kowalski@example.com")
