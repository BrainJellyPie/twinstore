"""Optional PDF support must reject bad input and release native rendering handles."""

import io
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest
from PIL import Image

from store_emulator.application.errors import AppError
from store_emulator.application.floorplan import load_plan_image


@pytest.fixture
def pdf_handles(monkeypatch):
    document = MagicMock()
    document.__len__.return_value = 1
    page = document.__getitem__.return_value
    bitmap = page.render.return_value
    bitmap.to_pil.return_value = Image.new("RGB", (8, 8), "white")
    monkeypatch.setitem(sys.modules, "pypdfium2", SimpleNamespace(PdfDocument=Mock(return_value=document)))
    return document, page, bitmap


def test_pdf_load_error_is_a_bad_request(monkeypatch):
    monkeypatch.setitem(sys.modules, "pypdfium2", SimpleNamespace(PdfDocument=Mock(side_effect=RuntimeError("bad PDF"))))
    with pytest.raises(AppError) as error:
        load_plan_image(b"%PDF-invalid", "plan.pdf")
    assert error.value.status_code == 400


def test_empty_pdf_is_rejected_and_closed(pdf_handles):
    document, _, _ = pdf_handles
    document.__len__.return_value = 0
    with pytest.raises(AppError) as error:
        load_plan_image(b"%PDF-empty", "plan.pdf")
    assert error.value.status_code == 400
    document.close.assert_called_once()


def test_pdf_render_error_releases_open_handles(pdf_handles):
    document, page, _ = pdf_handles
    page.render.side_effect = RuntimeError("render failed")
    with pytest.raises(AppError) as error:
        load_plan_image(b"%PDF-test", "plan.pdf")
    assert error.value.status_code == 400
    page.close.assert_called_once()
    document.close.assert_called_once()


def test_rendered_pdf_image_survives_handle_cleanup(pdf_handles):
    document, page, bitmap = pdf_handles
    image = load_plan_image(b"%PDF-test", "plan.pdf")
    assert image.getpixel((0, 0)) == (255, 255, 255)
    bitmap.close.assert_called_once()
    page.close.assert_called_once()
    document.close.assert_called_once()


def test_missing_pdf_dependency_remains_an_actionable_bad_request(monkeypatch):
    monkeypatch.setitem(sys.modules, "pypdfium2", None)
    with pytest.raises(AppError) as error:
        load_plan_image(b"%PDF-test", "plan.pdf")
    assert error.value.status_code == 400 and "pypdfium2" in error.value.message


def test_real_pdf_first_page_is_decoded_when_parser_is_available():
    pdfium = pytest.importorskip("pypdfium2")
    buffer = io.BytesIO()
    with pdfium.PdfDocument.new() as document:
        page = document.new_page(72, 36)
        page.close()
        document.save(buffer)
    image = load_plan_image(buffer.getvalue(), "plan.pdf")
    assert image.mode == "RGB" and image.size == (144, 72)
    assert image.getpixel((0, 0)) == (255, 255, 255)
