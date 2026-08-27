"""Test cases for the Health endpoint (GET /api/v1/health)."""

import allure
import pytest

pytestmark = allure.feature("Health")


@allure.title("API and database are up")
@allure.tag("HLT-01")
@allure.severity(allure.severity_level.BLOCKER)
@pytest.mark.smoke
def test_health_reports_api_and_database_are_up(api):
    response = api.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"


@allure.title("Health response identifies a non-production environment")
@allure.tag("HLT-02")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.smoke
def test_health_identifies_the_environment_under_test(api):
    """Guards against the suite silently running against prod."""
    body = api.get("/health").json()

    assert body["environment"], "Health response does not name an environment"
    assert body["environment"].lower() not in {"production", "prod"}
    assert body["version"], "Health response does not report a version"
