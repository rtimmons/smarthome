"""Integration tests for the printer service web interface."""

import json
import pytest
from printer_service.app import create_app


@pytest.fixture
def app():
    """Create test app."""
    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


class TestBlueyLabelIntegration:
    """Test Bluey label functionality end-to-end."""

    def test_bluey_label_form_renders_with_url_params(self, client):
        """Test that the form is populated with URL parameters."""
        response = client.get(
            "/bb?Line1=Test&Line2=Label&Side=TL&Between=middle&Bottom=12/11/25&Inversion=25&tpl=bluey_label"
        )
        assert response.status_code == 200

        # Check that form fields are populated with URL parameter values
        html = response.get_data(as_text=True)
        assert 'value="Test"' in html  # Line1
        assert 'value="Label"' in html  # Line2
        assert 'value="TL"' in html  # Side
        assert 'value="middle"' in html  # Between
        assert 'value="12/11/25"' in html  # Bottom
        assert 'value="25"' in html  # Inversion

    def test_bluey_label_preview_api_with_new_fields(self, client):
        """Test preview API with new field names."""
        payload = {
            "template": "bluey_label",
            "data": {
                "Line1": "Test",
                "Line2": "Label",
                "Side": "TL",
                "Between": "middle",
                "Bottom": "12/11/25",
                "Inversion": "25",
            },
        }

        response = client.post(
            "/bb/preview", data=json.dumps(payload), content_type="application/json"
        )
        assert response.status_code == 200

        data = response.get_json()
        assert data["template"] == "bluey_label"
        assert data["status"] == "preview"
        assert "label" in data
        assert "image" in data["label"]

    def test_bluey_label_preview_api_with_old_fields(self, client):
        """Test preview API with old field names for backward compatibility."""
        payload = {
            "template": "bluey_label",
            "data": {
                "Line1": "Test",
                "Line2": "Label",
                "Initials": "TL",
                "PackageDate": "12/11/25",
            },
        }

        response = client.post(
            "/bb/preview", data=json.dumps(payload), content_type="application/json"
        )
        assert response.status_code == 200

        data = response.get_json()
        assert data["template"] == "bluey_label"
        assert data["status"] == "preview"

    def test_bluey_label_print_api_with_new_fields(self, client):
        """Test print API with new field names."""
        payload = {
            "template": "bluey_label",
            "data": {
                "Line1": "Test",
                "Line2": "Label",
                "Side": "TL",
                "Between": "middle",
                "Bottom": "12/11/25",
                "Inversion": "25",
            },
        }

        response = client.post(
            "/bb/print", data=json.dumps(payload), content_type="application/json"
        )
        assert response.status_code == 200

        data = response.get_json()
        assert data["template"] == "bluey_label"
        assert data["status"] == "sent"

    def test_form_data_extraction_from_url_params(self, client):
        """Test that URL parameters are correctly extracted into form data."""
        # Test with new field names
        response = client.get(
            "/bb?Line1=URL&Line2=Test&Side=UT&Between=center&Bottom=12/11/25&Inversion=50&tpl=bluey_label"
        )
        assert response.status_code == 200

        # Test with old field names (backward compatibility)
        response = client.get(
            "/bb?Line1=URL&Line2=Test&Initials=UT&PackageDate=12/11/25&tpl=bluey_label"
        )
        assert response.status_code == 200

    def test_empty_form_renders_correctly(self, client):
        """Test that empty form renders without errors."""
        response = client.get("/bb?tpl=bluey_label")
        assert response.status_code == 200

        html = response.get_data(as_text=True)
        # Should have empty values but proper form structure
        assert 'name="Line1"' in html
        assert 'name="Side"' in html
        assert 'name="Between"' in html
        assert 'name="Bottom"' in html
        assert 'name="Inversion"' in html

    def test_form_submission_simulation(self, client):
        """Test simulating form submission like JavaScript would do."""
        # Simulate what happens when user fills out form and JavaScript submits it
        form_data = {
            "Line1": "JavaScript",
            "Line2": "Test",
            "SymbolName": "awake",
            "Side": "JS",
            "Between": "center",
            "Bottom": "12/11/25",
            "Inversion": "15",
        }

        # Test preview endpoint (what JavaScript calls)
        payload = {"template": "bluey_label", "data": form_data}

        response = client.post(
            "/bb/preview", data=json.dumps(payload), content_type="application/json"
        )
        assert response.status_code == 200

        data = response.get_json()
        assert data["template"] == "bluey_label"
        assert data["status"] == "preview"

        # Verify the print URL contains the correct parameters
        print_url = data.get("print_url", "")
        assert "Line1=JavaScript" in print_url
        assert "Line2=Test" in print_url
        assert "Side=JS" in print_url
        assert "Between=center" in print_url
        assert "Bottom=12%2F11%2F25" in print_url  # URL encoded
        assert "Inversion=15" in print_url

    def test_countdown_functionality_url_params(self, client):
        """Test that countdown URLs work correctly."""
        # Test URL with print=true parameter
        response = client.get("/bb?Line1=Countdown&Line2=Test&Side=CT&tpl=bluey_label&print=true")
        assert response.status_code == 200

        html = response.get_data(as_text=True)
        # Should contain countdown container
        assert "printCountdownContainer" in html
        # Should have form populated with values
        assert 'value="Countdown"' in html
        assert 'value="Test"' in html
        assert 'value="CT"' in html

    def test_end_to_end_bluey_workflow(self, client):
        """Test complete end-to-end workflow for Bluey labels."""
        # Step 1: Load form with URL parameters (simulates user clicking a link)
        response = client.get(
            "/bb?Line1=E2E&Line2=Test&Side=ET&Between=workflow&Bottom=12/11/25&Inversion=75&tpl=bluey_label"
        )
        assert response.status_code == 200

        html = response.get_data(as_text=True)
        # Verify form is populated correctly
        assert 'value="E2E"' in html
        assert 'value="Test"' in html
        assert 'value="ET"' in html
        assert 'value="workflow"' in html
        assert 'value="12/11/25"' in html
        assert 'value="75"' in html
        assert 'data-template="bluey_label"' in html

        # Step 2: Simulate JavaScript preview request
        preview_payload = {
            "template": "bluey_label",
            "data": {
                "Line1": "E2E",
                "Line2": "Test",
                "SymbolName": "awake",
                "Side": "ET",
                "Between": "workflow",
                "Bottom": "12/11/25",
                "Inversion": "75",
            },
        }

        response = client.post(
            "/bb/preview", data=json.dumps(preview_payload), content_type="application/json"
        )
        assert response.status_code == 200

        data = response.get_json()
        assert data["template"] == "bluey_label"
        assert data["status"] == "preview"
        assert "label" in data
        assert "image" in data["label"]

        # Step 3: Simulate print request
        print_payload = {
            "template": "bluey_label",
            "data": {
                "Line1": "E2E",
                "Line2": "Test",
                "SymbolName": "awake",
                "Side": "ET",
                "Between": "workflow",
                "Bottom": "12/11/25",
                "Inversion": "75",
            },
        }

        response = client.post(
            "/bb/print", data=json.dumps(print_payload), content_type="application/json"
        )
        assert response.status_code == 200

        data = response.get_json()
        assert data["template"] == "bluey_label"
        assert data["status"] == "sent"

        # Step 4: Test execute-print endpoint (countdown completion)
        form_data = {
            "Line1": "E2E",
            "Line2": "Test",
            "SymbolName": "awake",
            "Side": "ET",
            "Between": "workflow",
            "Bottom": "12/11/25",
            "Inversion": "75",
            "tpl": "bluey_label",
        }

        print_data = "&".join([f"{k}={v}" for k, v in form_data.items()])
        response = client.post(
            "/bb/execute-print", data=print_data, content_type="application/x-www-form-urlencoded"
        )
        assert response.status_code == 200

        data = response.get_json()
        assert data["template"] == "bluey_label"
        assert data["status"] == "sent"
