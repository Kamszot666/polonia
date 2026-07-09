from app.extract.phone_extractor import find_phones


def test_find_phones_detects_polish_landline():
    text = "Zadzwoń do nas: 22 556 90 02"
    phones = find_phones(text)
    assert "+48225569002" in phones


def test_find_phones_detects_international_format():
    text = "Telefon: +48 22 628 55 57"
    phones = find_phones(text)
    assert "+48226285557" in phones


def test_find_phones_ignores_non_phone_numbers():
    text = "NIP 5260300368, REGON 000779213"
    assert find_phones(text) == []


def test_find_phones_deduplicates():
    text = "Telefon: +48 22 556 90 02, tel. 22 556 90 02"
    assert find_phones(text) == ["+48225569002"]
