def _auth(client, email="member@ngonsacviet.example.com"):
    response = client.post(
        "/v1/auth/register",
        json={"email": email, "password": "password1", "display_name": "Member"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_health_and_five_peoples(client):
    assert client.get("/health").json()["status"] == "ok"
    peoples = client.get("/v1/peoples").json()
    assert {row["slug"] for row in peoples} == {"tay", "ede", "cham", "hmong", "jrai"}
    assert len(client.get("/v1/languages").json()) == 7


def test_register_refresh_rotation(client):
    tokens = _auth(client)
    me = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200
    assert me.json()["role"] == "member"
    refreshed = client.post("/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refreshed.status_code == 200
    reused = client.post("/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert reused.status_code == 401


def test_translate_text_and_image_fallback(client):
    text = client.post("/v1/translate", json={"text": "Xin chào", "source_lang": "vi", "target_lang": "en"})
    assert text.status_code == 200
    assert text.json()["text"] == "Hello"
    image = client.post(
        "/v1/translate/image",
        data={"source_lang": "vi", "target_lang": "en"},
        files={"file": ("note.png", b"fake-image", "image/png")},
    )
    assert image.status_code == 200
    assert image.json()["recognized_text"] == "xin chào"


def test_lesson_hides_answer_key(client):
    lessons = client.get("/v1/lessons").json()
    detail = client.get(f"/v1/lessons/{lessons[0]['id']}").json()
    encoded = str(detail)
    assert "is_correct" not in encoded
    scored = client.post(f"/v1/lessons/{lessons[0]['id']}/quiz", json={"answers": []})
    assert scored.status_code == 200
    assert scored.json()["score"] == 0
    assert scored.json()["total"] == 3


def test_contribution_is_reviewed_before_training_export(client):
    member = _auth(client)
    headers = {"Authorization": f"Bearer {member['access_token']}"}
    created = client.post(
        "/v1/contributions",
        headers=headers,
        json={
            "client_id": "device-pair-001",
            "language_code": "tyz",
            "source_lang": "tyz",
            "target_lang": "vi",
            "source_text": "pair_a",
            "target_text": "xin chào",
            "note": "Câu đã đối chiếu với người nói, đây là mã thử luồng duyệt.",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["status"] == "pending"
    forbidden = client.get("/v1/training/pairs.csv", headers=headers)
    assert forbidden.status_code == 403
    reviewer = client.post(
        "/v1/auth/login",
        json={"email": "demo@ngonsacviet.example.com", "password": "Demo1234"},
    ).json()
    review_headers = {"Authorization": f"Bearer {reviewer['access_token']}"}
    decision = client.post(
        f"/v1/contributions/{created.json()['id']}/review",
        headers=review_headers,
        json={"status": "approved", "review_note": "Đối chiếu thử nghiệm luồng."},
    )
    assert decision.status_code == 200
    exported = client.get("/v1/training/pairs.csv", headers=review_headers)
    assert exported.status_code == 200
    assert "tyz,vi,pair_a,xin chào,true" in exported.text
    again = client.post(
        "/v1/sync/push",
        headers=headers,
        json={
            "contributions": [
                {
                    "client_id": "device-pair-001",
                    "language_code": "tyz",
                    "source_lang": "tyz",
                    "target_lang": "vi",
                    "source_text": "pair_a",
                    "target_text": "xin chào",
                }
            ]
        },
    )
    assert again.status_code == 200
    assert again.json()["contributions"][0]["status"] == "approved"


def test_pull_contains_catalog(client):
    payload = client.get("/v1/sync/pull").json()
    assert len(payload["peoples"]) == 5
    assert len(payload["lessons"]) == 5
    assert payload["approved_contributions"] == []
