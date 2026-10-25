"""Online stores of a project: sites made from templates (or the project's own shelves), browsing them as a shopper
would, and runs where virtual shoppers visit one site or compare up to four variants.

Storage: `.data/<pid>/online/sites/<site_id>.json`; runs under `.data/<pid>/online/runs/<run_id>/` (status.json,
request snapshot of the sites and shoppers, sessions-<variant>.json, result.json), polled like other background jobs.
"""

import asyncio
import hashlib
import io
import json
import logging
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import cast

from filelock import FileLock, Timeout
from PIL import Image, ImageDraw
from pydantic import BaseModel, Field, TypeAdapter

from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.interview import (
    AnalystMessage,
    AnalystQuestion,
    AnalystThread,
    InterviewMessage,
    InterviewQuestion,
)
from store_emulator.domain.marketing import VariantChange
from store_emulator.domain.online import (
    FUNNEL_STAGES,
    ActionKind,
    AdCampaign,
    BrowserState,
    DesignChatReply,
    DesignChatRequest,
    Device,
    OnlineProduct,
    OnlineRunRequest,
    OnlineRunResult,
    OnlineRunStatus,
    OnlineShopper,
    OnlineSite,
    OnlineTemplate,
    PageOption,
    PageStyle,
    Vision,
    PageView,
    RivalVisit,
    SessionOutcome,
    SessionResult,
    SessionStep,
    SiteOptions,
    VariantComparison,
    VisitBrief,
)
from store_emulator.domain.rack import SlotItem
from store_emulator.domain.store import Store
from store_emulator.domain.types import ResourceId, stable_seed
from store_emulator.engine.files import remove_tree
from store_emulator.engine.online.ads import ad_lifts
from store_emulator.engine.online.analysis import clickstream_csv, paired_deltas, segment_deltas, summarize, switches
from store_emulator.engine.online.browser import apply, build_page, initial_state, numbering, outline
from store_emulator.engine.online.catalog import FROM_STORE_TEMPLATE, build_site, site_from_store, template_ids, template_summaries
from store_emulator.engine.layout_edit import MAX_LAYOUT_EDIT_CHANGES, ZERO_DECIMAL
from store_emulator.engine.online.analyst import answer_online_question, online_facts, suggest_online_questions
from store_emulator.engine.online.design_chat import apply_design, chat_design
from store_emulator.engine.online.store_changes import apply_store_changes, price_changes
from store_emulator.engine.online.interview import ask_shopper as interview_shopper
from store_emulator.engine.online.policies import ModelPolicy, RulePolicy, ShopperPolicy, Surveyor, tries_rival
from store_emulator.engine.online.render import ProductPicture, Screenshot, animate, render_page, see_as
from store_emulator.engine.online.report import online_report_html
from store_emulator.engine.online.session import run_session
from store_emulator.engine.online.shoppers import at_rival, sample_shoppers
from store_emulator.engine.perception.product_images import bundled_product_image

from .async_executor import executor, submit_background
from .currencies import project_currency
from .errors import AppError, job_failure, model_failure
from .product_images import project_image_loader, snapshot_image_loader, snapshot_project_images
from .providers import answered_by, assistive_client, assistive_model, build_client, ensure_resolvable
from .setups import setup_lock_path, setup_tree_transaction
from .simulation import with_engine_model, with_vision_default
from .shelf_lab import package_path
from .storage.io import DATA_DIR, now_iso, read_json, write_json
from .storage.personas import read_personas
from .storage.setups import read_setup, read_state

logger = logging.getLogger(__name__)

_MIN_STATUS_INTERVAL_SEC = 1.0
_MAX_SITES = 60
_MODEL_CONCURRENCY = 4
_SESSIONS = TypeAdapter(list[SessionResult])
_SHOPPERS = TypeAdapter(list[OnlineShopper])
_SITES = TypeAdapter(list[OnlineSite])


class CreateSiteRequest(BaseModel):
    template_id: str = Field(min_length=1, max_length=60)
    name: str = Field(default="", max_length=60)
    seed: int = 0
    setup_id: ResourceId | None = Field(default=None, description='Layout whose shelves become the catalog ("from_store")')


class CopySiteRequest(BaseModel):
    name: str = Field(default="", max_length=60)
    note: str = Field(default="", max_length=400)
    options: SiteOptions | None = None  # the variant's options (default: the original's)
    products: list[OnlineProduct] | None = Field(default=None, min_length=1)
    ads: list[AdCampaign] | None = Field(default=None, max_length=12)  # the variant's ads (default: the original's)


class SiteSummary(BaseModel):
    id: str
    name: str
    template_id: str
    currency: str
    categories: int
    products: int
    photos: int
    theme_color: str
    device: Device | None
    cart_reminder: bool = False
    variant_of: str
    note: str
    created_at: str
    updated_at: str


class BrowseRequest(BaseModel):
    state: BrowserState | None = None  # None = a new visit
    option: int | None = Field(default=None, ge=1, description="Number of the option to use on the state's page")
    query: str = Field(default="", max_length=60, description="What was typed, when the option is the search box")
    mark_seed: int = Field(default=0, ge=0)
    has_account: bool = False
    device: Device = "desktop"  # of a new visit
    vision: Vision = "typical"  # see the page as a shopper with this eyesight does


class OnlineRunView(BaseModel):
    status: OnlineRunStatus
    result: OnlineRunResult | None = None


class SessionView(BaseModel):
    variant: int
    site_id: str
    site_name: str
    shopper: OnlineShopper
    session: SessionResult


class PlaybackFrame(BaseModel):
    """One step of a visit for an animated playback: the screenshot's size and the box of what the shopper clicked
    (none on the page where the visit ended)."""
    step: int
    width: int
    height: int
    box: tuple[int, int, int, int] | None = None


class OnlineInterview(BaseModel):
    """A conversation with one shopper about their visit to one store of a run."""
    run_id: str
    variant: int
    shopper_id: str
    model: str = ""
    messages: list[InterviewMessage] = []


# ── storage ────────────────────────────────────────────────────────────────────


def _root(pid: str) -> Path:
    return Path(DATA_DIR) / pid / "online"


def _site_path(pid: str, site_id: str) -> Path:
    return _root(pid) / "sites" / f"{site_id}.json"


