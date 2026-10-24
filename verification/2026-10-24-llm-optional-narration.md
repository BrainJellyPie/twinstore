# Normalize absent optional model narration

All three behavior stages provide empty defaults for optional narrative fields,
but an explicit JSON null raised a string validation error. A model returning
valid products, coordinates and quantities could thus lose the entire shopper
because it represented an unused description, reasoning or optional grammar
rewrite as null. This is especially relevant to JSON providers that do not enforce
the transmitted grammar.

The existing model-only text validators now normalize null to empty text before
their length handling. Prompts ask for empty strings when there is no narration;
the response grammar remains string-valued. No general falsey-value coercion was
introduced: arrays, objects, numbers and booleans still fail text validation, and
null structural values such as nav, quantity and product_sku remain invalid.
Domain actions retain their original validation behavior.

Before repair, twelve complete HTTP pipeline cases failed and eighteen validation
controls passed. Afterward, 172 focused checks passed in 3.03 seconds and strict
Pyright reported zero errors. Cases cover every affected field across all three
stages, actual OpenAI/LiteLLM/Instructor JSON and JSON_SCHEMA parsing, cached null
narration, preserved 500-unit purchase revenue, completed checkout/exit, strict
coordinate handling and the existing prose limits. Seven existing LiteLLM
logging-cleanup warnings occurred. Responses and HTTP transport were scripted;
no live inference or paid requests were used.
