"""Where a request typed in plain words belongs in the app.

"Would a 1+1 on cola beat a 20 % cut?" is an A/B test; "what would people pay for zero sugar?" a conjoint study;
"why does the freezer sell so little?" a question about the last run. The model only picks the place; the page it
opens drafts the rest from the same words.
"""

from typing import Literal, Protocol

from pydantic import BaseModel, Field

Destination = Literal[
    "ab_test", "shelf_test", "conjoint", "concept_test", "staff_script", "layout_edit", "area", "run_question",
    "find_shoppers", "none",
]


class StructuredLLM(Protocol):
    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str,
        *, max_retries: int = 1, seed: int | None = None,
    ) -> T: ...


class AssistRoute(BaseModel):
    destination: Destination
    reason: str = Field(default="", max_length=160, description="a few words on why")


ROUTER_PROMPT = """You route a store manager's request to the right tool of a store simulator:
- ab_test: compare what changes on the shelves (price, discount, promotion sign, placement, new package) do to sales
  over a simulated trading day, on the same shoppers;
- shelf_test: whether one product's new pack, price or sign stands out and gets picked when shoppers look at its
  shelf (a picture of the shelf before and after the change);
- conjoint: what features or price levels of one product shoppers prefer or would pay for;
- concept_test: how shoppers react to product packs, labels or new product ideas shown as pictures (appeal, purchase
  intent, value, which one they prefer), asked as a survey rather than on the shelf;
- staff_script: what staff should say to shoppers;
- layout_edit: change the store's layout itself now (move products, set prices or discounts, add signs), without
  testing it first;
- area: the neighborhood around the store (who lives or works nearby, rivals, nearby venues);
- run_question: a question about what happened in the last simulated day (sales, shelves, hours, shoppers);
- find_shoppers: show or list particular shoppers of the last simulated day (e.g. "students who left empty-handed");
- none: anything else.
{run_note}Pick one and give a few words on why."""


async def route_request(llm: StructuredLLM, text: str, *, has_run: bool) -> AssistRoute:
    note = "" if has_run else "There is no simulated day yet, so run_question and find_shoppers are not available.\n"
    route = await llm.generate_structured_async(AssistRoute, ROUTER_PROMPT.format(run_note=note), text.strip(), max_retries=2, seed=0)
    if route.destination in ("run_question", "find_shoppers") and not has_run:
        return route.model_copy(update={"destination": "none"})
    return route
