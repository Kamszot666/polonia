"""Testy wykrywania adresu siedziby w treści strony.

Przykłady odwzorowują realne zapisy ze stron organizacji polonijnych - w tym ten
z meta og:description na pol.org.pl, gdzie adres stoi bez separatora zaraz przy etykiecie
kolejnego pola („00-467 Warszawa E-mail biuro@...").
"""

from app.extract.address_extractor import find_address


def test_finds_full_address_from_real_meta_description():
    text = (
        'Fundacja "Pomoc Polakom na Wschodzie" Adres ul. Jazdów 10A, 00-467 Warszawa '
        "E-mail biuro@pol.org.pl Tel./fax +48 22 628 55 57"
    )
    assert find_address(text) == "ul. Jazdów 10A, 00-467 Warszawa"


def test_keeps_apartment_number():
    assert find_address("al. Jerozolimskie 30 lok. 8, 00-024 Warszawa") == (
        "al. Jerozolimskie 30 lok. 8, 00-024 Warszawa"
    )
    assert find_address("ul. Krakowskie Przedmieście 64/3, 00-322 Warszawa") == (
        "ul. Krakowskie Przedmieście 64/3, 00-322 Warszawa"
    )


def test_handles_two_word_city_names():
    assert find_address("ul. Rynek 5, 33-300 Nowy Sącz tel. 18 444 55 66") == (
        "ul. Rynek 5, 33-300 Nowy Sącz"
    )
    assert find_address("ul. Główna 2, 65-001 Zielona Góra") == "ul. Główna 2, 65-001 Zielona Góra"


def test_strips_label_glued_before_street():
    assert find_address("Siedziba: pl. Zamkowy 1, 00-001 Warszawa") == "pl. Zamkowy 1, 00-001 Warszawa"


def test_falls_back_to_postal_code_and_city():
    assert find_address("Korespondencja: 20-950 Lublin") == "20-950 Lublin"


def test_ignores_street_without_building_number():
    assert find_address("Mieszkamy przy ulicy Polnej, zapraszamy") is None


def test_returns_none_without_address():
    assert find_address("Zapraszamy na spotkanie o 15:00") is None