def _run_dir(pid: str, run_id: str) -> Path:
    return _root(pid) / "runs" / run_id


@contextmanager
def _write_transaction(pid: str) -> Iterator[None]:
    """Hold the project tree (so the project cannot be deleted meanwhile) and the online lock."""
    with setup_tree_transaction(pid):
        lock_path = _root(pid) / ".online.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with FileLock(lock_path, timeout=10):
                yield
        except Timeout as exc:
            raise AppError("Another online-store change is in progress; try again", 409) from exc


def list_templates() -> list[OnlineTemplate]:
    return template_summaries()


def _summary(site: OnlineSite) -> SiteSummary:
    return SiteSummary(
        id=site.id, name=site.name, template_id=site.template_id, currency=site.currency,
        categories=len(site.categories), products=len(site.products),
        photos=sum(1 for p in site.products if p.image_url), theme_color=site.options.theme_color,
        device=site.options.device, variant_of=site.variant_of, note=site.note, created_at=site.created_at,
        updated_at=site.updated_at, cart_reminder=site.options.cart_reminder,
    )


def list_sites(pid: str) -> list[SiteSummary]:
    folder = _root(pid) / "sites"
    if not folder.is_dir():
        return []
    out: list[SiteSummary] = []
    for path in folder.glob("*.json"):
        try:
            out.append(_summary(OnlineSite.model_validate(read_json(path))))
        except ValueError as e:  # one damaged site must not hide the others
            logger.warning(f"[online] skipping {pid}/{path.name}: {e}")
    return sorted(out, key=lambda s: s.created_at)


def get_site(pid: str, site_id: str) -> OnlineSite:
    path = _site_path(pid, site_id)
    if not path.exists():
        raise AppError(f"online store not found: {site_id}", 404)
    return OnlineSite.model_validate(read_json(path))


def _check(site: OnlineSite) -> None:
    for label, ids in (("category", [c.id for c in site.categories]), ("product", [p.id for p in site.products])):
        if len(set(ids)) != len(ids):
            raise AppError(f"Online store {label} IDs must be unique", 422)
    categories = {c.id for c in site.categories}
    stray = next((p for p in site.products if p.category_id not in categories), None)
    if stray is not None:
        raise AppError(f"Product {stray.name} is in a category the store does not have: {stray.category_id}", 422)
    if not site.options.payment_methods:
        raise AppError("Offer at least one payment method", 422)
    if len(site.options.home_sections) != len(set(site.options.home_sections)):
        raise AppError("Home page sections must not repeat", 422)
    ad_ids = [ad.id for ad in site.ads]
    if len(set(ad_ids)) != len(ad_ids):
        raise AppError("Ad IDs must be unique", 422)
    products = {p.id for p in site.products}
    unknown = next((ad for ad in site.ads if ad.product_id not in products), None)
    if unknown is not None:
        raise AppError(f"Ad {unknown.name} promotes a product the store does not sell: {unknown.product_id}", 422)


def _store_of_layout(pid: str, setup_id: str | None) -> Store:
    chosen = setup_id or read_state(pid).get("activeSetupId")
    if not isinstance(chosen, str) or not chosen:
        raise AppError("This project has no layout to take products from", 400)
    try:
        setup = read_setup(pid, chosen)
    except FileNotFoundError:
        raise AppError(f"layout not found: {chosen}", 404) from None
    if not setup.get("store"):
        raise AppError("This layout has no store yet", 400)
    return Store.model_validate(setup["store"])


def create_site(pid: str, request: CreateSiteRequest, config: SimulationConfig) -> OnlineSite:
    site_id = f"site_{uuid.uuid4().hex[:12]}"
    currency = project_currency(pid, config.currency)
    now = now_iso()
    with _write_transaction(pid):
        if len(list_sites(pid)) >= _MAX_SITES:
            raise AppError(f"A project can keep up to {_MAX_SITES} online stores; delete one first", 409)
        if request.template_id == FROM_STORE_TEMPLATE:
            store = _store_of_layout(pid, request.setup_id)
            try:
                site = site_from_store(store, site_id=site_id, name=request.name or _project_name(pid) or "Online store",
                                       currency=store.currency or currency, seed=request.seed, now=now)
            except ValueError as e:
                raise AppError(str(e), 400) from e
        elif request.template_id in template_ids():
            site = build_site(request.template_id, site_id=site_id, currency=currency, name=request.name,
                              seed=request.seed, now=now)
        else:
            raise AppError(f"unknown online store template: {request.template_id}", 400)
        write_json(_site_path(pid, site_id), site.model_dump(mode="json"))
    return site


def _project_name(pid: str) -> str:
    path = Path(DATA_DIR) / pid / "metadata.json"
    try:
        meta: object = read_json(path)
    except (FileNotFoundError, ValueError):
        return ""
    if not isinstance(meta, dict):
        return ""
    name = cast(dict[str, object], meta).get("name", "")
    return name if isinstance(name, str) else ""


def save_site(pid: str, site_id: str, site: OnlineSite) -> OnlineSite:
    if site.id != site_id:
        raise AppError("The store's ID does not match the address", 400)
    _check(site)
    with _write_transaction(pid):
        current = get_site(pid, site_id)
        saved = site.model_copy(update={"created_at": current.created_at, "template_id": current.template_id,
                                        "currency": current.currency, "updated_at": now_iso()})
        write_json(_site_path(pid, site_id), saved.model_dump(mode="json"))
    return saved


def copy_site(pid: str, site_id: str, request: CopySiteRequest) -> OnlineSite:
    """A variant: the same catalog with its own options, to compare with the original on the same shoppers."""
    with _write_transaction(pid):
        if len(list_sites(pid)) >= _MAX_SITES:
            raise AppError(f"A project can keep up to {_MAX_SITES} online stores; delete one first", 409)
        source = get_site(pid, site_id)
        now = now_iso()
        copy = source.model_copy(update={
            "id": f"site_{uuid.uuid4().hex[:12]}", "name": request.name or f"{source.name} B"[:60],
            "variant_of": source.id, "note": request.note, "options": request.options or source.options,
            "products": request.products if request.products is not None else source.products,
            "ads": request.ads if request.ads is not None else source.ads,
            "created_at": now, "updated_at": now,
        })
        _check(copy)
        write_json(_site_path(pid, copy.id), copy.model_dump(mode="json"))
    return copy


