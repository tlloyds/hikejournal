import json
from pathlib import Path


def test_cloud_build_uses_supported_logging_and_deploys_cloud_run() -> None:
    config = json.loads(Path("cloudbuild.json").read_text(encoding="utf-8"))

    assert config["options"]["logging"] == "CLOUD_LOGGING_ONLY"
    assert config["substitutions"] == {
        "_REGION": "us-east1",
        "_ARTIFACT_REPOSITORY": "cloud-run-source-deploy",
        "_IMAGE_PATH": "tlloyds-hikejournal/hikejournal-git",
        "_SERVICE_NAME": "hikejournal-git",
    }

    docker_build, docker_push, cloud_run_deploy = config["steps"]
    assert docker_build["args"][0] == "build"
    assert docker_push["args"][0] == "push"
    assert cloud_run_deploy["entrypoint"] == "gcloud"
    assert cloud_run_deploy["args"][:3] == ["run", "deploy", "${_SERVICE_NAME}"]
    assert "--region" in cloud_run_deploy["args"]
    assert "--quiet" in cloud_run_deploy["args"]
