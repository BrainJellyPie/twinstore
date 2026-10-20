from store_emulator.domain.config import EngineType

# engine_type → (module path, class name, requires LLM)
ENGINES: dict[EngineType, tuple[str, str, bool]] = {
    EngineType.PATTERN_INTENT_IMPULSE: (".pattern_intent_impulse", "PatternIntentImpulseEngine", True),
    EngineType.RULE_BASED: (".rule_based", "RuleBasedEngine", False),
    EngineType.VLM_GLANCE: (".vlm_glance", "VLMGlanceEngine", True),
}
