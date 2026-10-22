"""Partial briefs must preserve other choices and distinguish ambiguous categories."""
import asyncio
from copy import deepcopy
import pytest
from store_emulator.engine.layout_brief import _Brief, _Colors, read_brief, to_options

@pytest.mark.parametrize("part",["wall","floor","accent","counter"])
def test_changing_one_color_preserves_all_other_custom_colors(part):
    colors={"wall":"#111111","floor":"#222222","accent":"#333333","counter":"#444444"}
    current={"design_colors":colors,"density":"dense"};before=deepcopy(current)
    result=to_options(_Brief(design_colors=_Colors.model_validate({part:"#ABCDEF"})),current,[])
    assert result.options["design_colors"]=={**colors,part:"#abcdef"}
    assert current==before and "density" not in result.options

@pytest.mark.parametrize("asked",["Tea","Tea display","Tea and tea"])
@pytest.mark.parametrize("reverse",[False,True])
def test_ambiguous_category_names_never_exclude_an_arbitrary_category(asked,reverse):
    categories=[("tea_green","Tea"),("tea_black","Tea")]
    if reverse:categories.reverse()
    result=to_options(_Brief(excluded_categories=[asked]),{},categories)
    assert "excluded_categories" not in result.options and result.warnings

@pytest.mark.parametrize("asked",["tea_green","Green tea","Green tea display"])
def test_exact_category_or_unambiguous_label_is_preserved(asked):
    result=to_options(_Brief(excluded_categories=[asked]),{"excluded_categories":["coffee"]},[("tea_green","Green tea"),("tea_black","Black tea")])
    assert result.options["excluded_categories"]==["coffee","tea_green"]

def test_relative_brief_is_given_the_current_options_and_default_format():
    class Reader:
        prompts=[]
        async def generate_structured_async(self,response_model,system_prompt,user_prompt,**kwargs):
            self.prompts.append(user_prompt);return response_model.model_validate({"checkouts":8})
    fake=Reader();current={"checkouts":7,"design_colors":{"wall":"#123456"},"excluded_categories":["tea"]}
    asyncio.run(read_brief(fake,"Add one more till",{"name":"Shop","grid":[12,10],"checkouts":2},[("tea","Tea")],current))
    assert '"checkouts": 7' in fake.prompts[0] and '#123456' in fake.prompts[0] and '"tea"' in fake.prompts[0]