class StoreChangesRequest(BaseModel):
    """A marketing A/B variant's changes, to make a variant of an online store with."""
    name: str = Field(default="", max_length=60)
    note: str = Field(default="", max_length=400)
    currency: str = Field(min_length=3, max_length=3, description="the currency of the test's prices")
    changes: list[VariantChange] = Field(min_length=1, max_length=20)


class StoreChangesResult(BaseModel):
    site: OnlineSite  # the new variant
    applied: list[str]
    skipped: list[str]


def variant_from_changes(pid: str, site_id: str, req: StoreChangesRequest) -> StoreChangesResult:
    """A variant of this online store with a marketing test's changes, matched by SKU (see engine/online/store_changes)."""
    site = get_site(pid, site_id)
    if site.currency.upper() != req.currency.upper():
        raise AppError(f"This store's prices are in {site.currency.upper()} and the test's in {req.currency.upper()}; "
                       "pick a store in the same currency", 400)
    uris: dict[str, str] = {}
    for change in req.changes:
        if change.kind == "package" and change.asset_id:
            try:
                uris[change.asset_id] = "file://" + str(package_path(pid, change.asset_id).resolve())
            except AppError:
                continue  # reported as skipped below
    minor = 1 if site.currency.upper() in ZERO_DECIMAL else 100
    products, applied, skipped = apply_store_changes(site, req.changes, minor_per_major=minor, package_uris=uris)
    if not applied:
        raise AppError("None of these changes fits this store: " + "; ".join(skipped[:3]), 400)
    copy = copy_site(pid, site_id, CopySiteRequest(name=req.name or f"{site.name} B"[:60], note=req.note, products=products))
    return StoreChangesResult(site=copy, applied=applied, skipped=skipped)


def delete_site(pid: str, site_id: str) -> None:
    with _write_transaction(pid):
        path = _site_path(pid, site_id)
        if not path.exists():
            raise AppError(f"online store not found: {site_id}", 404)
        path.unlink()


# ── browsing ───────────────────────────────────────────────────────────────────


def _picture(pid: str, run_id: str | None = None) -> ProductPicture:
    frozen = (run_id is not None and
              OnlineRunStatus.model_validate(read_json(_run_dir(pid, run_id) / "status.json")).image_snapshot)
    if frozen and run_id is not None:
        try:
            loader = snapshot_image_loader(_run_dir(pid, run_id) / "images")
        except (OSError, ValueError) as exc:
            raise AppError("This run's saved product images are unavailable", 404) from exc
    else:
        loader = project_image_loader(pid)

    def picture(product: OnlineProduct) -> Image.Image | None:
        if not product.image_url and not product.sku:
            return None
        return loader(SlotItem(sku=product.sku or product.id, name=product.name, price=product.price,
                               image_url=product.image_url or None))

    return picture


def _bundled_picture(product: OnlineProduct) -> Image.Image | None:
    return bundled_product_image(product.image_url) if product.image_url else None


def page_view(site: OnlineSite, state: BrowserState, *, mark_seed: int = 0, picture: ProductPicture | None = None,
              render: bool = True, vision: Vision = "typical") -> PageView:
    page = build_page(site, state)
    numbers = numbering(page, mark_seed)
    shot = see_as(render_page(page, site, numbers, picture), vision, large_text=page.large_text) if render else None
    options = sorted((PageOption(kind=c.action.kind, target=c.action.target, label=c.action.label,
                                 ad_id=c.action.ad_id, number=numbers[c.index], box=shot.boxes.get(c.index) if shot else None)
                      for c in page.active), key=lambda o: o.number)
    return PageView(url=page.url, title=page.title, page=page.kind, options=options, outline=outline(page, site),
                    state=state, image=shot.data_url() if shot else "", width=shot.width if shot else 0,
                    height=shot.height if shot else 0)


def browse(pid: str, site_id: str, request: BrowseRequest) -> PageView:
    """The page after using one option of the current page (or the landing page of a new visit)."""
    site = get_site(pid, site_id)
    state = request.state or initial_state(site, device=request.device)
    if request.option is not None:
        page = build_page(site, state)
        numbers = numbering(page, request.mark_seed)
        index = next((i for i, n in numbers.items() if n == request.option), None)
        if index is None:
            raise AppError("That option is not on this page", 400)
        action = page.controls[index].action
        if action.kind == ActionKind.SEARCH and not request.query.strip():
            raise AppError("Type what to search for", 400)
        if action.kind == ActionKind.LEAVE:
            state = initial_state(site, device=state.device).model_copy(update={"notice": "You left the site. This is a new visit."})
        else:
            state = apply(site, state, action, query=request.query, has_account=request.has_account)
    return page_view(site, state, mark_seed=request.mark_seed, picture=_picture(pid), vision=request.vision)


@lru_cache(maxsize=64)
def template_preview(template_id: str, currency: str) -> bytes:
    """The home page of a template, without popups or badges (gallery thumbnails)."""
    if template_id not in template_ids():
        raise AppError(f"unknown online store template: {template_id}", 404)
    site = build_site(template_id, site_id="preview", currency=currency)
    state = BrowserState(cookies_answered=True)
    return render_page(build_page(site, state), site, {}, _bundled_picture).png


def design_chat(pid: str, site_id: str, req: DesignChatRequest, config: SimulationConfig) -> DesignChatReply:
    """The designer model's reply to the owner's latest message, with its changes applied to the design being edited
    (validated like the designer form). Nothing is saved."""
    site = get_site(pid, site_id)
    if req.messages[-1].role != "owner":
        raise AppError("The last message must be the owner's", 400)
    options = req.options or site.options
    llm_config = config.llm_for(EngineType.PATTERN_INTENT_IMPULSE).model_copy(update={"temperature": 0.2, "max_tokens": 900})
    try:
        model = assistive_model(req.model, llm_config)
        llm = assistive_client(model, llm_config)
    except ValueError as e:
        raise AppError(str(e), 400) from e
    try:
        reply = asyncio.run(chat_design(llm, site, options, req.messages))
        edited, changed = apply_design(options, reply.changes, site.currency)
    except Exception as e:  # provider errors and unusable proposals reach the owner as a message, not a 500
        logger.warning(f"[online design chat] {pid}/{site_id}: {type(e).__name__}: {e}")
        raise AppError(model_failure(e, "The design could not be changed"), 502) from e
    return DesignChatReply(reply=reply.reply, options=edited, changed=changed, model=answered_by(llm, model))


