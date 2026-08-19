from pathlib import Path
from xml.etree import ElementTree


ANDROID_NAMESPACE = "{http://schemas.android.com/apk/res/android}"


def test_android_uses_system_picker_without_broad_media_permissions() -> None:
    manifest = ElementTree.parse("android/app/src/main/AndroidManifest.xml").getroot()
    permissions = {
        element.attrib[f"{ANDROID_NAMESPACE}name"]: element.attrib
        for element in manifest.findall("uses-permission")
    }

    assert "android.permission.ACCESS_MEDIA_LOCATION" in permissions
    assert "android.permission.READ_MEDIA_IMAGES" not in permissions
    assert "android.permission.READ_MEDIA_VIDEO" not in permissions
    assert "android.permission.READ_MEDIA_VISUAL_USER_SELECTED" not in permissions
    assert "android.permission.READ_EXTERNAL_STORAGE" not in permissions

    app = Path("android/app/src/main/java/com/hikejournal/app/ui/HikeJournalApp.kt").read_text()
    assert "PickMultipleVisualMedia" in app
    assert "PickVisualMedia.ImageAndVideo" in app
