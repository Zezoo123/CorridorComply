"""Tests for the screening upload UI and batch API."""
import io

from app.routes.screen_ui import detect_columns, read_table


SAMPLE_CSV = (
    "customer_id,full_name,date_of_birth,nationality,type\n"
    "C-1,Maria Clara Santos,1985-02-14,PH,person\n"
    "C-2,Jonathan Whitfield,1979-02-03,GB,person\n"
    "C-3,Mellat Bank,,IR,entity\n"
    "C-4,Muhammad Reza Naghdi,1953-03-11,IR,person\n"
    "C-5,,1990-01-01,QA,person\n"
)


def test_detect_columns_recognises_common_headers():
    d = detect_columns(["Customer ID", "Full Name", "Date of Birth", "Country", "Type"])
    assert d == {"name": "Full Name", "dob": "Date of Birth", "nationality": "Country",
                 "entity_type": "Type", "reference": "Customer ID"}


def test_read_table_sniffs_semicolons():
    headers, rows = read_table("x.csv", b"name;dob\nA B;1990-01-01\n")
    assert headers == ["name", "dob"] and rows == [{"name": "A B", "dob": "1990-01-01"}]


def test_read_table_xlsx():
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["name", "nationality"])
    ws.append(["Jonathan Whitfield", "GB"])
    buf = io.BytesIO()
    wb.save(buf)
    headers, rows = read_table("customers.xlsx", buf.getvalue())
    assert headers == ["name", "nationality"] and rows[0]["name"] == "Jonathan Whitfield"


def test_upload_page_renders(client):
    r = client.get("/screen")
    assert r.status_code == 200 and "Screen a customer file" in r.text


def test_upload_screens_rows_and_downloads_csv(client):
    r = client.post("/screen", files={"file": ("customers.csv", SAMPLE_CSV, "text/csv")})
    assert r.status_code == 200
    assert "Screening report" in r.text
    assert "MOHAMMAD REZA NAQDI" in r.text          # alias hit
    assert "BANK MELLAT" in r.text                  # entity typed row
    assert "Jonathan Whitfield" in r.text
    # 4 screened rows (the blank-name row is skipped); 2 hits: the Naqdi alias and the Mellat entity.
    # "Maria Clara Santos" scores below the threshold against "MARIA SANTOS" (extra given name).
    assert "<b>4</b>" in r.text and "<b>2</b>" in r.text
    job_id = r.text.split("report id <code>")[1].split("</code>")[0]

    csv_r = client.get(f"/screen/{job_id}/report.csv")
    assert csv_r.status_code == 200
    lines = csv_r.text.strip().splitlines()
    assert lines[0].startswith("row,reference,name")
    assert len(lines) == 5
    assert any("MOHAMMAD REZA NAGHDI" in line and "alias" in line for line in lines)

    assert client.get(f"/screen/{job_id}").status_code == 200
    assert client.get("/screen/does-not-exist").status_code == 404


def test_upload_without_name_column_asks_for_mapping(client):
    r = client.post("/screen", files={"file": ("x.csv", "colA,colB\nfoo,bar\n", "text/csv")})
    assert r.status_code == 200 and "Map the columns" in r.text


def test_upload_with_explicit_mapping(client):
    r = client.post("/screen", data={"name_col": "colA"}, files={"file": ("x.csv", "colA,colB\nAbdul Rahman Yasin,bar\n", "text/csv")})
    assert r.status_code == 200 and "ABDUL RAHMAN YASIN" in r.text


def test_sample_file(client):
    r = client.get("/screen/sample/customers.csv")
    assert r.status_code == 200 and r.text.startswith("customer_id,full_name")


def test_batch_api(client):
    payload = {"items": [
        {"reference": "a", "full_name": "Jonathan Whitfield"},
        {"reference": "b", "full_name": "Abdul Rahman Yasin", "dob": "1960-04-10", "nationality": "IQ"},
        {"reference": "c", "full_name": "Bank Mellat", "entity_type": "entity"},
    ]}
    r = client.post("/api/v1/aml/screen/batch", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3 and body["with_matches"] == 2
    by_ref = {x["reference"]: x for x in body["results"]}
    assert by_ref["a"]["sanctions_match"] is False
    assert by_ref["b"]["matches"][0]["dob_agreement"] == "exact"
    assert by_ref["c"]["matches"][0]["record_type"] == "entity"
    assert body["list_version"]
