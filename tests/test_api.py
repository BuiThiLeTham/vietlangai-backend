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


def test_google_login_requires_configuration(client):
    response = client.post("/v1/auth/google", json={"id_token": "not-a-real-google-token-value"})
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "google_not_configured"


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


class SpeechOnlyMl:
    """ASR exists for H'Mông, translation does not yet."""

    def __init__(self) -> None:
        self.translate_calls: list[dict] = []

    async def translate(self, body: dict) -> dict:
        from app.integrations.ml_client import MlError

        self.translate_calls.append(body)
        raise MlError(422, {"code": "model_not_ready", "message": "Chưa có mô hình."})

    async def asr(self, filename: str, content: bytes, content_type: str) -> dict:
        return {"text": "kuv mus tsev", "engine": "whisper", "language": "hmn", "warnings": ["Nghe lại."]}


def test_speech_keeps_transcript_when_translation_is_not_ready(client):
    from app.integrations.ml_client import get_ml_client
    from app.main import app

    fake = SpeechOnlyMl()
    app.dependency_overrides[get_ml_client] = lambda: fake
    response = client.post(
        "/v1/translate/speech",
        data={"target_lang": "vi"},
        files={"file": ("clip.m4a", b"fake-audio", "audio/mp4")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["recognized_text"] == "kuv mus tsev"
    assert body["text"] == ""
    assert body["source_lang"] == "hmn"
    assert body["detected_lang"] == "hmn"
    assert body["warnings"] == ["Nghe lại.", "Chưa có mô hình."]
    assert fake.translate_calls[0]["source_lang"] == "hmn"


class SpeechTranslationMl:
    """The checkpoint hears H'Mông and writes Vietnamese."""

    def __init__(self) -> None:
        self.translate_calls: list[dict] = []

    async def translate(self, body: dict) -> dict:
        self.translate_calls.append(body)
        return {"text": "I go home", "source_lang": body["source_lang"], "target_lang": body["target_lang"], "warnings": []}

    async def asr(self, filename: str, content: bytes, content_type: str) -> dict:
        return {
            "text": "tôi về nhà",
            "engine": "whisper",
            "language": "vi",
            "spoken_language": "hmn",
            "warnings": ["Dịch máy."],
        }


def test_speech_translation_uses_the_text_language(client):
    from app.integrations.ml_client import get_ml_client
    from app.main import app

    fake = SpeechTranslationMl()
    app.dependency_overrides[get_ml_client] = lambda: fake
    to_vi = client.post(
        "/v1/translate/speech",
        data={"target_lang": "vi", "source_lang": "hmn"},
        files={"file": ("clip.m4a", b"fake-audio", "audio/mp4")},
    ).json()
    assert to_vi["text"] == "tôi về nhà"
    assert to_vi["warnings"] == ["Dịch máy."]
    assert fake.translate_calls == []

    to_en = client.post(
        "/v1/translate/speech",
        data={"target_lang": "en", "source_lang": "tyz"},
        files={"file": ("clip.m4a", b"fake-audio", "audio/mp4")},
    ).json()
    assert fake.translate_calls[0]["source_lang"] == "vi"
    assert to_en["text"] == "I go home"
    assert to_en["recognized_text"] == "tôi về nhà"
    assert len(to_en["warnings"]) == 2


def test_lesson_hides_answer_key(client):
    lessons = client.get("/v1/lessons").json()
    detail = client.get(f"/v1/lessons/{lessons[0]['id']}").json()
    encoded = str(detail)
    assert "is_correct" not in encoded
    scored = client.post(f"/v1/lessons/{lessons[0]['id']}/quiz", json={"answers": []})
    assert scored.status_code == 200
    assert scored.json()["score"] == 0
    assert scored.json()["total"] == 3


def test_contribution_rejects_english_pair(client):
    member = _auth(client)
    headers = {"Authorization": f"Bearer {member['access_token']}"}
    rejected = client.post(
        "/v1/contributions",
        headers=headers,
        json={
            "client_id": "device-en-pair-001",
            "language_code": "tyz",
            "source_lang": "tyz",
            "target_lang": "en",
            "source_text": "pair_en",
            "target_text": "hello",
        },
    )
    assert rejected.status_code == 400
    assert rejected.json()["detail"]["code"] == "ethnic_vi_only"


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
    lessons = client.get("/v1/lessons", params={"language": "tyz"}).json()
    assert lessons
    lesson = client.get(f"/v1/lessons/{lessons[0]['id']}").json()
    assert any(
        phrase["native_text"] == "pair_a" and phrase["vi_text"] == "xin chào"
        for phrase in lesson["phrases"]
    )
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
