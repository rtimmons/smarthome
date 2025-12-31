"""Browser automation tests for the printer service."""

import json
import time
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


class TestBrowserSimulation:
    """Test browser-like interactions with the printer service."""

    def test_form_auto_preview_simulation(self, client):
        """Simulate what happens when a user loads a form and JavaScript auto-generates preview."""
        # Step 1: User loads page with URL parameters
        response = client.get("/bb?Line1=Auto&Line2=Preview&Side=AP&Bottom=Shelf+2&tpl=bluey_label")
        assert response.status_code == 200

        html = response.get_data(as_text=True)
        # Verify form is populated
        assert 'value="Auto"' in html
        assert 'value="Preview"' in html
        assert 'value="AP"' in html
        assert 'value="Shelf 2"' in html

        # Step 2: JavaScript would collect form data and send preview request
        # Simulate the JavaScript formDataToObject function
        form_data = {
            "Line1": "Auto",
            "Line2": "Preview",
            "SymbolName": "awake",  # Default value
            "Side": "AP",
            "Bottom": "Shelf 2",
        }

        # Step 3: JavaScript sends preview request
        payload = {"template": "bluey_label", "data": form_data}

        response = client.post(
            "/bb/preview", data=json.dumps(payload), content_type="application/json"
        )
        assert response.status_code == 200

        data = response.get_json()
        assert data["template"] == "bluey_label"
        assert data["status"] == "preview"
        assert "label" in data
        assert "image" in data["label"]

        # Verify the image data is not empty (base64 encoded image)
        image_data = data["label"]["image"]
        assert image_data.startswith("data:image/")
        assert len(image_data) > 1000  # Should be a substantial image

    def test_print_button_click_simulation(self, client):
        """Simulate clicking the print button after filling out form."""
        # Step 1: User fills out form and clicks print
        form_data = {
            "Line1": "Print",
            "Line2": "Test",
            "SymbolName": "awake",
            "Side": "PT",
            "Bottom": "Shelf 1",
            "tpl": "bluey_label",  # Include template parameter
        }

        # Step 2: JavaScript would trigger print with countdown
        # This simulates the print URL that would be generated
        print_url = "/bb/execute-print"
        print_data = "&".join([f"{k}={v}" for k, v in form_data.items()])

        response = client.post(
            print_url, data=print_data, content_type="application/x-www-form-urlencoded"
        )
        assert response.status_code == 200

        data = response.get_json()
        assert data["template"] == "bluey_label"
        assert data["status"] == "sent"

    def test_countdown_behavior_simulation(self, client):
        """Test the countdown functionality behavior."""
        # Step 1: User accesses URL with print=true (triggers countdown)
        response = client.get("/bb?Line1=Countdown&Line2=Test&Side=CT&tpl=bluey_label&print=true")
        assert response.status_code == 200

        html = response.get_data(as_text=True)
        # Should contain countdown elements
        assert "printCountdownContainer" in html
        assert "countdownTimer" in html
        assert "printNowButton" in html
        assert "cancelCountdown" in html

        # Form should be populated
        assert 'value="Countdown"' in html
        assert 'value="Test"' in html
        assert 'value="CT"' in html

    def test_empty_form_preview_generation(self, client):
        """Test that empty form still generates a valid preview."""
        # Simulate JavaScript sending empty form data
        payload = {"template": "bluey_label", "data": {}}

        response = client.post(
            "/bb/preview", data=json.dumps(payload), content_type="application/json"
        )
        assert response.status_code == 200

        data = response.get_json()
        assert data["template"] == "bluey_label"
        assert data["status"] == "preview"
        assert "label" in data
        assert "image" in data["label"]

        # Even empty form should generate a valid image
        image_data = data["label"]["image"]
        assert image_data.startswith("data:image/")
        assert len(image_data) > 200  # Should be a valid image
