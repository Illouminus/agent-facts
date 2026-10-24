"""Google service-account keys: parsing, the signed JWT, the token exchange (no real network)."""

import base64
import json
from datetime import UTC, datetime

import httpx
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from werkzeug import Request, Response

from agentfacts.probe.google_sa import (
    GOOGLE_TOKEN_URL,
    JWT_BEARER,
    AuthError,
    mint_access_token,
    parse_service_account,
    secrets_of,
    signed_assertion,
)
from agentfacts.probe.http import make_client

NOW = datetime(2026, 10, 24, 10, 0, 0, tzinfo=UTC)
SCOPES = ("https://www.googleapis.com/auth/datastore",)
ACCESS = "ya29.FAKEaccessTOKENfakeFAKEfake0123"


@pytest.fixture(scope="module")
def rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def sa_json(rsa_key, **overrides) -> str:
    pem = rsa_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    doc = {
        "type": "service_account",
        "project_id": "agent-facts-test",
        "private_key_id": "0123456789abcdef0123456789abcdef01234567",
        "private_key": pem,
        "client_email": "probe@agent-facts-test.iam.gserviceaccount.com",
        "client_id": "123456789012345678901",
        "token_uri": GOOGLE_TOKEN_URL,
    }
    doc.update(overrides)
    return json.dumps({k: v for k, v in doc.items() if v is not None})


def b64json(part: str) -> dict:
    return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))


def verify(jwt: str, public_key) -> tuple[dict, dict]:
    head, body, signature = jwt.split(".")
    public_key.verify(
        base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4)),
        f"{head}.{body}".encode(),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return b64json(head), b64json(body)


def test_signed_assertion_is_an_rs256_jwt_for_the_token_url(rsa_key):
    sa = parse_service_account(sa_json(rsa_key))
    header, claims = verify(signed_assertion(sa, SCOPES, NOW), rsa_key.public_key())
    assert header == {"alg": "RS256", "typ": "JWT", "kid": sa.private_key_id}
    assert claims == {
        "iss": "probe@agent-facts-test.iam.gserviceaccount.com",
        "scope": SCOPES[0],
        "aud": GOOGLE_TOKEN_URL,
        "iat": int(NOW.timestamp()),
        "exp": int(NOW.timestamp()) + 3600,
    }


def test_several_scopes_are_space_separated(rsa_key):
    sa = parse_service_account(sa_json(rsa_key))
    scopes = (*SCOPES, "https://www.googleapis.com/auth/spreadsheets.readonly")
    _, claims = verify(signed_assertion(sa, scopes, NOW), rsa_key.public_key())
    assert claims["scope"] == " ".join(scopes)


@pytest.mark.parametrize(
    "overrides",
    [
        {"type": "authorized_user"},
        {"client_email": None},
        {"private_key": None},
        {"private_key": "not a pem"},
        {"private_key_id": None},
        {"token_uri": "https://evil.example/token"},
        {"client_email": "a b@x"},
    ],
)
def test_bad_key_files_are_refused_without_their_content(rsa_key, overrides):
    raw = sa_json(rsa_key, **overrides)
    with pytest.raises(AuthError) as exc:
        parse_service_account(raw)
    assert exc.value.code == "bad_key_file"
    assert "PRIVATE KEY" not in str(exc.value) and "evil" not in str(exc.value)


@pytest.mark.parametrize("raw", ["", "not json", "[1]", '{"type": "service_account"'])
def test_non_json_key_files_are_refused(raw):
    with pytest.raises(AuthError) as exc:
        parse_service_account(raw)
    assert exc.value.code == "bad_key_file"


def test_a_key_without_token_uri_is_accepted(rsa_key):
    assert parse_service_account(sa_json(rsa_key, token_uri=None)).client_email


def test_secrets_cover_the_file_the_pem_and_its_id(rsa_key):
    raw = sa_json(rsa_key)
    sa = parse_service_account(raw)
    found = secrets_of(raw)
    assert {raw, sa.private_key, sa.private_key_id} <= found
    assert json.dumps(sa.private_key)[1:-1] in found  # the PEM as escaped inside the JSON
    body = [line for line in sa.private_key.splitlines() if "PRIVATE KEY" not in line]
    assert all(line in found for line in body if len(line) >= 16)
    assert secrets_of("not json") == {"not json"}


def test_mint_trades_the_assertion_for_an_access_token(rsa_key, httpserver):
    sa = parse_service_account(sa_json(rsa_key))
    seen = []

    def token(request: Request) -> Response:
        seen.append(request)
        assert request.form["grant_type"] == JWT_BEARER
        verify(request.form["assertion"], rsa_key.public_key())
        body = {"access_token": ACCESS, "expires_in": 3599, "token_type": "Bearer"}
        return Response(json.dumps(body), 200, content_type="application/json")

    httpserver.expect_request("/token", method="POST").respond_with_handler(token)
    with make_client() as client:
        assert mint_access_token(client, sa, SCOPES, NOW, httpserver.url_for("/token")) == ACCESS
    assert seen[0].headers["User-Agent"].startswith("agent-facts-probe/")


@pytest.mark.parametrize(
    ("status", "body", "detail"),
    [
        (400, {"error": "invalid_grant", "error_description": "Invalid JWT Signature."},
         "400 invalid_grant"),
        (401, {"error": "unauthorized_client"}, "401 unauthorized_client"),
        (200, {"token_type": "Bearer"}, "200 no access_token"),
        (500, {"error": "x" * 200}, "500"),
        (302, {}, "302"),
    ],
)
def test_mint_failures_are_auth_errors(rsa_key, httpserver, status, body, detail):
    sa = parse_service_account(sa_json(rsa_key))
    httpserver.expect_request("/token").respond_with_json(body, status=status)
    with make_client() as client, pytest.raises(AuthError) as exc:
        mint_access_token(client, sa, SCOPES, NOW, httpserver.url_for("/token"))
    assert (exc.value.code, exc.value.message) == ("token_exchange", detail)


def test_mint_transport_error_is_an_auth_error(rsa_key):
    sa = parse_service_account(sa_json(rsa_key))
    with httpx.Client(timeout=1.0, trust_env=False) as client, pytest.raises(AuthError) as exc:
        mint_access_token(client, sa, SCOPES, NOW, "http://127.0.0.1:9/token")
    assert (exc.value.code, exc.value.message) == ("token_exchange", "connect_error")
