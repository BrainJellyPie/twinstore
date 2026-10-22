from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.runner import SimulationRunner

from store_emulator.application.presets.behavior import BEHAVIOR_PATTERNS, sample_cue
from store_emulator.application.providers import build_client
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.perception.product_images import ProductImageLoader
from store_emulator.engine.simulation.engines import ENGINES
from store_emulator.engine.simulation.factory import build_engine
from store_emulator.engine.simulation.simulator import PerCustomerSimulationRunner


def build_runner(config: SimulationConfig, *, image_loader: ProductImageLoader | None = None) -> SimulationRunner:
    pathfinder = AStarPathFinder(diagonal=config.diagonal_moves)

    if config.engine_type not in ENGINES:
        raise ValueError(f"unsupported engine type: {config.engine_type}")

    needs_llm = ENGINES[config.engine_type][2]
    llm = build_client(config.llm_for(config.engine_type), config.ensemble) if needs_llm else None
    engine = build_engine(config, llm=llm, pathfinder=pathfinder, image_loader=image_loader)
    return PerCustomerSimulationRunner(config, engine, pathfinder, sample_cue, BEHAVIOR_PATTERNS)
