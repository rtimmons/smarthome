from printer_service.label_templates import best_by


def test_build_qr_caption_includes_base_date_when_present():
    url = "http://[::1]:8099/bb?BaseDate=2025-12-04&Offset=2+weeks&tpl=best_by&print=true"
    caption = best_by._build_qr_caption(url, "", "2 weeks")
    assert "Base 2025-12-04" in caption


def test_build_qr_caption_omits_base_date_when_missing():
    url = "http://[::1]:8099/bb?Offset=2+weeks&tpl=best_by&print=true"
    caption = best_by._build_qr_caption(url, "", "2 weeks")
    assert "Base " not in caption