class DraftPreviewRequest(BaseModel):
    options: SiteOptions
    device: Device = "desktop"


def draft_preview(pid: str, site_id: str, options: SiteOptions, device: Device) -> bytes:
    """The home page of a store with a design that is not saved yet (the design chat's proposal)."""
    site = get_site(pid, site_id).model_copy(update={"options": options})
    state = BrowserState(cookies_answered=True, device=device)
    return render_page(build_page(site, state), site, {}, _picture(pid)).png


def site_preview(pid: str, site_id: str, device: Device, style: PageStyle | None = None) -> bytes:
    site = get_site(pid, site_id)
    if style is not None:
        site = site.model_copy(update={"options": site.options.model_copy(update={"page_style": style})})
    state = BrowserState(cookies_answered=True, device=device)
    return render_page(build_page(site, state), site, {}, _picture(pid)).png


# ── runs ───────────────────────────────────────────────────────────────────────


def _write_status(pid: str, status: OnlineRunStatus) -> None:
    write_json(_run_dir(pid, status.run_id) / "status.json", status.model_dump(mode="json"))


def _policy(request: OnlineRunRequest, config: SimulationConfig) -> tuple[ShopperPolicy, str]:
    """The shopper policy of a run and the model it uses ("" for rules). Raises AppError when the model cannot be used."""
    if request.policy == "rule":
        return RulePolicy(), ""
    if request.ensemble is not None and request.ensemble.mode != "mixture":
        raise AppError("Online shoppers support mixture ensembles (one model per shopper); "
                       "voting is only available for physical-store vision glances", 400)
    ensemble = request.ensemble if request.ensemble is not None and request.ensemble.members else None
    if request.policy == "vlm":
        run_config = with_vision_default(
            config.model_copy(update={"engine_type": EngineType.VLM_GLANCE, "ensemble": ensemble}), request.model)
        engine = EngineType.VLM_GLANCE
    else:
        run_config = config.model_copy(update={"engine_type": EngineType.PATTERN_INTENT_IMPULSE, "ensemble": ensemble})
        if request.model:
            run_config = with_engine_model(run_config, request.model)
        engine = EngineType.PATTERN_INTENT_IMPULSE
    try:
        ensure_resolvable(run_config)
    except ValueError as e:
        raise AppError(str(e), 400) from e
    llm_config = run_config.llm_for(engine)
    label = " + ".join(m.model for m in ensemble.members) if ensemble else request.model or llm_config.model
    return ModelPolicy(build_client(llm_config, ensemble), vision=request.policy == "vlm"), label


def start_run(pid: str, request: OnlineRunRequest, config: SimulationConfig) -> OnlineRunStatus:
    if len(set(request.site_ids)) != len(request.site_ids):
        raise AppError("Pick each online store once", 400)
    if not any(w > 0 for w in request.missions.values()):
        raise AppError("Give at least one shopping mission a share above zero", 400)
    if not any(w > 0 for w in request.arrivals.values()):
        raise AppError("Give at least one traffic source a share above zero", 400)
    if request.rival_site_id is not None and request.rival_site_id in request.site_ids:
        raise AppError("Pick a rival shop that is not one of the stores being compared", 400)
    policy, model = _policy(request, config)
    run_id = f"orun_{uuid.uuid4().hex[:12]}"
    with _write_transaction(pid):
        sites = [get_site(pid, site_id) for site_id in request.site_ids]
        if len({site.currency for site in sites}) != 1:
            raise AppError("Compare online stores using the same currency so shopper budgets and order totals are comparable", 400)
        rival = get_site(pid, request.rival_site_id) if request.rival_site_id is not None else None
        if rival is not None and rival.currency != sites[0].currency:
            raise AppError("Pick a rival shop in the same currency as the stores being compared", 400)
        personas = read_personas(pid) if request.source == "project" else None
        if request.source == "project" and not personas:
            raise AppError("This project has no customers yet: generate them, or use the built-in panel", 400)
        shoppers = sample_shoppers(sites[0], request.shoppers, seed=request.seed, missions=request.missions,
                                   mobile_share=request.mobile_share, personas=personas,
                                   accessibility=request.accessibility, arrivals=request.arrivals)
        status = OnlineRunStatus(
            run_id=run_id, name=request.name or " vs ".join(s.name for s in sites)[:80], site_ids=[s.id for s in sites],
            site_names=[s.name for s in sites], status="pending",
            total=len(shoppers) * (len(sites) + (rival is not None)), request=request,
            created_at=now_iso(), image_snapshot=True,
        )
        folder = _run_dir(pid, run_id)
        folder.mkdir(parents=True, exist_ok=False)
        try:
            snapshot_project_images(pid, (
                SlotItem(sku=p.sku or p.id, name=p.name, price=p.price, image_url=p.image_url or None)
                for site in [*sites, rival] if site is not None
                for p in site.products if p.sku or p.image_url
            ), folder / "images")
            write_json(folder / "sites.json", _SITES.dump_python(sites, mode="json"))
            if rival is not None:
                write_json(folder / "rival.json", rival.model_dump(mode="json"))
            write_json(folder / "shoppers.json", _SHOPPERS.dump_python(shoppers, mode="json"))
            _write_status(pid, status)
            picture = _picture(pid, run_id)
        except Exception:
            remove_tree(folder)
            raise
    try:
        submit_background(executor, _run_job, pid, status, sites, shoppers, policy, model, picture, rival)
    except RuntimeError as exc:
        status.status, status.finished_at = "failed", now_iso()
        status.error = "Could not start the online run. Please retry when the worker is available."
        _write_status(pid, status)
        raise AppError(status.error, 503) from exc
    return status


