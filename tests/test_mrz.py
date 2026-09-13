"""MRZ parsing for passports (TD3) and ID cards (TD1). Text-level; no images or models."""
import pytest

mrz_mod = pytest.importorskip("mrz")  # pure-python, but keep the guard for minimal installs
from app.core.ocr import parse_mrz, mrz_format_for, assemble_mrz_text, mrz_yymmdd_to_iso, compare_mrz_with_request_data

TD1 = "I<UTOD231458907<<<<<<<<<<<<<<<\n7408122F1204159UTO<<<<<<<<<<<6\nERIKSSON<<ANNA<MARIA<<<<<<<<<<"
TD3 = "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<\nL898902C36UTO7408122F1204159ZE184226B<<<<<10"


def test_format_detection():
    assert mrz_format_for(TD1) == "TD1"
    assert mrz_format_for(TD3) == "TD3"
    assert mrz_format_for("garbage") is None


def test_td1_parses_with_checksums():
    d = parse_mrz(TD1)
    assert d["format"] == "TD1" and "error" not in d
    assert d["surname"] == "ERIKSSON" and d["given_names"] == "ANNA MARIA"
    assert d["document_number"] == "D23145890" and d["nationality"] == "UTO"
    assert d["birth_date"] == "740812" and d["birth_date_iso"] == "1974-08-12"
    assert d["expiry_date_iso"] == "2012-04-15"
    assert d["valid_composite"] is True and all(d["checks"].values())
    assert {"document_number", "birth_date", "expiry_date", "final"} <= set(d["checks"])


def test_td3_still_parses():
    d = parse_mrz(TD3)
    assert d["format"] == "TD3" and d["surname"] == "ERIKSSON" and d["valid_composite"] is True


def test_td1_checksum_failure_is_per_field():
    bad = TD1.replace("D231458907", "D231458908")  # break the document-number check digit
    d = parse_mrz(bad)
    assert "error" not in d
    assert d["checks"]["document_number"] is False and d["valid_composite"] is False


def test_assemble_from_ocr_lines_td1_and_td3():
    lines = [ln.replace("<", "<") for ln in TD1.split("\n")]
    multi, single, fmt = assemble_mrz_text(lines)
    assert fmt == "TD1" and len(single) == 90 and multi.count("\n") == 2
    assert parse_mrz(multi, fmt)["surname"] == "ERIKSSON"
    multi, single, fmt = assemble_mrz_text(TD3.split("\n"))
    assert fmt == "TD3" and len(single) == 88


def test_birth_century_and_expiry():
    assert mrz_yymmdd_to_iso("740812", "birth") == "1974-08-12"
    assert mrz_yymmdd_to_iso("150101", "birth") == "2015-01-01"
    assert mrz_yymmdd_to_iso("300101", "expiry") == "2030-01-01"
    assert mrz_yymmdd_to_iso("xx", "birth") is None


def test_compare_uses_1900s_for_old_birth_dates():
    d = parse_mrz(TD1)
    cmp = compare_mrz_with_request_data(d, {"document_number": "D23145890", "first_name": "Anna", "last_name": "Eriksson",
                                            "date_of_birth": "1974-08-12", "nationality": "UTO", "expiry_date": "2012-04-15",
                                            "issuing_country": "UTO"})
    assert cmp["all_match"] is True and cmp["match_count"] == 7


def test_validate_document_ocr_uses_td1_for_id_cards(monkeypatch):
    """Route an id_card through the MRZ path with the OCR reader mocked."""
    pytest.importorskip("easyocr")
    import numpy as np
    from PIL import Image
    from app.core import ocr
    monkeypatch.setattr(ocr, "extract_mrz_from_image", lambda img: np.zeros((10, 10), dtype="uint8"))
    class Reader:
        def readtext(self, img, detail=0):
            return TD1.split("\n")
    from app.core import id_ocr
    monkeypatch.setattr(id_ocr, "get_ocr_reader", lambda: Reader())
    result = ocr.validate_document_ocr(Image.new("RGB", (400, 250)), document_type="id_card", country_code="QA")
    assert result["mrz_data"]["format"] == "TD1" and result["mrz_data"]["surname"] == "ERIKSSON"
    assert result["expiry_validation"]["is_expired"] is True   # 2012
    assert result["valid"] is False and "expired" in result["details"][-1].lower()
