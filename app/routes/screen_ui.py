"""
Screening-only web UI: upload a customer file, screen every row, review the
report, download it as CSV. Runs entirely on the operator's machine.

This is the "shadow run" offer for obligated entities that cannot send data
to a third party. No database: results live in memory for the process
lifetime and are keyed by a random job id.
"""
from __future__ import annotations

import csv
import io
import logging
import secrets
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

from ..core.logger import log_audit_event
from ..services.aml_service import AMLService

logger = logging.getLogger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

_JOBS: Dict[str, Dict[str, Any]] = {}
_MAX_JOBS = 20
MAX_ROWS = 20000

# Header names we recognise, lowercase, punctuation-insensitive.
COLUMN_ALIASES = {
    "name": {"name", "full name", "fullname", "full_name", "customer name", "customer", "client name", "client", "beneficiary", "beneficiary name", "party", "counterparty", "entity name", "company", "company name"},
    "dob": {"dob", "date of birth", "date_of_birth", "birth date", "birthdate", "birthday", "born"},
    "nationality": {"nationality", "country", "citizenship", "nation", "country of nationality", "residence", "country of residence"},
    "entity_type": {"type", "entity type", "entity_type", "customer type", "kind", "party type"},
    "reference": {"id", "reference", "ref", "customer id", "customer_id", "client id", "account", "account no", "account number", "row"},
}


def _norm_header(h: str) -> str:
    return " ".join(str(h).strip().lower().replace("_", " ").replace("-", " ").split())


def detect_columns(headers: List[str]) -> Dict[str, Optional[str]]:
    found: Dict[str, Optional[str]] = {k: None for k in COLUMN_ALIASES}
    for h in headers:
        n = _norm_header(h)
        for field, names in COLUMN_ALIASES.items():
            if found[field] is None and n in names:
                found[field] = h
    return found


def read_table(filename: str, content: bytes) -> tuple[List[str], List[Dict[str, str]]]:
    """CSV or XLSX to (headers, rows of str)."""
    name = (filename or "").lower()
    if name.endswith((".xlsx", ".xlsm")):
        try:
            import openpyxl
        except ImportError:
            raise HTTPException(400, "XLSX support needs the openpyxl package; upload a CSV instead.")
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.active
        rows_iter = ws.iter_rows(values_only=True)
        headers = [str(h) if h is not None else f"col{i+1}" for i, h in enumerate(next(rows_iter, []) or [])]
        rows = []
        for r in rows_iter:
            if r is None or all(v in (None, "") for v in r):
                continue
            rows.append({headers[i]: ("" if v is None else str(v)) for i, v in enumerate(r) if i < len(headers)})
        return headers, rows
    text = content.decode("utf-8-sig", errors="replace")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    headers = reader.fieldnames or []
    rows = [{k: (v or "") for k, v in row.items() if k is not None} for row in reader]
    return list(headers), rows


def _entity_type(value: str) -> str:
    v = (value or "").strip().lower()
    if v in ("entity", "company", "organisation", "organization", "business", "corporate", "legal", "e", "c"):
        return "entity"
    if v in ("vessel", "ship", "v"):
        return "vessel"
    if v in ("any", "all", "*"):
        return "any"
    return "person"


def _remember(job: Dict[str, Any]) -> None:
    if len(_JOBS) >= _MAX_JOBS:
        oldest = min(_JOBS, key=lambda k: _JOBS[k]["created"])
        _JOBS.pop(oldest, None)
    _JOBS[job["id"]] = job


@router.get("/screen", response_class=HTMLResponse)
async def screen_form(request: Request):
    return templates.TemplateResponse("screen_upload.html", {"request": request, "error": None})