def _run_job(pid: str, status: OnlineRunStatus, sites: list[OnlineSite], shoppers: list[OnlineShopper],
             policy: ShopperPolicy, model: str, picture: ProductPicture, rival: OnlineSite | None = None) -> None:
    started = time.monotonic()
    status.status = "running"
    last = 0.0

    def progress(phase: str) -> None:
        nonlocal last
        status.done += 1
        status.phase = phase
        now = time.monotonic()
        if status.done < status.total and now - last < _MIN_STATUS_INTERVAL_SEC:
            return
        last = now
        _write_status(pid, status)

    try:
        _write_status(pid, status)
        request = status.request
        variants, at_rival_shop = asyncio.run(_simulate(sites, shoppers, policy, request, picture, progress, rival))
        if isinstance(policy, ModelPolicy) and not policy.answered and policy.last_failure is not None:
            raise policy.last_failure
        for index, sessions in enumerate([*variants, at_rival_shop] if rival is not None else variants):
            write_json(_run_dir(pid, status.run_id) / f"sessions-{index}.json", _SESSIONS.dump_python(sessions, mode="json"))
        by_id = {s.id: s for s in shoppers}
        with_rival = rival is not None
        summaries = [summarize(site, by_id, sessions, with_rival=with_rival)
                     for site, sessions in zip(sites, variants, strict=True)]
        comparisons: list[VariantComparison] = []
        for site, sessions, summary in zip(sites[1:], variants[1:], summaries[1:], strict=True):
            won, lost, changed, switched = switches(variants[0], sessions)
            comparisons.append(VariantComparison(
                site_id=site.id, site_name=site.name,
                deltas=paired_deltas(variants[0], sessions, seed=request.seed, with_rival=with_rival),
                ad_lifts=ad_lifts(sites[0], variants[0], summaries[0].ads, site, sessions, summary.ads),
                segments=segment_deltas(variants[0], sessions, by_id, seed=request.seed), won=won, lost=lost,
                changed=changed, switches=switched,
            ))
        requests = sum(s.model_requests for sessions in [*variants, at_rival_shop] for s in sessions)
        fallbacks = sum(s.fallbacks for sessions in [*variants, at_rival_shop] for s in sessions)
        notes = ["Virtual shoppers, not real traffic: use the differences between variants, measured on the same "
                 "shoppers, rather than the absolute rates."]
        if request.policy == "rule":
            notes.append("Rule shoppers follow illustrative, uncalibrated probabilities. Use a vision model to let "
                         "shoppers react to what each page actually shows.")
        if fallbacks:
            notes.append(f"{fallbacks} of {requests} model decisions failed and were made by the rules instead.")
        result = OnlineRunResult(
            run_id=status.run_id, name=status.name, policy=request.policy, model=model, currency=sites[0].currency,
            variants=summaries, comparisons=comparisons, shoppers=shoppers, model_requests=requests,
            fallbacks=fallbacks, seconds=round(time.monotonic() - started, 1), notes=notes,
            rival_name=rival.name if rival is not None else "",
            visits={shopper.id: [VisitBrief(outcome=sessions[i].outcome, order_total=sessions[i].order_total,
                                            clicks=sum(1 for step in sessions[i].steps if step.choice is not None),
                                            rival=r.outcome if (r := sessions[i].rival) else None,
                                            furthest=max(sessions[i].reached, key=FUNNEL_STAGES.index))
                                 for sessions in variants]
                    for i, shopper in enumerate(shoppers)},
        )
        write_json(_run_dir(pid, status.run_id) / "result.json", json.loads(result.model_dump_json()))
        status.status, status.phase, status.finished_at = "completed", "done", now_iso()
        _write_status(pid, status)
    except Exception as e:  # surface any failure to the UI instead of a stuck job
        logger.exception(f"[online] run {status.run_id} failed")
        status.status = "failed"
        status.error = job_failure(e, "The online run failed")
        status.finished_at = now_iso()
        _write_status(pid, status)


async def _simulate(sites: list[OnlineSite], shoppers: list[OnlineShopper], policy: ShopperPolicy,
                    request: OnlineRunRequest, picture: ProductPicture, progress: Callable[[str], None],
                    rival: OnlineSite | None = None) -> tuple[list[list[SessionResult]], list[SessionResult]]:
    """Every shopper's visit to each variant, then, with a rival shop, the visits of those who left a variant without
    buying and try the rival. A rival visit is the same whichever variant the shopper left, so it runs once and is
    attached to each of their visits that ended without an order."""
    render = request.policy == "vlm"
    surveyor = policy.survey if isinstance(policy, ModelPolicy) and request.exit_survey else None
    slots = asyncio.Semaphore(_MODEL_CONCURRENCY if request.policy != "rule" else 1)
    out: list[list[SessionResult]] = []

    async def one(site: OnlineSite, shopper: OnlineShopper, phase: str, surveyor: Surveyor | None, seed: int) -> SessionResult:
        async with slots:
            result = await run_session(site, shopper, policy, seed=seed, max_steps=request.max_steps,
                                       render=render, shuffle_marks=request.shuffle_marks,
                                       image_width=request.image_width, picture=picture, surveyor=surveyor)
        progress(phase)
        return result

    for index, site in enumerate(sites):
        phase = f"variant {index + 1} of {len(sites)}"
        visiting: list[OnlineShopper] = shoppers
        if index:
            # Product/category IDs belong to one catalog. Match the original intent before
            # visiting another store, where the same ID may describe an unrelated item.
            category_ids: dict[str, str] = {}
            for category in sites[0].categories:
                matches = [c.id for c in site.categories if c.name.strip().casefold() == category.name.strip().casefold()]
                category_ids[category.id] = (category.id if category.id in matches
                                             else matches[0] if len(matches) == 1 else "")
            product_ids: dict[str, str] = {}
            local_ids = {p.id for p in site.products}
            for product in sites[0].products:
                if product.sku:
                    matches = [p.id for p in site.products if p.sku == product.sku]
                else:
                    matches = [p.id for p in site.products
                               if p.name.strip().casefold() == product.name.strip().casefold()
                               and p.category_id == category_ids.get(product.category_id)]
                if product.id in matches:
                    target = product.id
                elif len(matches) == 1:
                    target = matches[0]
                else:
                    # A nonempty, absent target retains the rule shopper's preference for
                    # a specific unavailable product, instead of turning it into a generic goal.
                    target = product.id
                    while target in local_ids:
                        target = f"missing:{target}"
                product_ids[product.id] = target
            visiting = []
            for shopper in shoppers:
                target_id = product_ids.get(shopper.target_product, shopper.target_product)
                target_product = site.product(target_id) if target_id else None
                visiting.append(shopper.model_copy(update={
                    "target_product": target_id,
                    "target_category": (target_product.category_id if target_product is not None
                                        else category_ids.get(shopper.target_category, "")),
                }))

        out.append(list(await asyncio.gather(*(one(site, s, phase, surveyor, request.seed) for s in visiting))))
    if rival is None:
        return out, []
    lost = [there for i, s in enumerate(shoppers)
            if any(v[i].outcome != "purchased" for v in out) and tries_rival(s, request.seed)
            and (there := at_rival(rival, s, sites[0])) is not None]
    for _ in range(len(shoppers) - len(lost)):
        progress("rival shop")
    # No exit survey at the rival: the survey is about the stores being compared. The visit draws its own random
    # numbers: on the run's seed it would replay, page for page, the visit the shopper just left at a store like it.
    visits = list(await asyncio.gather(*(one(rival, s, "rival shop", None, stable_seed(request.seed, "online-rival-visit"))
                                         for s in lost)))
    went = {v.shopper_id: RivalVisit(outcome=v.outcome, order_total=v.order_total, exit_thought=v.exit_thought,
                                     steps=sum(1 for step in v.steps if step.choice is not None)) for v in visits}
    return [[s.model_copy(update={"rival": went[s.shopper_id]}) if s.outcome != "purchased" and s.shopper_id in went
             else s for s in sessions] for sessions in out], visits


