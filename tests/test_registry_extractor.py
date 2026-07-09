from app.extract.registry_extractor import (
    find_krs_numbers,
    find_nip_numbers,
    find_regon_numbers,
    is_valid_nip,
    is_valid_regon,
)

# Numery pochodzą z realnych organizacji (plik bazy użytkownika i dokumentacja źródłowa).


def test_is_valid_nip_accepts_real_numbers():
    assert is_valid_nip("5262149912")  # Fundacja Pomoc Polakom na Wschodzie
    assert is_valid_nip("7120104964")  # Towarzystwo Naukowe KUL
    assert is_valid_nip("5422697397")  # Fundacja na rzecz Pomocy Dzieciom z Grodzieńszczyzny


def test_is_valid_nip_rejects_bad_checksum():
    assert not is_valid_nip("1234567890")
    assert not is_valid_nip("123")


def test_is_valid_regon_accepts_real_number():
    assert is_valid_regon("010100610")  # Fundacja Pomoc Polakom na Wschodzie


def test_is_valid_regon_rejects_bad_checksum():
    assert not is_valid_regon("123456789")


def test_find_krs_nip_regon_from_real_meta_description():
    text = (
        'Fundacja "Pomoc Polakom na Wschodzie" im. Jana Olszewskiego Adres ul. Jazdów 10A, '
        "00-467 Warszawa E-mail biuro@pol.org.pl Tel./fax +48 22 628 55 57 KRS 0000130056 "
        "NIP 5262149912 Regon 010100610 Konto bankowe 17 1540 1287 2216 0009 2923 0001"
    )
    assert find_krs_numbers(text) == ["0000130056"]
    assert find_nip_numbers(text) == ["5262149912"]
    assert find_regon_numbers(text) == ["010100610"]


def test_find_nip_numbers_ignores_invalid_candidates():
    assert find_nip_numbers("NIP 1234567890") == []
