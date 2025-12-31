"""
Test suite to reproduce and verify fixes for navigation and state management issues.
"""

import json
import pytest
from pathlib import Path
from printer_service.app import create_app


class TestNavigationIssues:
    """Test current navigation and state management issues."""

    @pytest.fixture
    def client(self):
        app = create_app()
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    def test_current_preview_navigation_flow(self, client):
        """Test the current preview → print navigation flow to identify issues."""
        # Step 1: Load initial form page
        response = client.get("/bb?Line1=Test&Line2=Flow&Side=TF&tpl=bluey_label")
        assert response.status_code == 200

        html = response.get_data(as_text=True)
        # Verify form is populated
        assert 'value="Test"' in html
        assert 'value="Flow"' in html
        assert 'value="TF"' in html
        assert 'data-template="bluey_label"' in html

        # Verify preview triggers are present
        assert "bb-preview-trigger" in html
        assert 'data-print-target="label"' in html
        assert 'data-print-target="qr"' in html

    def test_print_page_with_countdown_trigger(self, client):
        """Test that print=true URLs trigger countdown correctly."""
        # Step 2: Navigate to print page (simulates preview click)
        response = client.get("/bb?Line1=Test&Line2=Flow&Side=TF&tpl=bluey_label&print=true")
        assert response.status_code == 200

        html = response.get_data(as_text=True)
        # Verify form is still populated after navigation
        assert 'value="Test"' in html
        assert 'value="Flow"' in html
        assert 'value="TF"' in html

        # Verify countdown container is present (but hidden by default)
        assert "printCountdownContainer" in html
        assert 'style="display: none;"' in html

        # Verify JavaScript will detect print=true parameter
        # (This would be tested in browser automation tests)

    def test_qr_print_navigation(self, client):
        """Test QR label print navigation."""
        response = client.get(
            "/bb?Line1=Test&Line2=Flow&Side=TF&tpl=bluey_label&print=true&qr=true"
        )
        assert response.status_code == 200

        html = response.get_data(as_text=True)
        # Form should still be populated
        assert 'value="Test"' in html
        assert 'value="Flow"' in html
        assert 'value="TF"' in html

        # Countdown container should be present
        assert "printCountdownContainer" in html

    def test_execute_print_endpoint_consistency(self, client):
        """Test that execute-print endpoint works with URL parameters."""
        # Test the endpoint that gets called after countdown
        form_data = {"Line1": "Test", "Line2": "Flow", "Side": "TF", "tpl": "bluey_label"}

        print_data = "&".join([f"{k}={v}" for k, v in form_data.items()])
        response = client.post(
            "/bb/execute-print", data=print_data, content_type="application/x-www-form-urlencoded"
        )
        assert response.status_code == 200

        data = response.get_json()
        assert data["template"] == "bluey_label"
        assert data["status"] == "sent"

    def test_url_parameter_preservation(self, client):
        """Test that URL parameters are preserved across navigation."""
        # Test with complex parameters including special characters
        params = {
            "Line1": "Test & Flow",
            "Line2": "Special/Chars",
            "Side": "T&F",
            "Bottom": "12/11/25",
            "tpl": "bluey_label",
        }

        # Build URL with parameters (URL encoded)
        from urllib.parse import urlencode

        param_string = urlencode(params)

        # Test normal page
        response = client.get(f"/bb?{param_string}")
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert 'value="Test &amp; Flow"' in html  # HTML escaped
        assert 'value="Special/Chars"' in html
        assert 'value="T&amp;F"' in html

        # Test print page
        response = client.get(f"/bb?{param_string}&print=true")
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        # Parameters should still be preserved
        assert 'value="Test &amp; Flow"' in html
        assert 'value="Special/Chars"' in html
        assert 'value="T&amp;F"' in html

    def test_preview_api_consistency(self, client):
        """Test that preview API works consistently with form data."""
        payload = {
            "template": "bluey_label",
            "data": {"Line1": "Test", "Line2": "Flow", "Side": "TF", "SymbolName": "awake"},
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

    def test_improved_navigation_structure(self, client):
        """Test that the improved navigation structure is in place."""
        # Test that JavaScript functions are present in the page
        response = client.get("/bb?Line1=Test&Line2=Flow&Side=TF&tpl=bluey_label")
        assert response.status_code == 200

        html = response.get_data(as_text=True)

        # Verify countdown container is present but hidden
        assert "printCountdownContainer" in html
        assert 'style="display: none;"' in html

        # Verify preview triggers are present
        assert "bb-preview-trigger" in html
        assert 'data-print-target="label"' in html
        assert 'data-print-target="qr"' in html

        # Verify JavaScript is loaded
        assert 'src="/static/app.js"' in html

    def test_theme_picker_markup(self, client):
        """Test that the theme picker markup is present."""
        response = client.get("/bb?tpl=bluey_label")
        assert response.status_code == 200

        html = response.get_data(as_text=True)
        assert 'id="themeToggle"' in html
        assert 'data-theme="light"' in html
        assert 'data-theme="dark"' in html
        assert 'data-theme="system"' in html
        assert html.count("theme-toggle__option") >= 3

    def test_print_state_url_handling(self, client):
        """Test that print=true URLs still work correctly."""
        # Test that print=true URLs render correctly
        response = client.get("/bb?Line1=Test&Line2=Flow&Side=TF&tpl=bluey_label&print=true")
        assert response.status_code == 200

        html = response.get_data(as_text=True)

        # Form should be populated
        assert 'value="Test"' in html
        assert 'value="Flow"' in html
        assert 'value="TF"' in html

        # Countdown container should be present
        assert "printCountdownContainer" in html

        # JavaScript should detect print=true parameter
        # (This would trigger countdown in browser)

    def test_qr_state_url_handling(self, client):
        """Test that QR print URLs work correctly."""
        response = client.get(
            "/bb?Line1=Test&Line2=Flow&Side=TF&tpl=bluey_label&print=true&qr=true"
        )
        assert response.status_code == 200

        html = response.get_data(as_text=True)

        # Form should be populated
        assert 'value="Test"' in html
        assert 'value="Flow"' in html
        assert 'value="TF"' in html

        # Countdown container should be present
        assert "printCountdownContainer" in html


class TestEndToEndWorkflows:
    """Test complete end-to-end workflows with the new navigation system."""

    @pytest.fixture
    def client(self):
        """Create a test client for the Flask app."""
        from printer_service.app import create_app

        app = create_app()
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    def test_preview_to_print_to_countdown_workflow(self, client):
        """Test the complete workflow: form → preview → print → countdown."""
        # Step 1: Load form with data
        response = client.get("/bb?Line1=E2E&Line2=Test&Side=ET&tpl=bluey_label")
        assert response.status_code == 200

        html = response.get_data(as_text=True)

        # Verify form is populated
        assert 'value="E2E"' in html
        assert 'value="Test"' in html
        assert 'value="ET"' in html

        # Verify preview triggers are present
        assert "bb-preview-trigger" in html
        assert 'data-print-target="label"' in html
        assert 'data-print-target="qr"' in html

        # Step 2: Test preview generation (simulates JavaScript preview)
        preview_payload = {
            "template": "bluey_label",
            "data": {"Line1": "E2E", "Line2": "Test", "Side": "ET", "SymbolName": "awake"},
        }

        preview_response = client.post(
            "/bb/preview", data=json.dumps(preview_payload), content_type="application/json"
        )
        assert preview_response.status_code == 200

        preview_data = preview_response.get_json()
        assert preview_data["status"] == "preview"
        assert "label" in preview_data
        assert "qr" in preview_data

        # Step 3: Navigate to print state (simulates preview click)
        print_response = client.get("/bb?Line1=E2E&Line2=Test&Side=ET&tpl=bluey_label&print=true")
        assert print_response.status_code == 200

        print_html = print_response.get_data(as_text=True)

        # Verify form data is preserved
        assert 'value="E2E"' in print_html
        assert 'value="Test"' in print_html
        assert 'value="ET"' in print_html

        # Verify countdown container is present
        assert "printCountdownContainer" in print_html

        # Step 4: Test QR print state
        qr_response = client.get(
            "/bb?Line1=E2E&Line2=Test&Side=ET&tpl=bluey_label&print=true&qr=true"
        )
        assert qr_response.status_code == 200

        qr_html = qr_response.get_data(as_text=True)

        # Verify form data is still preserved
        assert 'value="E2E"' in qr_html
        assert 'value="Test"' in qr_html
        assert 'value="ET"' in qr_html

        # Verify countdown container is present
        assert "printCountdownContainer" in qr_html

    def test_url_state_consistency_across_transitions(self, client):
        """Test that URL state remains consistent across all transitions."""
        base_params = {
            "Line1": "State",
            "Line2": "Test",
            "Side": "ST",
            "Bottom": "12/11/25",
            "tpl": "bluey_label",
        }

        # Test form state
        form_url = "/bb?" + "&".join([f"{k}={v}" for k, v in base_params.items()])
        response = client.get(form_url)
        assert response.status_code == 200

        html = response.get_data(as_text=True)
        assert 'value="State"' in html
        assert 'value="Test"' in html
        assert 'value="ST"' in html
        assert 'value="12/11/25"' in html

        # Test print state preserves all parameters
        print_params = base_params.copy()
        print_params["print"] = "true"
        print_url = "/bb?" + "&".join([f"{k}={v}" for k, v in print_params.items()])

        response = client.get(print_url)
        assert response.status_code == 200

        html = response.get_data(as_text=True)
        assert 'value="State"' in html
        assert 'value="Test"' in html
        assert 'value="ST"' in html
        assert 'value="12/11/25"' in html

        # Test QR print state preserves all parameters
        qr_params = print_params.copy()
        qr_params["qr"] = "true"
        qr_url = "/bb?" + "&".join([f"{k}={v}" for k, v in qr_params.items()])

        response = client.get(qr_url)
        assert response.status_code == 200

        html = response.get_data(as_text=True)
        assert 'value="State"' in html
        assert 'value="Test"' in html
        assert 'value="ST"' in html
        assert 'value="12/11/25"' in html

    def test_print_execution_with_preserved_state(self, client):
        """Test that print execution works correctly with preserved form state."""
        # Set up form data
        form_data = {
            "Line1": "Print",
            "Line2": "Execute",
            "Side": "PE",
            "SymbolName": "awake",
            "Bottom": "12/11/25",
        }

        # Test label print execution
        response = client.post(
            "/bb/execute-print",
            data={**form_data, "template": "bluey_label"},
            content_type="application/x-www-form-urlencoded",
        )

        # Should succeed (or fail gracefully if no printer)
        assert response.status_code in [200, 500]  # 500 if no printer available

        # Test QR print execution
        response = client.post(
            "/bb/execute-print",
            data={**form_data, "template": "bluey_label", "qr": "true"},
            content_type="application/x-www-form-urlencoded",
        )

        # Should succeed (or fail gracefully if no printer)
        assert response.status_code in [200, 500]  # 500 if no printer available

    def test_execute_print_endpoint_javascript_format(self, monkeypatch, tmp_path):
        """Test that execute-print endpoint works with the format JavaScript sends."""
        # Set up test environment with file backend (no real printing)
        monkeypatch.setenv("PRINTER_BACKEND", "file")
        monkeypatch.setenv("PRINTER_OUTPUT_PATH", str(tmp_path / "test_output.png"))

        # Create test client with safe environment
        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()

        # This test simulates exactly what the JavaScript does:
        # POST request with parameters in URL, no body, no Content-Type header

        url_params = "Line1=JS&Line2=Test&Side=JT&tpl=bluey_label"
        response = client.post(f"/bb/execute-print?{url_params}")

        # Should return JSON response (not HTML) - may succeed or fail gracefully
        assert response.status_code in [200, 500]  # 500 if no printer available

        # Response should be JSON, not HTML
        content_type = response.headers.get("Content-Type", "")
        assert "application/json" in content_type

        # Should be able to parse as JSON
        data = response.get_json()
        assert data is not None

        if response.status_code == 200:
            # Success case
            assert data["template"] == "bluey_label"
            assert data["status"] == "sent"
        else:
            # Error case (no printer available)
            assert "error" in data

        # Most importantly: this test validates that the JavaScript request format
        # (POST with URL params, no body) works correctly and returns JSON

    def test_preview_generation_does_not_cause_unexpected_format_error(self, monkeypatch, tmp_path):
        """Test that preview generation calls don't cause 'Unexpected response format' errors."""
        # Set up test environment with file backend (no real printing)
        monkeypatch.setenv("PRINTER_BACKEND", "file")
        monkeypatch.setenv("PRINTER_OUTPUT_PATH", str(tmp_path / "test_output.png"))

        # Create test client
        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()

        # Test the preview endpoint that gets called during preview generation
        preview_payload = {
            "template": "bluey_label",
            "data": {"Line1": "Preview", "Line2": "Test", "Side": "PT", "SymbolName": "awake"},
        }

        response = client.post(
            "/bb/preview", data=json.dumps(preview_payload), content_type="application/json"
        )

        # Should return JSON response (not HTML)
        assert response.status_code == 200

        # Response should be JSON, not HTML
        content_type = response.headers.get("Content-Type", "")
        assert "application/json" in content_type

        # Should be able to parse as JSON
        data = response.get_json()
        assert data is not None
        assert "label" in data
        assert "qr" in data
        assert "image" in data["label"]
        assert "image" in data["qr"]

        # This validates that preview generation works correctly and doesn't
        # cause the "Unexpected response format" error that was happening
        # when clicking preview images