def list_runs(pid: str) -> list[OnlineRunStatus]:
    base = _root(pid) / "runs"
    if not base.is_dir():
        return []
    runs: list[OnlineRunStatus] = []
    for folder in base.iterdir():
        if (folder / "status.json").exists():
            try:
                runs.append(OnlineRunStatus.model_validate(read_json(folder / "status.json")))
            except ValueError as e:
                logger.warning(f"[online] skipping run {pid}/{folder.name}: {e}")
    return sorted(runs, key=lambda r: r.created_at, reverse=True)


def get_run(pid: str, run_id: str) -> OnlineRunView:
    path = _run_dir(pid, run_id) / "status.json"
    if not path.exists():
        raise AppError(f"online run not found: {run_id}", 404)
    status = OnlineRunStatus.model_validate(read_json(path))
    result_path = _run_dir(pid, run_id) / "result.json"
    result = OnlineRunResult.model_validate(read_json(result_path)) if result_path.exists() else None
    return OnlineRunView(status=status, result=result)


class PersonaVisit(BaseModel):
    """One online visit of a project customer: a run's shopper made from them, at one store of the run."""
    run_id: str
    run_name: str
    created_at: str
    variant: int
    site_name: str
    shopper_id: str
    outcome: SessionOutcome
    order_total: int
    currency: str


def persona_visits(pid: str, persona_id: str) -> list[PersonaVisit]:
    """Where this customer shopped online: every finished run that drew shoppers from the project's customers, newest
    first, one row per store they visited (runs saved before visits were recorded are left out)."""
    visits: list[PersonaVisit] = []
    for status in list_runs(pid):
        if status.status != "completed" or status.request.source != "project":
            continue
        result = get_run(pid, status.run_id).result
        if result is None:
            continue
        for shopper in result.shoppers:
            if shopper.persona_id != persona_id:
                continue
            for variant, brief in enumerate((result.visits or {}).get(shopper.id, [])):
                if variant < len(result.variants):
                    visits.append(PersonaVisit(
                        run_id=status.run_id, run_name=status.name or " vs ".join(status.site_names),
                        created_at=status.created_at, variant=variant, site_name=result.variants[variant].site_name,
                        shopper_id=shopper.id, outcome=brief.outcome, order_total=brief.order_total, currency=result.currency))
    return visits[:60]


def delete_run(pid: str, run_id: str) -> None:
    with _write_transaction(pid):
        view = get_run(pid, run_id)
        if view.status.status in ("pending", "running"):
            raise AppError("This run is still going; delete it when it has finished", 409)
        remove_tree(_run_dir(pid, run_id))


def _snapshot(pid: str, run_id: str) -> tuple[list[OnlineSite], list[OnlineShopper]]:
    folder = _run_dir(pid, run_id)
    if not (folder / "sites.json").exists():
        raise AppError(f"online run not found: {run_id}", 404)
    return _SITES.validate_python(read_json(folder / "sites.json")), _SHOPPERS.validate_python(read_json(folder / "shoppers.json"))


def _sessions(pid: str, run_id: str, variant: int) -> list[SessionResult]:
    path = _run_dir(pid, run_id) / f"sessions-{variant}.json"
    if not path.exists():
        raise AppError("This run has no sessions for that store yet", 404)
    return _SESSIONS.validate_python(read_json(path))


def _stores(pid: str, run_id: str) -> list[OnlineSite]:
    """The run's copies of its stores: the variants, then the rival shop if the run has one."""
    sites, _ = _snapshot(pid, run_id)
    path = _run_dir(pid, run_id) / "rival.json"
    return [*sites, OnlineSite.model_validate(read_json(path))] if path.exists() else sites


def get_session(pid: str, run_id: str, variant: int, shopper_id: str) -> SessionView:
    """One shopper's visit to one store of the run; the index after the variants is their visit to the rival shop."""
    sites, shoppers = _snapshot(pid, run_id)
    stores = _stores(pid, run_id)
    if not 0 <= variant < len(stores):
        raise AppError("No such store in this run", 404)
    session = next((s for s in _sessions(pid, run_id, variant) if s.shopper_id == shopper_id), None)
    shopper = next((s for s in shoppers if s.id == shopper_id), None)
    if session is None or shopper is None:
        raise AppError(f"shopper not found in this run: {shopper_id}", 404)
    if variant == len(sites):
        shopper = at_rival(stores[variant], shopper, sites[0]) or shopper
    return SessionView(variant=variant, site_id=stores[variant].id, site_name=stores[variant].name, shopper=shopper,
                       session=session)


class RunStoreChanges(BaseModel):
    """A variant's prices from an online run, as changes for a physical layout (see engine/online/store_changes)."""
    name: str
    currency: str
    changes: list[VariantChange]
    skipped: list[str]


