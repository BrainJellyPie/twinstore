import importlib

from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.engine import CustomerBehaviorEngine
from store_emulator.domain.types import PathFinder
from store_emulator.engine.llm_router import SimLLM
from store_emulator.engine.perception.product_images import ProductImageLoader

from .engines import ENGINES


def build_engine(
    config: SimulationConfig,
    *,
    llm: SimLLM | None = None,
    pathfinder: PathFinder,
    image_loader: ProductImageLoader | None = None,
) -> CustomerBehaviorEngine:
    entry = ENGINES.get(config.engine_type)
    if not entry:
        available = ", ".join(ENGINES.keys())
        raise ValueError(f"Unsupported engine type: {config.engine_type} (available: {available})")

    module_path, class_name, needs_llm = entry
    if needs_llm and llm is None:
        raise ValueError(f"{config.engine_type} engine requires an LLM client")

    module = importlib.import_module(module_path, package="store_emulator.engine.simulation.engines")
    engine_cls = getattr(module, class_name)

    if needs_llm:
        if config.engine_type == "vlm_glance" and image_loader is not None:
            return engine_cls(llm=llm, pathfinder=pathfinder, config=config, image_loader=image_loader)  # type: ignore[return-value]
        return engine_cls(llm=llm, pathfinder=pathfinder, config=config)  # type: ignore[return-value]
    return engine_cls(pathfinder=pathfinder, config=config)  # type: ignore[return-value]
