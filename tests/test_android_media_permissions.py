from pathlib import Path
from xml.etree import ElementTree


ANDROID_NAMESPACE = "{http://schemas.android.com/apk/res/android}"


def test_android_declares_direct_media_and_location_permissions() -> None:
    manifest = ElementTree.parse("android/app/src/main/AndroidManifest.xml").getroot()
    permissions = {
        element.attrib[f"{ANDROID_NAMESPACE}name"]: element.attrib
        for element in manifest.findall("uses-permission")
    }

    assert "android.permission.ACCESS_MEDIA_LOCATION" in permissions
    assert "android.permission.READ_MEDIA_IMAGES" in permissions
    assert "android.permission.READ_MEDIA_VIDEO" in permissions
    assert "android.permission.READ_MEDIA_VISUAL_USER_SELECTED" in permissions
    assert permissions["android.permission.READ_EXTERNAL_STORAGE"][
        f"{ANDROID_NAMESPACE}maxSdkVersion"
    ] == "32"
