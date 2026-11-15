from datetime import datetime, timedelta, timezone

import httpx

from app.core.config import get_settings
from app.core.db import normalize_db_url
from app.integrations.ml_client import MlClient, MlError, get_ml_client
from app.main import app


def _register_user(client, email: str, password: str = "password123", name: str = "User") -> dict:
    res = client.post(
        "/v1/auth/register",
        json={"email": email, "password": password, "display_name": name},
    )
    assert res.status_code == 201, res.text
    return res.json()


def test_01_authentication_and_logout_flow(client):
    tokens = _register_user(client, "auth_user@ngonsacviet.example.com")
    # Duplicate registration fails with 409
    dup = client.post(
        "/v1/auth/register",
        json={"email": "AUTH_USER@ngonsacviet.example.com", "password": "password123", "display_name": "Dup"},
    )
    assert dup.status_code == 409
    assert dup.json()["detail"]["code"] == "email_taken"

    # Invalid login fails with 401
    bad = client.post(
        "/v1/auth/login",
        json={"email": "auth_user@ngonsacviet.example.com", "password": "wrongpassword"},
    )
    assert bad.status_code == 401
    assert bad.json()["detail"]["code"] == "invalid_login"

    # Logout revokes refresh token
    out = client.post("/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert out.status_code == 204
    re_refresh = client.post("/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert re_refresh.status_code == 401


def test_02_authorization_token_type_and_rbac(client):
    tokens = _register_user(client, "rbac_member@ngonsacviet.example.com")
    # Refresh token cannot be used as Bearer access token
    bad_me = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {tokens['refresh_token']}"})
    assert bad_me.status_code == 401
    assert bad_me.json()["detail"]["code"] == "unauthorized"

    # Member cannot access moderation queue
    member_headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    q_res = client.get("/v1/contributions", headers=member_headers)
    assert q_res.status_code == 403
    assert q_res.json()["detail"]["code"] == "forbidden"


def test_03_user_change_password(client):
    tokens = _register_user(client, "pwd_user@ngonsacviet.example.com", password="OldPassword123")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # Wrong current password fails with 401
    wrong = client.post(
        "/v1/auth/change-password",
        headers=headers,
        json={"current_password": "WrongOldPassword", "new_password": "NewPassword456"},
    )
    assert wrong.status_code == 401
    assert wrong.json()["detail"]["code"] == "invalid_password"

    # Correct current password succeeds and revokes old refresh token
    ok = client.post(
        "/v1/auth/change-password",
        headers=headers,
        json={"current_password": "OldPassword123", "new_password": "NewPassword456"},
    )
    assert ok.status_code == 204

    old_refresh = client.post("/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert old_refresh.status_code == 401

    new_login = client.post(
        "/v1/auth/login",
        json={"email": "pwd_user@ngonsacviet.example.com", "password": "NewPassword456"},
    )
    assert new_login.status_code == 200


def test_04_05_06_catalog_languages_peoples_and_heritage(client):
    # Languages filter & detail
    ethnic_langs = client.get("/v1/languages", params={"role": "ethnic"}).json()
    assert len(ethnic_langs) == 5
    searched_langs = client.get("/v1/languages", params={"q": "Tày"}).json()
    assert len(searched_langs) == 1
    assert searched_langs[0]["code"] == "tyz"

    lang_detail = client.get("/v1/languages/tyz")
    assert lang_detail.status_code == 200
    assert lang_detail.json()["iso639_3"] == "tyz"
    assert client.get("/v1/languages/nonexistent").status_code == 404

    # Peoples filter, search & detail
    chamic = client.get("/v1/peoples", params={"family": "Chamic"}).json()
    assert {item["slug"] for item in chamic} == {"ede", "cham", "jrai"}

    tay_detail = client.get("/v1/peoples/tay")
    assert tay_detail.status_code == 200
    assert tay_detail.json()["language"]["code"] == "tyz"
    assert len(tay_detail.json()["heritage"]) >= 1
    assert client.get("/v1/peoples/nonexistent").status_code == 404

    # Heritage endpoint
    heritage_all = client.get("/v1/heritage").json()
    assert len(heritage_all) >= 5
    heritage_tay = client.get("/v1/heritage", params={"group_slug": "tay", "kind": "article"}).json()
    assert len(heritage_tay) == 1
    assert heritage_tay[0]["group_slug"] == "tay"


def test_07_08_09_translation_ocr_asr_validation_and_history(client):
    tokens = _register_user(client, "translator@ngonsacviet.example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # Unknown language rejected with 400
    bad_lang = client.post(
        "/v1/translate",
        headers=headers,
        json={"text": "Xin chào", "source_lang": "xyz", "target_lang": "vi"},
    )
    assert bad_lang.status_code == 400
    assert bad_lang.json()["detail"]["code"] == "unknown_language"

    # Authenticated translation saves to user history
    ok_trans = client.post(
        "/v1/translate",
        headers=headers,
        json={"text": "Xin chào", "source_lang": "vi", "target_lang": "en"},
    )
    assert ok_trans.status_code == 200

    # Empty image rejected with 400
    empty_img = client.post(
        "/v1/translate/image",
        headers=headers,
        data={"source_lang": "vi", "target_lang": "en"},
        files={"file": ("empty.png", b"", "image/png")},
    )
    assert empty_img.status_code == 400
    assert empty_img.json()["detail"]["code"] == "empty_file"

    # Invalid file type rejected with 400
    bad_ext = client.post(
        "/v1/translate/image",
        headers=headers,
        data={"source_lang": "vi", "target_lang": "en"},
        files={"file": ("malware.exe", b"MZ-fake", "application/x-msdownload")},
    )
    assert bad_ext.status_code == 400
    assert bad_ext.json()["detail"]["code"] == "invalid_file_type"

    # History endpoint returns user's translation logs
    history = client.get("/v1/translate/history", headers=headers)
    assert history.status_code == 200
    items = history.json()
    assert len(items) == 1
    assert items[0]["mode"] == "text"
    assert items[0]["source_text"] == "Xin chào"


def test_10_11_learning_quiz_and_progress_tracking(client):
    tokens = _register_user(client, "learner@ngonsacviet.example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    tay_lessons = client.get("/v1/lessons", params={"language": "tyz"}).json()
    assert len(tay_lessons) == 1
    lesson_id = tay_lessons[0]["id"]

    # Nonexistent lesson returns 404
    assert client.get("/v1/lessons/not-a-lesson").status_code == 404
    assert client.post("/v1/lessons/not-a-lesson/quiz", json={"answers": []}).status_code == 404

    # Submit quiz while logged in records progress
    detail = client.get(f"/v1/lessons/{lesson_id}").json()
    answers = [
        {"question_id": q["id"], "choice_id": q["choices"][0]["id"]}
        for q in detail["questions"]
    ]
    scored = client.post(f"/v1/lessons/{lesson_id}/quiz", headers=headers, json={"answers": answers})
    assert scored.status_code == 200
    assert scored.json()["total"] == 3

    progress = client.get("/v1/lessons/progress/me", headers=headers)
    assert progress.status_code == 200
    body = progress.json()
    assert body["lessons_attempted"] == 1
    assert len(body["history"]) == 1
    assert body["progress"][0]["lesson_id"] == lesson_id


def test_12_13_14_15_community_sync_and_filtered_export(client):
    user1 = _register_user(client, "contrib1@ngonsacviet.example.com")
    user2 = _register_user(client, "contrib2@ngonsacviet.example.com")
    h1 = {"Authorization": f"Bearer {user1['access_token']}"}
    h2 = {"Authorization": f"Bearer {user2['access_token']}"}

    # Same source and target language fails with 400
    same = client.post(
        "/v1/contributions",
        headers=h1,
        json={
            "client_id": "same-lang-001",
            "language_code": "tyz",
            "source_lang": "tyz",
            "target_lang": "tyz",
            "source_text": "a",
            "target_text": "b",
        },
    )
    assert same.status_code == 400
    assert same.json()["detail"]["code"] == "same_language"

    # Valid contribution by user1
    c1 = client.post(
        "/v1/contributions",
        headers=h1,
        json={
            "client_id": "unique-client-001",
            "language_code": "rad",
            "source_lang": "rad",
            "target_lang": "vi",
            "source_text": "kâo",
            "target_text": "tôi",
        },
    )
    assert c1.status_code == 201

    # Another user reusing the same client_id gets 409 client_id_taken
    conflict = client.post(
        "/v1/contributions",
        headers=h2,
        json={
            "client_id": "unique-client-001",
            "language_code": "rad",
            "source_lang": "rad",
            "target_lang": "vi",
            "source_text": "kâo",
            "target_text": "tôi",
        },
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "client_id_taken"

    # Mine endpoint returns user1's contribution
    mine = client.get("/v1/contributions/mine", headers=h1).json()
    assert any(item["client_id"] == "unique-client-001" for item in mine)

    # Reviewer filters queue and approves
    reviewer = client.post(
        "/v1/auth/login",
        json={"email": "demo@ngonsacviet.example.com", "password": "Demo1234"},
    ).json()
    rev_headers = {"Authorization": f"Bearer {reviewer['access_token']}"}
    rad_queue = client.get("/v1/contributions", params={"status": "pending", "language_code": "rad"}, headers=rev_headers)
    assert rad_queue.status_code == 200
    assert len(rad_queue.json()) >= 1

    rev_res = client.post(
        f"/v1/contributions/{c1.json()['id']}/review",
        headers=rev_headers,
        json={"status": "approved", "review_note": "Chuẩn Ê Đê"},
    )
    assert rev_res.status_code == 200

    # Filtered CSV export by language_code
    csv_rad = client.get("/v1/training/pairs.csv", params={"language_code": "rad"}, headers=rev_headers)
    assert csv_rad.status_code == 200
    assert "rad,vi,kâo,tôi,true" in csv_rad.text

    # Incremental sync pull with updated_after in the future returns empty approved_contributions
    future_iso = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    pull_future = client.get("/v1/sync/pull", params={"updated_after": future_iso}).json()
    assert pull_future["approved_contributions"] == []


def test_db_url_normalization_and_validation_error_format(client):
    assert normalize_db_url("postgres://u:p@host:5432/db") == "postgresql+asyncpg://u:p@host:5432/db"
    assert normalize_db_url("postgresql://u:p@host:5432/db") == "postgresql+asyncpg://u:p@host:5432/db"

    # RequestValidationError returns standardized 422 detail
    invalid = client.post("/v1/auth/register", json={"email": "not-an-email", "password": "short", "display_name": ""})
    assert invalid.status_code == 422
    detail = invalid.json()["detail"]
    assert detail["code"] == "validation_error"
    assert "errors" in detail

