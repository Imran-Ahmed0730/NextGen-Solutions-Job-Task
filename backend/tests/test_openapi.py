from app.main import app


def test_openapi_describes_versioned_public_and_protected_endpoints() -> None:
    schema = app.openapi()

    assert schema["info"]["title"] == "Sabuj Pran API"
    assert schema["openapi"].startswith("3.")
    assert "/api/v1/auth/login" in schema["paths"]
    assert "/api/v1/auth/me" in schema["paths"]
    assert "/api/v1/purchase/orders" in schema["paths"]
    assert "/api/v1/reports/dashboard" in schema["paths"]

    login = schema["paths"]["/api/v1/auth/login"]["post"]
    profile = schema["paths"]["/api/v1/auth/me"]["get"]
    dashboard = schema["paths"]["/api/v1/reports/dashboard"]["get"]

    assert "security" not in login
    assert profile["security"]
    assert dashboard["security"]
    assert schema["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"
