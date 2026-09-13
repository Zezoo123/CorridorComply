"""HTTP Basic login on the web UI."""


def test_ui_open_without_credentials_configured(client, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "UI_USERNAME", "")
    monkeypatch.setattr(config, "UI_PASSWORD", "")
    assert client.get("/screen").status_code == 200


def test_ui_requires_login_when_configured(client, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "UI_USERNAME", "mlro")
    monkeypatch.setattr(config, "UI_PASSWORD", "s3cret")
    r = client.get("/screen")
    assert r.status_code == 401 and "Basic" in r.headers.get("www-authenticate", "")
    assert client.get("/review", auth=("mlro", "wrong")).status_code == 401
    assert client.get("/review", auth=("mlro", "s3cret")).status_code == 200
    # the API is unaffected by the UI login
    assert client.get("/health").status_code == 200
    assert client.post("/api/v1/aml/screen", json={"full_name": "Jonathan Whitfield"}).status_code == 200
