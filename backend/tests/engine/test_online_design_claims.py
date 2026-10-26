"""A designer reply may not pass for changes its updates do not hold: the options it mentions without setting are named."""

import pytest

from store_emulator.application import online
from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.online import DesignChatRequest, DesignMessage
from store_emulator.engine.online.catalog import build_site
from store_emulator.engine.online.design_chat import DesignReply, unapplied_mentions

# A real reply of a 450M local model on CPU: it set the colour and the home sections, and described six more changes.
NARRATED = ("I've updated the theme color to #00AA33 to give the store a more premium feel. I've also changed the home "
            "sections to include bestsellers and deals, and added a coupon code 'STYLE15' for a 15% discount. I've removed "
            "the welcome popup and the newsletter, and I've added a chat widget to improve customer service. I've also "
            "updated the shipping fee to $4.99. I've changed the guest checkout to true and set the page load time to 600ms.")


def test_a_reply_narrating_unset_changes_names_each_of_them_once():
    assert unapplied_mentions(NARRATED, ["theme_color", "home_sections"]) == [
        "welcome_popup", "chat_widget", "shipping_fee", "coupon_code", "guest_checkout", "page_load_ms"]


def test_option_names_in_a_reply_read_as_the_changes_they_name():
    # Another real reply of the same model, quoting option names; only the colour was set.
    reply = ("I've updated the page_style to 'luxury'. I've also removed the 'shipping_fee' and 'coupon_code' options, "
             "set the guest_checkout to true and the checkout_flow to multi_step, and added a 'page_load_ms' of 600.")
    assert unapplied_mentions(reply, ["theme_color"]) == [
        "page_style", "shipping_fee", "coupon_code", "guest_checkout", "checkout_flow", "page_load_ms"]


@pytest.mark.parametrize("name", ["free shipping threshold", "free-delivery threshold", "free_shipping_threshold"])
def test_setting_a_shipping_fee_does_not_cover_an_unset_threshold_claim(name):
    # Actual CPU reply set the already-current shipping fee and claimed this threshold was removed.
    reply = f"I've set the shipping fee to $4.99 on every order, removing the {name}."
    assert unapplied_mentions(reply, ["shipping_fee"]) == ["free_shipping_threshold"]
    assert unapplied_mentions(reply, ["shipping_fee", "free_shipping_threshold"]) == []
    assert unapplied_mentions(f"I changed the {name}.", []) == ["free_shipping_threshold"]
    assert unapplied_mentions(f"I changed the {name}.", ["free_shipping_threshold"]) == []


@pytest.mark.parametrize("reply,set_options", [
    ("I added a cookie banner at the bottom.", ["cookie_banner"]),  # not the hero banner
    ("A luxury style with a deep navy colour, and no popup.", ["page_style", "theme_color", "welcome_popup"]),
    ("Free delivery over $50 and a 10% coupon in the welcome popup.", ["free_shipping_threshold", "welcome_popup"]),
    ("Pages now load in 300 ms with add-to-cart buttons on the cards.", ["page_load_ms", "quick_add"]),
    ("What colour would you like?", []),  # a question changes nothing and claims nothing
])
def test_a_reply_that_matches_its_updates_or_asks_has_nothing_to_add(reply, set_options):
    assert unapplied_mentions(reply, set_options) == []


def test_the_designer_reply_says_which_mentioned_changes_were_not_applied(monkeypatch):
    site = build_site("fashion", site_id="claims")

    async def answer(*_args, **_kwargs):
        return DesignReply.model_validate({"updates": [{"option": "theme_color", "value": "#00AA33"},
                                                       {"option": "home_sections", "value": ["bestsellers", "deals"]}],
                                           "reply": NARRATED})

    monkeypatch.setattr(online, "get_site", lambda *_: site)
    monkeypatch.setattr(online, "assistive_model", lambda *_: "stub")
    monkeypatch.setattr(online, "assistive_client", lambda *_: object())
    monkeypatch.setattr(online, "answered_by", lambda *_: "stub")
    monkeypatch.setattr(online, "chat_design", answer)
    result = online.design_chat("p", site.id, DesignChatRequest(messages=[DesignMessage(role="owner", text="Make it premium")]),
                                SimulationConfig())
    assert result.changed == ["theme_color", "home_sections"]
    assert result.reply == NARRATED
    assert result.unapplied == ["welcome_popup", "chat_widget", "shipping_fee", "coupon_code", "guest_checkout", "page_load_ms"]
