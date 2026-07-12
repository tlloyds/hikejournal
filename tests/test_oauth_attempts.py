from hike_journal import config


def test_oauth_attempt_is_user_bound_and_can_complete(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config, "INAT_OAUTH_ATTEMPTS_PATH", tmp_path / "oauth_attempts.json")

    created = config.create_inat_oauth_attempt(
        subject="google-user-1",
        email="Hiker@example.com",
    )

    pending = config.get_inat_oauth_attempt(created["state"])
    assert pending is not None
    assert pending["status"] == "pending"
    assert pending["subject"] == "google-user-1"
    assert pending["email"] == "hiker@example.com"

    config.complete_inat_oauth_attempt(created["state"])

    completed = config.get_inat_oauth_attempt(created["state"])
    assert completed is not None
    assert completed["status"] == "completed"
    assert completed.get("completed_at")
