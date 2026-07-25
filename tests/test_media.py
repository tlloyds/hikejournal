from hike_journal.media import is_supported_video_upload, is_video, video_content_type


def test_recognizes_common_phone_video_uploads() -> None:
    assert is_supported_video_upload("trail.MOV", "")
    assert is_supported_video_upload("clip.mp4", "video/mp4")
    assert is_supported_video_upload("moment.3gp", "video/3gpp")
    assert not is_supported_video_upload("field-note.jpg", "image/jpeg")


def test_identifies_video_records_and_content_types() -> None:
    assert is_video({"content_type": "video/quicktime"})
    assert not is_video({"content_type": "image/jpeg"})
    assert video_content_type("trail.mov") == "video/quicktime"
    assert video_content_type("trail.mp4", "video/mp4") == "video/mp4"
