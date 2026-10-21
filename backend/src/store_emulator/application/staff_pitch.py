"""Staff-script jobs with immutable product, script and persona snapshots."""

import asyncio
import csv
import io
import time

from store_emulator.application.errors import AppError
from store_emulator.application.async_executor import executor
from store_emulator.application.marketing import (
    _finish, _job_dir, _new_job, _status, _write_status,  # pyright: ignore[reportPrivateUsage]
)
from store_emulator.application.providers import build_client
from store_emulator.application.shelf_lab import _check_id, _load_store, _personas  # pyright: ignore[reportPrivateUsage]
from store_emulator.application.storage.io import read_json, write_json
from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.marketing import JobStatus
from store_emulator.domain.staff_pitch import PitchProduct, PitchReport, PitchRequest, PitchView
from store_emulator.engine.marketing.staff_pitch import summarize_pitch, test_pitch_panel
from store_emulator.engine.optimize.evaluate import select_personas


def start_pitch(pid: str, req: PitchRequest, config: SimulationConfig) -> JobStatus:
    _check_id(pid, "project id")
    _check_id(req.setup_id, "setup id")
    store = _load_store(pid, req.setup_id)
    products = [p for rack in store.racks for slot in rack.slots for p in slot.items if p.sku == req.sku]
    if not products:
        raise AppError("Choose a product present in this layout", 400)
    if len({(p.name, p.price, p.promo) for p in products}) > 1:
        raise AppError("This SKU has conflicting names, prices or offers across shelves; resolve them before testing", 400)
    product = PitchProduct(sku=req.sku, name=products[0].name, price=products[0].price,
                           currency=config.currency, promo=products[0].promo)
    personas = _personas(pid)
    ids = [p.id.strip() for p in personas]
    if any(not pid for pid in ids) or len(set(ids)) != len(ids):
        raise AppError("Persona IDs must be nonblank and unique before testing scripts", 400)
    panel = select_personas(personas, req.panel, seed=req.seed)
    if len(panel) < 20:
        raise AppError("Staff script tests need at least 20 saved personas", 400)
    llm_config = config.llm_for(EngineType.PATTERN_INTENT_IMPULSE).model_copy(update={
        "temperature": 0.4, "max_tokens": 700,
    })
    try:
        llm = build_client(llm_config, None, model_ref=req.model.strip() or None)
    except ValueError as exc:
        raise AppError(str(exc), 400) from exc
    name = req.name.strip() or f"{req.variants[0].name} vs {req.variants[1].name}"
    status = _new_job(pid, "pitch", name, req)
    write_json(_job_dir(pid, "pitch", status.job_id) / "inputs.json", {
        "product": product.model_dump(mode="json"), "personas": [p.model_dump(mode="json") for p in panel],
        "model": req.model.strip() or llm_config.model, "temperature": 0.4,
    })

    def run() -> None:
        started = time.perf_counter()
        status.status, status.stage = "running", "testing scripts"
        _write_status(pid, status)
        try:
            def progress(value: float, stage: str) -> None:
                status.progress, status.stage = round(value, 3), stage
                _write_status(pid, status)

            answers = asyncio.run(test_pitch_panel(llm, panel, req, product, on_progress=progress))
            if not any(a.a is not None and a.b is not None for a in answers):
                # Preserve failed responses for diagnosis without reporting an empty result as a success.
                write_json(_job_dir(pid, "pitch", status.job_id) / "answers.json",
                           [a.model_dump(mode="json") for a in answers])
                raise ValueError("No complete response pairs; check the text model configuration and retry")
            report = summarize_pitch(status.job_id, name, req.model.strip() or llm_config.model, req, product, answers,
                                     seconds=round(time.perf_counter() - started, 1))
            _finish(pid, status, report)
        except Exception as exc:
            _finish(pid, status, None, f"{type(exc).__name__}: staff script test failed; check the text model configuration and retry")

    executor.submit(run)
    return status


def get_pitch(pid: str, pitch_id: str) -> PitchView:
    status = _status(pid, "pitch", pitch_id)
    path = _job_dir(pid, "pitch", pitch_id) / "report.json"
    report = PitchReport.model_validate(read_json(path)) if path.exists() else None
    return PitchView(**status.model_dump(), report=report)


def pitch_csv(pid: str, pitch_id: str) -> str:
    report = get_pitch(pid, pitch_id).report
    if report is None:
        raise AppError("This staff script test has no report yet", 409)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["test_id", "model", "seed", "sku", "price_minor", "currency", "respondent", "age_group", "gender",
                     "first_arm", "included_pair", "arm", "script_name", "script", "context", "product_facts",
                     "purchase_intent", "trust", "pressure", "reply", "reason", "error"])
    for answer in report.answers:
        for i, (arm, rating, error) in enumerate((("A", answer.a, answer.error_a), ("B", answer.b, answer.error_b))):
            variant = report.request.variants[i]
            row: list[str | int] = [
                report.pitch_id, report.model, report.request.seed, report.product.sku, report.product.price,
                report.product.currency, answer.respondent, answer.age_group, answer.gender, answer.first_arm,
                int(answer.a is not None and answer.b is not None), arm, variant.name, variant.script,
                report.request.context, report.request.product_facts,
                rating.purchase_intent if rating else "", rating.trust if rating else "", rating.pressure if rating else "",
                rating.reply if rating else "", rating.reason if rating else "", error,
            ]
            # User/model text must not become formulas when opened in a spreadsheet.
            writer.writerow(["'" + cell if isinstance(cell, str) and cell.lstrip().startswith(("=", "+", "-", "@"))
                             else cell for cell in row])
    return buf.getvalue()
