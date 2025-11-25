import easyocr
from mrz_detect import main as mrz_main
from mrz.checker.td3 import TD3CodeChecker


def parse_mrz(mrz_text: str) -> dict:
    try:
        td3_check = TD3CodeChecker(mrz_text)
        if not td3_check.fields:
            return {"error": "Invalid MRZ format"}
        fields = td3_check.fields()
        return {
            "document_type": fields.document_type,
            "country_code": fields.country,
            "surname": fields.surname,
            "given_names": fields.name,
            "document_number": fields.document_number,
            "nationality": fields.nationality,
            "birth_date": fields.birth_date,  # YYMMDD format
            "sex": fields.sex,
            "expiry_date": fields.expiry_date, # YYMMDD format
            "valid_composite": bool(td3_check) # Checksums check
        }
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    file = "../../tests/data/sample_passports/canada.jpg"
    mrz_image = mrz_main(file)
    reader = easyocr.Reader(['en'], gpu=False)
    results = reader.readtext(mrz_image, detail=0)
    mrz_text = "\n".join(results)
    mrz_text = mrz_text.upper().replace(" ", "").strip()
    print(f"\nMRZ Text:\n{mrz_text}\n")
    print(f"\nParsed Data:\n {parse_mrz(mrz_text)}")