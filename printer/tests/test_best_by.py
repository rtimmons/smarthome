from printer_service.label_templates import best_by


def test_build_qr_caption_includes_base_date_when_present():
    url = "http://[::1]:8099/bb?BaseDate=2025-12-04&Offset=2+weeks&tpl=best_by&print=true"
    caption = best_by._build_qr_caption(url, "", "2 weeks")
    assert "Base 2025-12-04" in caption


def test_build_qr_caption_omits_base_date_when_missing():
    url = "http://[::1]:8099/bb?Offset=2+weeks&tpl=best_by&print=true"
    caption = best_by._build_qr_caption(url, "", "2 weeks")
    assert "Base " not in caption


def test_build_qr_caption_prefix_only_when_base_date_empty():
    url = "http://[::1]:8099/bb?BaseDate=&Offset=2+weeks&Prefix=Test&tpl=best_by&print=true"
    caption = best_by._build_qr_caption(url, "", "2 weeks")
    assert caption == "Print Test"


def test_build_qr_caption_respects_provided_caption_forced_empty_base_date():
    url = "http://[::1]:8099/bb?BaseDate=&Offset=2+weeks&Prefix=Test&tpl=best_by&print=true"
    caption = best_by._build_qr_caption(url, "Print Test", "2 weeks")
    assert caption == "Print Test"


def test_build_qr_caption_prefix_no_colon_with_details():
    url = "http://[::1]:8099/bb?Offset=2+weeks&Prefix=Made&tpl=best_by&print=true"
    caption = best_by._build_qr_caption(url, "", "2 weeks")
    assert caption == "Print Made +2 Weeks"