@router.post("/screen", response_class=HTMLResponse)
async def screen_upload(
    request: Request,
    file: UploadFile = File(...),
    name_col: str = Form(""),
    dob_col: str = Form(""),
    nat_col: str = Form(""),
    type_col: str = Form(""),
    ref_col: str = Form(""),
    default_type: str = Form("person"),
):
    content = await file.read()
    if not content:
        return templates.TemplateResponse("screen_upload.html", {"request": request, "error": "The file is empty."})
    try:
        headers, rows = read_table(file.filename or "", content)
    except HTTPException as e:
        return templates.TemplateResponse("screen_upload.html", {"request": request, "error": e.detail})
    if not headers or not rows:
        return templates.TemplateResponse("screen_upload.html", {"request": request, "error": "Could not find a header row and at least one data row."})
    if len(rows) > MAX_ROWS:
        return templates.TemplateResponse("screen_upload.html", {"request": request, "error": f"Too many rows ({len(rows)}). The limit is {MAX_ROWS} per file."})

    detected = detect_columns(headers)
    cols = {
        "name": name_col or detected["name"],
        "dob": dob_col or detected["dob"],
        "nationality": nat_col or detected["nationality"],
        "entity_type": type_col or detected["entity_type"],
        "reference": ref_col or detected["reference"],
    }
    if not cols["name"] or cols["name"] not in headers:
        # Ask the user to map columns
        return templates.TemplateResponse("screen_map.html", {
            "request": request, "headers": headers, "detected": detected, "filename": file.filename,
            "row_count": len(rows), "error": "Which column holds the name?",
        })

    t0 = time.time()
    results = []
    list_version = None
    for i, row in enumerate(rows, 1):
        name = (row.get(cols["name"]) or "").strip()
        if not name:
            continue
        dob = (row.get(cols["dob"]) or "").strip() if cols["dob"] else None
        nat = (row.get(cols["nationality"]) or "").strip() if cols["nationality"] else None
        et = _entity_type(row.get(cols["entity_type"]) or "") if cols["entity_type"] else _entity_type(default_type)
        ref = (row.get(cols["reference"]) or str(i)) if cols["reference"] else str(i)
        r = AMLService.screen_sync(name, dob=dob or None, nationality=nat or None, entity_type=et)
        list_version = r["list_version"]
        results.append({
            "row": i, "reference": ref, "name": name, "dob": dob or "", "nationality": nat or "",
            "entity_type": et, "match": r["sanctions_match"], "risk_score": r["risk_score"],
            "risk_level": r["risk_level"].value, "matches": r["matches"], "details": r["details"],
        })

    hits = [r for r in results if r["match"]]
    high = [r for r in hits if any(m["confidence"] == "high" for m in r["matches"])]
    job = {
        "id": secrets.token_urlsafe(8), "created": time.time(), "filename": file.filename,
        "list_version": list_version, "elapsed": round(time.time() - t0, 2),
        "total": len(results), "hits": len(hits), "high": len(high),
        "results": sorted(results, key=lambda r: (-r["risk_score"], r["row"])),
        "columns": cols,
    }
    _remember(job)
    log_audit_event(
        event_type="aml_batch_screening",
        data={"status": "success", "channel": "web_upload", "upload_filename": file.filename, "total": job["total"],
              "with_matches": job["hits"], "high_confidence": job["high"], "list_version": list_version},
        request=request,
    )
    return templates.TemplateResponse("screen_report.html", {"request": request, "job": job})


@router.get("/screen/{job_id}", response_class=HTMLResponse)
async def screen_report(request: Request, job_id: str):
    job = _JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Report not found (reports are kept in memory until the server restarts).")
    return templates.TemplateResponse("screen_report.html", {"request": request, "job": job})


@router.get("/screen/{job_id}/report.csv")
async def screen_report_csv(job_id: str):
    job = _JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Report not found")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["row", "reference", "name", "dob", "nationality", "entity_type", "match", "risk_score", "risk_level",
                "best_match_name", "matched_on", "match_type", "similarity", "confidence", "source", "program",
                "list_dob", "dob_agreement", "list_nationality", "country_match", "other_matches", "list_version"])
    for r in job["results"]:
        best = r["matches"][0] if r["matches"] else {}
        w.writerow([
            r["row"], r["reference"], r["name"], r["dob"], r["nationality"], r["entity_type"],
            "YES" if r["match"] else "no", r["risk_score"], r["risk_level"],
            best.get("sanctioned_name", ""), best.get("matched_name", ""), best.get("match_type", ""),
            best.get("similarity", ""), best.get("confidence", ""), best.get("source", ""), best.get("program", ""),
            "; ".join(best.get("dob") or []), best.get("dob_agreement", ""), best.get("country", ""),
            best.get("country_match", ""), len(r["matches"]) - 1 if r["matches"] else 0, job["list_version"],
        ])
    fname = f"screening_report_{job_id}.csv"
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


@router.get("/screen/sample/customers.csv")
async def sample_csv():
    sample = (
        "customer_id,full_name,date_of_birth,nationality,type\n"
        "C-1001,Maria Clara Santos,1991-06-12,PH,person\n"
        "C-1002,Ahmad Fuad Salim,1951-06-19,EG,person\n"
        "C-1003,Jonathan Whitfield,1979-02-03,GB,person\n"
        "C-1004,Bank Mellat,,IR,entity\n"
        "C-1005,Muhammad Reza Naghdi,1953-03-11,IR,person\n"
        "C-1006,Rahul Sharma,1988-11-30,IN,person\n"
    )
    return Response(sample, media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="sample_customers.csv"'})
