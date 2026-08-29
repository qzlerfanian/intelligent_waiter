import pytest


@pytest.mark.parametrize("path,headers", [
    ("/api/v1/organizations/branches/", "authorization,content-type,x-organization-id"),
    ("/api/v1/customer/orders/confirm/", "content-type,x-table-session,idempotency-key"),
    ("/api/v1/staff/orders/", "authorization,x-organization-id,x-request-id"),
])
def test_frontend_preflight_allows_application_headers(client, settings, path, headers):
    settings.CORS_ALLOWED_ORIGINS = ["http://localhost:5173"]
    response = client.options(
        path,
        HTTP_ORIGIN="http://localhost:5173",
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
        HTTP_ACCESS_CONTROL_REQUEST_HEADERS=headers,
    )
    assert response.status_code == 200
    assert response["Access-Control-Allow-Origin"] == "http://localhost:5173"
    allowed = {value.strip().lower() for value in response["Access-Control-Allow-Headers"].split(",")}
    assert set(headers.split(",")) <= allowed


def test_untrusted_origin_is_not_allowed(client, settings):
    settings.CORS_ALLOWED_ORIGINS = ["http://localhost:5173"]
    response = client.options(
        "/api/v1/organizations/branches/",
        HTTP_ORIGIN="https://untrusted.example",
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
        HTTP_ACCESS_CONTROL_REQUEST_HEADERS="x-organization-id",
    )
    assert "Access-Control-Allow-Origin" not in response
