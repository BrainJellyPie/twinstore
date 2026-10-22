# TwinStore interface copy

The interface supports English, Korean, simplified Chinese, Japanese, Spanish and French.
This is an editing guide, not evidence of native-speaker review. Language quality still needs
external review; automated checks verify rendering, placeholders and behavior, not fluency.

## Write for the action on screen

- Translate the user's task, not the English sentence structure. Put the action or the next step first.
- Keep button labels short and specific. A hint can explain the consequence or exception.
- Prefer familiar retail language to implementation language. “Distinct products” means product
  types, not units on a shelf; a blank limit means the whole available assortment, not infinite stock.
- Explain technical terms where they help reproduce work. The assortment seed is a number that
  recreates the same selection with the same product settings. It is not a product ID or a forecast.
- Preserve constraints, data-loss implications, uncertainty and error recovery. Shorter copy must
  not imply that manual fixture/product edits are included in a generation-options export.
- Write complete translated messages around placeholders. Do not assemble sentences from fragments
  or use Korean placeholder particles such as `을(를)`. A label/value construction often reads better.
- Match the visible action in the hint. If a button is renamed, review nearby instructions and
  accessibility names too. Use the same terms across the whole flow.
- Check counts at zero, one and several. A metric label followed by its value (for example,
  `Caisses : 1`) avoids attaching a fixed plural noun to every number. In sentences, use the
  language's correct singular/plural form. Do not drop numeric limits or integer requirements.
- Preserve user names, original product information, IDs and request values. Do not silently translate
  or “correct” user data while editing interface copy.

## Voice by language

| Language | Voice and examples |
| --- | --- |
| English | Direct verbs and short sentences. “Choose”, “Save”, “Try again”. Avoid describing internal state transitions as user instructions. |
| Korean | Polite `하세요` guidance and concise action labels. Prefer `여는 시간`, `닫는 시간`, `상품 종류 수` in setup controls. Explain `상품 조합 번호(시드)` on first use. Avoid noun chains such as `생성 진열대` and literal constructions such as `공통 설정을 따릅니다` when `비워 두면 위에서 정한 수를 사용합니다` is clearer. |
| Simplified Chinese | Use ordinary product UI language: `设置`, `营业时间`, `商品类别`, `换一组商品`. Use `店铺类型` instead of repeatedly calling a shop `业态`. Keep technical seed semantics in the explanation; do not imply the number is an SKU. |
| Japanese | Use polite `してください` for instructions and concise verb labels. Prefer `標準`, `商品種類数`, `品揃えを変える` to literal imported wording. Use `シード値` with a short explanation of reproducibility. |
| Spanish | Use consistent informal singular instructions (`elige`, `introduce`, `puedes`) and infinitive button labels (`Guardar`, `Importar ajustes`). Prefer `tipo de tienda`, `productos distintos` and `límite general` to literal uses of “format” or “shared”. |
| French | Use consistent `vous` instructions and infinitive button labels (`Enregistrer`, `Importer les réglages`). Prefer `type de magasin`, `produits différents`, `limite générale`. Explain `graine` as a number for reproducing a selection; avoid treating it as a familiar everyday word. |

## Review in context

Read labels, hints, errors and success states together in every supported language. Check narrow
screens, expanded sections and accessible names, not only the catalog file. Switch language with a
draft or a pending request to check that the words change without losing the user's work. Download
and reopen files to confirm that translated explanations do not change the underlying data format.
Record remaining English server/model output separately from missing frontend translations.
