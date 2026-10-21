"""Where a request typed in plain words belongs in the app.

"Would a 1+1 on cola beat a 20 % cut?" is an A/B test; "what would people pay for zero sugar?" a conjoint study;
"why does the freezer sell so little?" a question about the last run. The model only picks the place; the page it
opens drafts the rest from the same words.
"""

from typing import Literal, Protocol

from pydantic import BaseModel, Field

Destination = Literal["ab_test", "conjoint", "staff_script", "area", "run_question", "none"]


class StructuredLLM(Protocol):
    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str,
        *, max_retries: int = 1, seed: int | None = None,
    ) -> T: ...


class AssistRoute(BaseModel):
    destination: Destination
    reason: str = Field(default="", max_length=160, description="a few words on why")


ROUTER_PROMPT = """You route a store manager's request to the right tool of a store simulator:
- ab_test: compare changes on the shelves (price, discount, promotion sign, placement, new package) on the same shoppers;
- conjoint: what features or price levels of one product shoppers prefer or would pay for;
- staff_script: what staff should say to shoppers;
- area: the neighborhood around the store (who lives or works nearby, rivals, nearby venues);
- run_question: a question about what happened in the last simulated day (sales, shelves, hours, shoppers);
- none: anything else.
{run_note}Pick one and give a few words on why."""


async def route_request(llm: StructuredLLM, text: str, *, has_run: bool) -> AssistRoute:
    note = "" if has_run else "There is no simulated day yet, so run_question is not available.\n"
    route = await llm.generate_structured_async(AssistRoute, ROUTER_PROMPT.format(run_note=note), text.strip(), max_retries=2, seed=0)
    if route.destination == "run_question" and not has_run:
        return route.model_copy(update={"destination": "none"})
    return route