def run_store_changes(pid: str, run_id: str, variant: int) -> RunStoreChanges:
    sites, _ = _snapshot(pid, run_id)
    if not 1 <= variant < len(sites):
        raise AppError("Pick a variant of this run, not its control", 404)
    changes, skipped = price_changes(sites[0], sites[variant])
    if len(changes) > MAX_LAYOUT_EDIT_CHANGES:
        raise AppError(f"This variant changes {len(changes)} prices; a layout can accept at most "
                       f"{MAX_LAYOUT_EDIT_CHANGES} price changes at once. Use a variant with fewer price changes.", 400)
    return RunStoreChanges(name=sites[variant].name[:80], currency=sites[variant].currency.upper(), changes=changes,
                           skipped=skipped)


def _analyst_path(pid: str, run_id: str) -> Path:
    return _run_dir(pid, run_id) / "analyst.json"


def get_analyst(pid: str, run_id: str) -> AnalystThread:
    """Questions asked about this online run and the analyst's answers."""
    get_run(pid, run_id)
    path = _analyst_path(pid, run_id)
    return AnalystThread.model_validate(read_json(path)) if path.exists() else AnalystThread(run_id=run_id)


@contextmanager
def _analyst_lock(pid: str, run_id: str) -> Iterator[None]:
    digest = hashlib.sha256(run_id.encode()).hexdigest()
    lock = FileLock(setup_lock_path(pid, "online-analyst").with_name(f"online-analyst_{digest}.lock"), timeout=0)
    try:
        lock.acquire()
    except Timeout as e:
        raise AppError("The previous question is still being answered. Try again in a moment.", 409) from e
    try:
        yield
    finally:
        lock.release()


def ask_analyst(pid: str, run_id: str, q: AnalystQuestion, config: SimulationConfig) -> AnalystThread:
    """The question and the analyst's answer, read off the run's report, added to the run's analyst thread."""
    with _analyst_lock(pid, run_id):
        with _write_transaction(pid):
            result = get_run(pid, run_id).result
            if result is None:
                raise AppError("This run has no results yet", 409)
            thread = get_analyst(pid, run_id)
        llm_config = config.llm_for(EngineType.PATTERN_INTENT_IMPULSE).model_copy(update={"temperature": 0.2, "max_tokens": 1600})
        try:
            model = assistive_model(q.model, llm_config)
            llm = assistive_client(model, llm_config)
        except ValueError as e:
            raise AppError(str(e), 400) from e
        try:
            answer = asyncio.run(answer_online_question(llm, result, q.question, thread.messages,
                                                        seed=stable_seed("online-analyst", run_id, len(thread.messages))))
        except Exception as e:  # provider errors reach the user as advice
            logger.warning(f"[online analyst] {pid}/{run_id}: {type(e).__name__}: {e}")
            raise AppError(model_failure(e, "The question could not be answered"), 502) from e
        thread.model = answered_by(llm, model)
        thread.messages += [
            AnalystMessage(role="user", text=q.question, created_at=now_iso()),
            AnalystMessage(role="analyst", text=answer.answer, figures=answer.figures, follow_ups=answer.follow_ups,
                           created_at=now_iso()),
        ]
        with _write_transaction(pid):
            if not (_run_dir(pid, run_id) / "status.json").is_file():
                raise AppError(f"online run not found: {run_id}", 404)
            write_json(_analyst_path(pid, run_id), thread.model_dump(mode="json"))
        return thread


def suggest_analyst_questions(pid: str, run_id: str, model: str, config: SimulationConfig) -> list[str]:
    """Three starter questions read off this run's report (what stands out); nothing is kept."""
    result = get_run(pid, run_id).result
    if result is None:
        raise AppError("This run has no results yet", 409)
    llm_config = config.llm_for(EngineType.PATTERN_INTENT_IMPULSE).model_copy(update={"temperature": 0.3, "max_tokens": 500})
    try:
        llm = assistive_client(assistive_model(model, llm_config), llm_config)
    except ValueError as e:
        raise AppError(str(e), 400) from e
    try:
        return asyncio.run(suggest_online_questions(llm, result))
    except Exception as e:  # provider errors reach the user as advice
        logger.warning(f"[online analyst] suggestions {pid}/{run_id}: {type(e).__name__}: {e}")
        raise AppError(model_failure(e, "No questions could be suggested"), 502) from e


def clear_analyst(pid: str, run_id: str) -> None:
    with _analyst_lock(pid, run_id), _write_transaction(pid):
        get_run(pid, run_id)
        _analyst_path(pid, run_id).unlink(missing_ok=True)


def run_report_html(pid: str, run_id: str) -> str:
    """The run's report as one page to share or print, with the questions asked about it."""
    view = get_run(pid, run_id)
    if view.result is None:
        raise AppError("This run has no results yet", 409)
    return online_report_html(view.result, view.status.created_at, get_analyst(pid, run_id))


def analyst_facts(pid: str, run_id: str) -> str:
    result = get_run(pid, run_id).result
    if result is None:
        raise AppError("This run has no results yet", 409)
    return online_facts(result)


def _interview_path(pid: str, run_id: str, variant: int, shopper_id: str) -> Path:
    return _run_dir(pid, run_id) / "interviews" / f"{variant}-{shopper_id}.json"


@contextmanager
def _interview_lock(pid: str, run_id: str, variant: int, shopper_id: str) -> Iterator[None]:
    digest = hashlib.sha256(json.dumps([run_id, variant, shopper_id]).encode()).hexdigest()
    # Lock files outlive runs; acquiring a lock must not recreate a deleted run folder.
    path = setup_lock_path(pid, "online-interview").with_name(f"online-interview_{digest}.lock")
    lock = FileLock(path, timeout=0)
    try:
        lock.acquire()
    except Timeout as e:
        raise AppError("This shopper is answering a question. Try again when the answer is complete.", 409) from e
    try:
        yield
    finally:
        lock.release()


def get_interview(pid: str, run_id: str, variant: int, shopper_id: str) -> OnlineInterview:
    get_session(pid, run_id, variant, shopper_id)  # an unknown shopper is not one who said nothing
    path = _interview_path(pid, run_id, variant, shopper_id)
    if path.exists():
        return OnlineInterview.model_validate(read_json(path))
    return OnlineInterview(run_id=run_id, variant=variant, shopper_id=shopper_id)


