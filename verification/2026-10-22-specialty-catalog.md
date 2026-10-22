# Specialty catalog expansion

Added 192 products in 16 categories, bringing the catalog to 1,016 products in 91 categories. Baking,
world sauces, herbs, prepared food, confectionery, care, travel, textiles, art, cycling, storage, games
and refill cleaning all have twelve distinct bilingual examples. Thirty-two additional photos cover
existing apparel/books/pets/hobbies and the new specialty groups; 64 photos are now bundled locally.
Automatic selection receives image availability but must prioritize the store and product requirements.

Validation on 2026-10-22:

- Targeted backend: 679 passed, including 91 categories in three currencies, exact selected SKU/price
  preservation, photo availability, all image endpoints, invalid indices and duplicated display names.
- Full backend: 17,419 passed, one skipped in 608.86 seconds. Strict types and application boot passed.
- Full frontend: 3,937 passed in 222 files; build passed; lint retained 19 warnings and zero errors.
- Browser: art/book shop creation through real routes with controlled model/persona responses selected
  books and the new fine-art catalog, with photos from both new atlases and no page errors. All 32 new
  images loaded in a gallery. Realistic rendering loaded both new atlases without errors.
- Visual inspection found a yoga strap and small neighboring-object fragments crossing atlas boundaries.
  Both new atlases were regenerated with more whitespace. The image/identity files then passed 120 tests,
  gallery screenshots were checked again, and realistic rendering passed again. The wheel was rebuilt.

The full suite preceded this final image-only correction; its affected checks were rerun afterward.
No live model provider or full paid simulation was invoked. Original generated sources remain preserved.
