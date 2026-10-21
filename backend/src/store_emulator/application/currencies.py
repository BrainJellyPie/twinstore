"""Keep a layout's prices and the project's shared shopper budgets in one unit."""

from store_emulator.application.errors import AppError
from store_emulator.application.storage.io import read_json
from store_emulator.application.storage.setups import metadata_path
from store_emulator.domain.store import Store


def project_currency(pid: str, fallback: str) -> str:
    path = metadata_path(pid)
    meta: dict[str, object] = read_json(path) if path.exists() else {}
    return str(meta.get("currency") or fallback).upper()


def simulation_currency(pid: str, store: Store, fallback: str) -> str:
    budget_currency = project_currency(pid, fallback)
    if store.currency and store.currency != budget_currency:
        raise AppError(
            f"This layout uses {store.currency}, but project shopper budgets use {budget_currency}. "
            f"Choose a layout in {budget_currency} or create a new {store.currency} project. "
            "Existing budgets are not converted automatically.", 422,
        )
    return store.currency or budget_currency