def ask_shopper(pid: str, run_id: str, variant: int, shopper_id: str, q: InterviewQuestion,
                config: SimulationConfig) -> OnlineInterview:
    """The researcher's question and the shopper's answer, added to their conversation about this visit."""
    with _interview_lock(pid, run_id, variant, shopper_id):
        with _write_transaction(pid):
            view = get_session(pid, run_id, variant, shopper_id)
            sites = _stores(pid, run_id)
            transcript = get_interview(pid, run_id, variant, shopper_id)
        llm_config = config.llm_for(EngineType.PATTERN_INTENT_IMPULSE).model_copy(update={"temperature": 0.7, "max_tokens": 700})
        try:
            model = assistive_model(q.model, llm_config)
            llm = assistive_client(model, llm_config)
        except ValueError as e:
            raise AppError(str(e), 400) from e
        question = q.question.strip()
        try:
            reply = asyncio.run(interview_shopper(llm, sites[variant], view.shopper, view.session, transcript.messages,
                                                  question, run_id=run_id))
        except Exception as e:  # provider errors reach the user as a message, not a 500
            logger.warning(f"[online interview] {pid}/{run_id}/{variant}/{shopper_id}: {type(e).__name__}: {e}")
            raise AppError(model_failure(e, "The shopper could not answer"), 502) from e
        transcript.model = answered_by(llm, model)
        transcript.messages += [
            InterviewMessage(role="interviewer", text=question, created_at=now_iso()),
            InterviewMessage(role="shopper", text=reply.answer, steps=reply.steps, created_at=now_iso()),
        ]
        with _write_transaction(pid):
            if not (_run_dir(pid, run_id) / "status.json").is_file():
                raise AppError(f"online run not found: {run_id}", 404)
            write_json(_interview_path(pid, run_id, variant, shopper_id), transcript.model_dump(mode="json"))
        return transcript


def clear_interview(pid: str, run_id: str, variant: int, shopper_id: str) -> None:
    with _interview_lock(pid, run_id, variant, shopper_id), _write_transaction(pid):
        get_session(pid, run_id, variant, shopper_id)
        _interview_path(pid, run_id, variant, shopper_id).unlink(missing_ok=True)


def step_screenshot(pid: str, run_id: str, variant: int, shopper_id: str, step: int, *, highlight: bool = True) -> bytes:
    """The page as this shopper saw it at this step (drawn again from the run's own copy of the site), with what they
    clicked circled unless `highlight` is off (an animated playback draws the click itself)."""
    view = get_session(pid, run_id, variant, shopper_id)
    found = next((s for s in view.session.steps if s.index == step), None)
    if found is None:
        raise AppError("No such step in this session", 404)
    site = _stores(pid, run_id)[variant]
    picture = _picture(pid, run_id)
    return _seen(site, view.shopper, found, picture) if highlight else _shot(site, view.shopper, found, picture)[0].png


def playback(pid: str, run_id: str, variant: int, shopper_id: str) -> list[PlaybackFrame]:
    """Where each click of a visit landed on its screenshot, for an animated playback of the visit."""
    view = get_session(pid, run_id, variant, shopper_id)
    site, picture = _stores(pid, run_id)[variant], _picture(pid, run_id)
    frames: list[PlaybackFrame] = []
    for step in view.session.steps:
        # Eyesight filters blur pixels but move no box, and they are the slow part of drawing a page.
        shot, box = _shot(site, view.shopper, step, picture, eyes=False)
        frames.append(PlaybackFrame(step=step.index, width=shot.width, height=shot.height, box=box))
    return frames


def journey_gif(pid: str, run_id: str, variant: int, shopper_id: str) -> bytes:
    """The whole visit as an animated GIF to share: every page as the shopper saw it with their click circled, what
    they did and what they thought."""
    view = get_session(pid, run_id, variant, shopper_id)
    site, picture, steps = _stores(pid, run_id)[variant], _picture(pid, run_id), view.session.steps
    frames: list[tuple[bytes, str, str]] = []
    for n, step in enumerate(steps, start=1):
        page = step.page.value.replace("_", " ")
        did = (f'searched "{step.search_text}"' if step.choice is not None and step.search_text
               else step.choice.label if step.choice is not None else view.session.outcome.replace("_", " "))
        frames.append((_seen(site, view.shopper, step, picture), f"{n}/{len(steps)} · {page} → {did}", step.thought))
    return animate(frames)


def _shot(site: OnlineSite, shopper: OnlineShopper, found: SessionStep, picture: ProductPicture, *,
          eyes: bool = True) -> tuple[Screenshot, tuple[int, int, int, int] | None]:
    """The step's screenshot through the shopper's eyes (`eyes`; otherwise as drawn), and the box of the option they
    chose."""
    page = build_page(site, found.state)
    numbers = numbering(page, found.mark_seed)
    shot = render_page(page, site, numbers, picture)
    if eyes:
        shot = see_as(shot, shopper.vision, large_text=page.large_text)
    chosen = next((i for i, n in numbers.items() if found.choice is not None and n == found.choice.number), None)
    return shot, shot.boxes.get(chosen) if chosen is not None else None


def _seen(site: OnlineSite, shopper: OnlineShopper, found: SessionStep, picture: ProductPicture) -> bytes:
    shot, box = _shot(site, shopper, found, picture)
    if box is None:
        return shot.png
    with Image.open(io.BytesIO(shot.png)) as source:
        image = source.convert("RGB")
    ImageDraw.Draw(image).rounded_rectangle((box[0] - 3, box[1] - 3, box[2] + 3, box[3] + 3), radius=8,
                                            outline=(244, 63, 94), width=4)
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def export_clickstream(pid: str, run_id: str) -> str:
    view = get_run(pid, run_id)
    if view.status.status != "completed":
        raise AppError("The run has not finished yet", 409)
    sites, shoppers = _snapshot(pid, run_id)
    stores = _stores(pid, run_id)
    visitors = [{s.id: s for s in shoppers} for _ in sites]
    if len(stores) > len(sites):  # the rival's visitors, as they arrived there
        visitors.append({s.id: there for s in shoppers if (there := at_rival(stores[-1], s, sites[0])) is not None})
    return clickstream_csv([(site, _sessions(pid, run_id, i), visitors[i]) for i, site in enumerate(stores)])
