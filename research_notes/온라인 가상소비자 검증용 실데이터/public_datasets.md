# Public real e-commerce behavior datasets as ground truth for TwinStore's simulated online shoppers

Scope: a catalog of publicly obtainable real e-commerce session, clickstream, event, search and ad logs that TwinStore's simulated online-shopper outputs can be compared against (session outcome shares, conversion rate, AOV, bounce, add-to-cart, cart abandonment, the funnel, pages and dwell time per session, search use, exit pages, page-to-page flows, click positions, device, demographic, traffic-source and mission breakdowns, and ad CTR and conversion). Research date: 2026-10-25. Link-liveness checks were run from this session on 2026-10-25 and are labelled "probe".

**Flag legend**, used in each entry header:
- `[TS]`: per-event timestamps, so dwell time and session duration can be derived.
- `[CHECKOUT]`: explicit checkout or payment steps.
- `[SEARCH-TEXT]`, `[SEARCH-HASH]`, `[SEARCH-VEC]`: search queries as raw text, as hashed tokens, or as vectors or embeddings.
- `[DEV]`: device, OS or platform field.
- `[SRC]`: traffic source or referrer.
- `[DEMO]`: user age or gender.
- `[PRICE]`: prices or revenue.
- `[POS]`: on-screen or list position.
- `[ADS]`: ad impressions, clicks or conversions.
- `[OBF]`: obfuscated or partly synthetic.
- `[AGG]`: session-level aggregates only, with no event sequence.
- `[AVAIL?]`: the download location is changed, gone or uncertain.

---

## Q1. Which real e-commerce session, clickstream, search and ad datasets exist, and what does each contain?

### Takeaway
At least 40 relevant public real-user datasets exist; they are listed below as D1–D40, with the agent and trajectory datasets in Q4. Only a handful cover the full web funnel with page-level, checkout, device and traffic-source data:
- Google Merchandise Store GA360 sample (BigQuery)
- GA4 obfuscated sample
- Kaggle GA Customer Revenue Prediction
- UCI Online Shoppers Purchasing Intention (session aggregates)
- KDD Cup 2000 Gazelle.com (now hard to obtain)

Most large modern sets (REES46, Retailrocket, OTTO, YOOCHOOSE, Coveo, Synerise, Taobao) are product-event logs (view / cart / purchase) with timestamps but no page types, device or referrer. The demographic fields come almost entirely from Chinese and Japanese platforms: Tmall, the Taobao display-ad set, JD and Ponpare. H&M also has age, but only for purchases.

### Cited Findings

#### A. Full-funnel web-analytics datasets (page level, with device, source and checkout)

**D1. UCI Online Shoppers Purchasing Intention.** Flags: `[AGG] [DEV-coded] [SRC-coded] [TS-agg]`
- Provider and year: Sakar and Kastro, donated to UCI on 2018-08-30. The paper is Sakar, Polat, Katircioglu and Kastro (2019), *Neural Computing & Applications*. Dataset DOI 10.24432/C5F88Q. URL: https://archive.ics.uci.edu/dataset/468/online+shoppers+purchasing+intention+dataset — [UCI](https://archive.ics.uci.edu/dataset/468/online+shoppers+purchasing+intention+dataset)
- Size: 12,330 sessions with 17 features plus a Revenue label. 10,422 sessions (84.5%) ended without a purchase and 1,908 (15.5%) with one. — [UCI](https://archive.ics.uci.edu/dataset/468/online+shoppers+purchasing+intention+dataset)
- Fields — [UCI](https://archive.ics.uci.edu/dataset/468/online+shoppers+purchasing+intention+dataset):
  - Page counts and total durations by page type: Administrative / _Duration, Informational / _Duration, ProductRelated / _Duration.
  - Google Analytics page metrics: BounceRates, ExitRates, PageValues.
  - Context: SpecialDay, Month, OperatingSystems, Browser, Region, TrafficType, VisitorType (new or returning), Weekend.
  - The integer codes for OS, Browser, Region and TrafficType are not described.
- License: CC BY 4.0. — [UCI](https://archive.ics.uci.edu/dataset/468/online+shoppers+purchasing+intention+dataset)
- TwinStore metrics it can validate:
  - Purchase share and conversion rate (15.5% of sessions).
  - Pages per session by page type, and time per page type (product versus info pages).
  - New versus returning visitors, and weekend or seasonal effects.
  - Traffic-type and OS/browser breakdowns, but only as anonymous codes.
  - No event order, no funnel steps and no search.
- KR: 1.2만 세션 단위 요약(페이지 유형별 조회수·체류시간, 이탈률, 구매여부) — 전환율·페이지/세션·체류시간 분포 비교용 표준 벤치마크.

**D2. Google Analytics 360 sample dataset (Universal Analytics), Google Merchandise Store.** Flags: `[TS] [CHECKOUT] [DEV] [SRC] [PRICE] [POS] [OBF-partial]`
- Location: BigQuery `bigquery-public-data.google_analytics_sample.ga_sessions_YYYYMMDD`, covering 1 Aug 2016 to 1 Aug 2017. It is "obfuscated Google Analytics 360 data" from a real e-commerce store. — [Google support](https://support.google.com/analytics/answer/7586738?hl=en)
- Obfuscation: fullVisitorId is obfuscated, and clientId, adWordsClickInfo and geoNetwork are removed. Empty fields read "Not available in demo dataset". The article is marked legacy (Universal Analytics). — [Google support](https://support.google.com/analytics/answer/7586738?hl=en)
- Schema — [UA BigQuery Export schema](https://support.google.com/analytics/answer/3437719?hl=en):
  - Session totals: `totals.bounces` (1 for a bounced session), `totals.timeOnSite` (seconds), `totals.pageviews`, `totals.transactions`.
  - Traffic and device: `trafficSource.source` and `trafficSource.medium` (organic, cpc, referral, utm_medium), `device.deviceCategory` (Mobile, Tablet, Desktop).
  - Hit timing and pages: `hits.time` (ms after visit start), `hits.type` (PAGE, TRANSACTION, ITEM, EVENT…), `hits.page.pagePath`, `hits.isEntrance`, `hits.isExit`.
  - Ecommerce steps: `hits.eCommerceAction.action_type`, coded 1 list click, 2 product detail view, 3 add to cart, 4 remove from cart, 5 checkout, 6 completed purchase, 7 refund, 8 checkout options. `hits.eCommerceAction.step` holds the checkout step.
  - List position: `hits.product.productListPosition`.
  - No age or gender fields.
- Access: free to query, viewer access only. The BigQuery sandbox or free tier is enough. — [Google support](https://support.google.com/analytics/answer/7586738?hl=en)
- TwinStore metrics it can validate. This is the best single public match to TwinStore's outputs:
  - Bounce rate and session duration.
  - Pages per session and per-page dwell (from `hits.time` deltas).
  - Exit pages (`isExit`) and page-to-page flows (`pagePath` sequences).
  - The full funnel: list → detail → add to cart → checkout (steps) → purchase.
  - Cart abandonment, conversion rate, AOV and revenue per session.
  - Device and traffic-source (direct / organic / referral / cpc / email via medium) breakdowns.
  - Product list position effects.
- KR: 구글 머천다이즈 스토어 실제 GA360 세션/히트 로그(2016-08~2017-08) — 이탈·체류·결제단계·기기·유입경로까지 TwinStore 지표 대부분 검증 가능.

**D3. GA4 obfuscated sample ecommerce (Google Merchandise Store).** Flags: `[TS] [CHECKOUT] [DEV] [SRC] [SEARCH-TEXT?] [OBF]`
- Location: BigQuery `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`, three months from 2020-11-01 to 2021-01-31. — [Google Developers](https://developers.google.com/analytics/bigquery/web-ecommerce-demo-dataset)
- Implementation: the site uses the standard web ecommerce implementation plus enhanced measurement. — [Google Developers](https://developers.google.com/analytics/bigquery/web-ecommerce-demo-dataset)
- Obfuscation: the data is "obfuscated data that emulates what a real world dataset would look like". Fields can contain the placeholders `<Other>`, `NULL` and `''`, "internal consistency of the dataset might be somewhat limited", and the data cannot be compared with the GA Demo Account. — [Google Developers](https://developers.google.com/analytics/bigquery/web-ecommerce-demo-dataset)
- Relevant GA4 ecommerce events (definitions only):
  - `begin_checkout` and `add_payment_info` (payment info submitted during checkout).
  - `view_search_results`, with an optional `search_term` parameter and collected automatically by enhanced measurement.
  - — [gtag event reference](https://developers.google.com/gtagjs/reference/event?authuser=1)
- TwinStore metrics it can validate: event-level funnel including the checkout and payment steps; device and source; possibly site-search terms. Because it is flagged OBFUSCATED, use it for marginal distributions rather than joint ones.
- KR: GA4 이벤트 단위 공개 샘플(2020-11~2021-01) — 결제·검색어 이벤트 포함하나 난독화되어 내부 일관성 제한, 논문에서는 '난독화'로 명시 필요.

**D4. Kaggle "Google Analytics Customer Revenue Prediction" (2018), GStore.** Flags: `[TS] [DEV] [SRC] [PRICE]`
- Content: the same store's GA sessions. train_v2 has 1,708,337 rows with JSON columns `device`, `geoNetwork`, `trafficSource` and `totals`. — [GitHub write-up](https://github.com/abdkumar/Google-Analytics-Customer-Revenue-Prediction); [r-bloggers](https://www.r-bloggers.com/2018/10/marketing-analytics-and-data-science/amp/)
- Period: training covers 2016-08-01 to 2018-04-30. — [SAS Global Forum paper](https://support.sas.com/resources/papers/proceedings19/4050-2019.pdf)
- Access: Kaggle competition data, subject to Kaggle competition rules.
- TwinStore metrics it can validate:
  - Session-level revenue per session (heavily zero-inflated).
  - Device, geo and traffic-source shares.
  - Pageviews, bounces and time on site from `totals`.
- KR: GA 세션 170만 건(geo 포함) — 세션당 매출·기기·유입경로 분포 비교용.

**D5. KDD Cup 2000, Gazelle.com (Blue Martini).** Flags: `[TS] [DEV-browser] [SRC] [DEMO-partial] [PRICE] [AVAIL?]`
- Provider: clickstream and purchase data from Gazelle.com, a legwear and legcare retailer. The site soft-launched on 30 Jan 2000 and hard-launched on 29 Feb 2000. Training covers two months and test one month. — [kdnuggets / organizers](https://www.kdnuggets.com/news/2000/n10/3i.html); [Kohavi et al., "KDD-Cup 2000 Organizers' Report: Peeling the Onion", SIGKDD Explorations 2(2), course copy, login-gated on probe](https://courses.cs.washington.edu/courses/csep546/07sp/proj1/kddOrganizerReport.pdf)
- Fields — [UW course notes](https://courses.cs.washington.edu/courses/csep546/03sp/proj1/proj1_data.html):
  - Session: date/time, cookie, browser, visit count, referrer.
  - Page view: URL, processing time, product, assortment.
  - Orders.
  - Customer attributes and questionnaire answers, attached only when a registered user logged in. Personal data was removed or perturbed.
- Organizer questions included "will the visitor view another page or leave?" and characterizing "killer pages" where users leave. — [Search summary of the organizers' report](https://courses.cs.washington.edu/courses/csep546/07sp/proj1/kddOrganizerReport.pdf)
- Access: non-commercial research use under a click-through agreement, with Blue Martini acknowledgement required. The original Purdue host `http://www.ecn.purdue.edu/KDDCUP/` returned **HTTP 410 Gone** (probe). A derived sequence-format version is on SPMF. — [SPMF datasets](https://www.philippe-fournier-viger.com/spmf/datasets.php)
- TwinStore metrics it can validate: exit and continuation probability by page, exit pages, referrer breakdown, browser, and demographics for logged-in users. The data is from 2000, so its external validity for modern UX is limited.
- KR: 2000년 Gazelle.com 클릭스트림(리퍼러·브라우저·일부 인구통계) — 이탈 페이지 분석의 고전, 원 배포처 소멸.

**D6. UCI "Clickstream data for online shopping" (Polish clothing e-shop for pregnant women).** Flags: `[POS] [PRICE] [SEQ]`
- Size and period: 165,474 rows with 14 features, covering April to August 2008. — [UCI](https://archive.ics.uci.edu/dataset/553/clickstream+data+for+online+shopping)
- Fields — [UCI](https://archive.ics.uci.edu/dataset/553/clickstream+data+for+online+shopping):
  - year, month, day.
  - `order`, the click sequence within the session, and session ID.
  - country (from IP).
  - page 1 (main category), page 2 (clothing model, 217 products), colour.
  - **location: photo location on the page, with the screen divided into six parts.**
  - model photography, price, price 2, page.
- License: CC BY 4.0. Citation: Łapczyński and Białowąs (2013). — [UCI](https://archive.ics.uci.edu/dataset/553/clickstream+data+for+online+shopping)
- TwinStore metrics it can validate: **click position on screen**. It is the only public e-commerce log found in this research with an on-page click location. It also supports clicks per session, category-to-product flows and country breakdowns.
- KR: 화면 6분할 클릭 위치가 있는 유일한 공개 쇼핑 클릭스트림 — TwinStore '클릭 위치' 지표 검증용.

#### B. Large product-event logs (view / cart / purchase), mostly from session-based recommendation research

**D7. REES46 "eCommerce behavior data from multi category store".** Flags: `[TS] [PRICE]`
- Content: 285M events over 7 months (Oct 2019 – Apr 2020) from a large multi-category online store, collected by Open CDP / REES46. The Kaggle copy is about 14.7 GB. — [Kaggle API metadata](https://www.kaggle.com/datasets/mkechinov/ecommerce-behavior-data-from-multi-category-store)
- Fields: event_time (UTC), event_type, product_id, category_id, category_code, brand, price, user_id, user_session (a temporary session ID). — [Kaggle](https://www.kaggle.com/datasets/mkechinov/ecommerce-behavior-data-from-multi-category-store)
- Extra monthly archives (Oct 2019 – Apr 2020) are at data.rees46.com. `2019-Oct.csv.gz` returned HTTP 200 (probe). — [Kaggle](https://www.kaggle.com/datasets/mkechinov/ecommerce-behavior-data-from-multi-category-store)
- License: Kaggle lists it as "Data files © Original Authors". Free use is allowed with a link to the page and to REES46. — [Kaggle](https://www.kaggle.com/datasets/mkechinov/ecommerce-events-history-in-cosmetics-shop)
- TwinStore metrics it can validate:
  - The view → cart → purchase funnel and add-to-cart rate.
  - Cart abandonment (sessions with a cart event but no purchase).
  - AOV and revenue per session (from price).
  - Events per session and inter-event dwell.
  - Product-level views, adds and purchases.
- KR: 2.85억 이벤트 대형 멀티카테고리몰 로그 — 조회→장바구니→구매 퍼널·장바구니 이탈·AOV 대규모 비교용.

**D8. REES46 cosmetics shop.** Flags: `[TS] [PRICE]`
- Content: 20M events from a medium cosmetics store, Oct 2019 – Feb 2020. — [Kaggle](https://www.kaggle.com/datasets/mkechinov/ecommerce-events-history-in-cosmetics-shop)
- Event types: `view`, `cart`, `remove_from_cart`, `purchase`. Multiple purchase events in one session form a single order. — [Kaggle](https://www.kaggle.com/datasets/mkechinov/ecommerce-events-history-in-cosmetics-shop)
- KR: 화장품몰 2천만 이벤트(장바구니 삭제 포함) — 카트 추가/삭제/구매 전이 비교.

**D9. REES46 electronics store events.** Flags: `[TS] [PRICE]`
- Content: about 900K events from a large electronics online store, Oct 2019 – Feb 2020. — [Kaggle](https://www.kaggle.com/datasets/mkechinov/ecommerce-events-history-in-electronics-store)
- KR: 전자제품몰 90만 이벤트 — 소규모 검증·파이프라인 테스트용.

**D10. Retailrocket recommender system dataset.** Flags: `[TS] [PRICE-in-properties]`
- Content: 2,756,101 events from 1,407,580 unique visitors over 4.5 months. These are 2,664,312 views, 69,332 add-to-carts and 22,457 transactions. All values are hashed. — [Kaggle](https://www.kaggle.com/datasets/retailrocket/ecommerce-dataset)
- Item properties: 20,275,902 timestamped rows for 417,053 items, plus a category tree. — [Kaggle](https://www.kaggle.com/datasets/retailrocket/ecommerce-dataset)
- License: CC BY-NC-SA 4.0. — [Kaggle](https://www.kaggle.com/datasets/retailrocket/ecommerce-dataset)
- TwinStore metrics it can validate: view → cart → transaction ratios and visitor-level conversion. There is no session ID.
- KR: 방문자 140만·이벤트 276만(조회/장바구니/거래) — 세션 ID 없음, 30분 규칙으로 세션화 필요.

**D11. YOOCHOOSE (RecSys Challenge 2015).** Flags: `[TS] [PRICE]`
- Content: about 9.2–9.3M sessions (roughly half a million are buy sessions) over about 6 months in 2014, from a large European e-commerce business. — [arXiv 2010.12540](https://arxiv.org/pdf/2010.12540); [RecSys 2015 challenge page](https://recsys.acm.org/recsys15/challenge/)
- Fields: click events, plus buy events with item, timestamp, quantity and price. — [search summary of challenge materials](https://www.cs.toronto.edu/~mvolkovs/recsys2015.pdf)
- After common session-recommendation preprocessing, 1,956,539 training sessions and 30,660 products remain. — [Amazon-M2 paper, Table 1](https://arxiv.org/pdf/2307.09688)
- Availability: a Kaggle mirror exists (1.9 GB, licence "Unknown"). — [Kaggle mirror](https://www.kaggle.com/datasets/chadgostopp/recsys-challenge-2015)
- TwinStore metrics it can validate: buy-session share, clicks per session, time between clicks, and AOV from price × quantity.
- KR: 2014년 유럽 쇼핑몰 920만 세션(클릭/구매+가격·수량) — 구매세션 비율·클릭수 분포.

**D12. Diginetica (CIKM Cup 2016, Track 2: personalized e-commerce search).** Flags: `[TS] [SEARCH-HASH] [PRICE]`
- Content — [Wu, Yan, Si, arXiv 1708.04479](https://arxiv.org/pdf/1708.04479):
  - 573,935 sessions.
  - 53,427 full-text queries and 869,700 query-less (category browse) queries.
  - 130,987 products, 1,127,764 clicks, 1,235,380 views and 18,025 purchases.
  - 232,817 identified users and 333,097 anonymous users.
  - Train query log: 1 Jan – 1 Jun 2016.
- Search records include the query, session, user ID and the products shown. Product metadata includes category and price. — [arXiv 1708.04479](https://arxiv.org/pdf/1708.04479)
- TwinStore metrics it can validate: share of sessions that search versus browse categories, clicks per search, rank of the clicked result, and the very low purchase rate per session.
- KR: 검색 기반 쇼핑 로그(텍스트 검색 5.3만 vs 카테고리 탐색 87만) — 검색 이용률·검색결과 클릭 비교.

**D13. Coveo SIGIR eCom 2021 Data Challenge.** Flags: `[TS] [SEARCH-VEC] [PRICE-bucket] [IMPRESSIONS]`
- Content: about 5M anonymized sessions in browsing_train (36M events in the full set), plus more than 800k search interactions and a catalog with category, price bucket and text and image vectors. — [GitHub](https://github.com/coveooss/SIGIR-ecom-data-challenge)
- Browsing fields: session_id_hash (new session after a 30-minute gap), event_type (pageview or event), product_action (detail / add / purchase / remove), product_sku_hash, server_timestamp_epoch_ms (shifted by an unspecified number of weeks), hashed_url. — [GitHub](https://github.com/coveooss/SIGIR-ecom-data-challenge)
- Search fields: query_vector (a dense vector; **raw query text is not released**), product_skus_hash (the impressions) and clicked_skus_hash. — [GitHub](https://github.com/coveooss/SIGIR-ecom-data-challenge)
- Access: research and educational use only, after a form and T&C. Reverse-engineering is forbidden. Paper: Tagliabue et al. 2021, arXiv 2104.09423. — [GitHub](https://github.com/coveooss/SIGIR-ecom-data-challenge)
- TwinStore metrics it can validate:
  - Page-to-page flows (hashed URLs) and pageviews per session.
  - Dwell from timestamps.
  - Detail → add → purchase funnel and cart removal.
  - Search usage share and search-result CTR.
  - A zero-result proxy (searches with an empty impression list).
- KR: 500만 세션(페이지뷰·상품액션·해시 URL)+검색 80만(쿼리 벡터, 노출/클릭) — 검색 이용률·페이지 흐름 검증에 최적.

**D14. OTTO RecSys dataset (Kaggle 2022).** Flags: `[TS]`
- Train: 12,899,779 sessions with 216,716,096 events (194.7M clicks, 16.9M carts, 5.1M orders) over 4 weeks.
- Test: 1,671,803 sessions over the following week.
- Fields: aid, ts, type (clicks / carts / orders). 1.86M items.
- License: CC BY 4.0. Citation: Normann, Baumeister, Wilm (2023), DOI 10.34740/KAGGLE/DSV/4991874.
- — [GitHub otto-de/recsys-dataset](https://github.com/otto-de/recsys-dataset)
- TwinStore metrics it can validate: click → cart → order transition matrices, events per session, inter-event times, and order share. It has no prices.
- KR: 독일 OTTO 1,290만 세션·2.2억 이벤트(클릭/카트/주문) — 행동 전이행렬·세션 길이 분포 대규모 기준.

**D15. Dressipi "1M Fashion Sessions" (RecSys Challenge 2022).** Flags: `[TS?]`
- Content: about 1.1M anonymous sessions over 18 months (Jan 2020 – Jun 2021). **Every session ends in a purchase.** About 24k items with expert-labelled features. The last month (100k sessions) is the test set. — [ETH Research Collection](https://www.research-collection.ethz.ch/items/558fe8bb-63e0-47c9-a97f-ed5d9a493058); [RecSys 2022 challenge](https://recsys.acm.org/recsys22/challenge/)
- Download: from Dressipi's site. The site carries a "Mapp acquires Dressipi" banner, so availability should be watched. — [dressipi.com/datasets](https://www.dressipi.com/datasets)
- TwinStore metrics it can validate: path length before purchase in **purchasing** sessions only. It cannot give conversion or bounce rates.
- KR: 구매로 끝난 패션 세션 110만 — 구매 세션의 조회 경로 길이만 비교 가능(전환율 불가).

**D16. Amazon-M2 (KDD Cup 2023 multilingual session dataset).** Flags: `[TEXT-product]`
- Size: 3,606,249 train and 361,659 test sessions, 1,410,675 products, 15.3M interactions, average session length 4.2.
- Locales: UK, DE and JP make up most of it; ES, FR and IT are about a tenth as large.
- Sessions are lists of product IDs, with product attributes in six languages.
- License: Apache 2.0, from AIcrowd. Published at NeurIPS 2023 (Datasets & Benchmarks).
- — [arXiv 2307.09688](https://arxiv.org/pdf/2307.09688)
- TwinStore metrics it can validate: number of products viewed per session by country (locale). It has no timestamps, event types or prices in the sessions.
- KR: 아마존 6개국 360만 세션(상품 ID 시퀀스) — 국가별 세션당 조회 상품 수 비교만 가능.

**D17. Synerise "Universal Behavioral Modeling" dataset (RecSys Challenge 2025).** Flags: `[TS] [SEARCH-VEC] [AVAIL?]`
- Event types — [recsys.synerise.com](https://recsys.synerise.com/summary):
  - product_buy, add_to_cart, remove_from_cart: client_id, timestamp, sku.
  - page_visit: client_id, timestamp at minute resolution, numeric url ID.
  - search_query: client_id, timestamp, query as a **product-quantized text embedding (no raw text)**.
- Profiles are evaluated for 1,000,000 relevant client IDs. — [recsys.synerise.com](https://recsys.synerise.com/summary)
- License: CC BY-NC 4.0. Dataset paper DOI 10.1145/3758126.3758188. — [search summary](https://recsys.acm.org/recsys25/challenge/); [UL record](https://pure.ul.ie/en/publications/the-synerise-dataset-an-e-commerce-dataset-for-sequential-recomme/)
- The documented download URL `https://data.recsys.synerise.com/dataset/ubc_data/ubc_data.tar.gz` returned **404 BlobNotFound** (probe, 2026-10-25). The current download location needs to be confirmed with Synerise or the GitHub repo. — [GitHub Synerise/recsys2025](https://github.com/Synerise/recsys2025)
- TwinStore metrics it can validate: page visits and search use alongside cart and buy in a single log, add/remove/buy transitions, and the share of users who search. This is the newest (2025) large real log with search events.
- KR: 2025 RecSys 챌린지 실로그(구매/담기/빼기/페이지방문/검색) — 검색 포함 최신 대규모 로그, 다운로드 링크 404 확인 필요.

**D18. Taobao UserBehavior (Alibaba Tianchi dataId=649).** Flags: `[TS]`
- Content: about 1M randomly sampled users active from 25 Nov to 3 Dec 2017, about 100M records of (user, item, category, behavior type, timestamp). Behavior types are click, purchase, add-to-cart and favor. — [TDM paper, arXiv 1801.02294](https://arxiv.org/pdf/1801.02294); [beta-recsys docs](https://beta-recsys.readthedocs.io/en/latest/_modules/beta_rec/datasets/taobao.html)
- The exact end date is reported inconsistently (3 or 4 Dec). — [Alibaba DLF tutorial](https://help.aliyun.com/zh/dlf/dlf-1-0/use-cases/dlf-data-exploration-taobao-user-behavior-analysis)
- Access: manual download from Tianchi after login. — [beta-recsys docs](https://beta-recsys.readthedocs.io/en/latest/_modules/beta_rec/datasets/taobao.html)
- TwinStore metrics it can validate: click → cart / fav → buy ratios on a mobile app, hourly and daily activity, and the repeat behaviour of 1M users. There is no session ID, so sessionize the data.
- KR: 타오바오 앱 100만 사용자·1억 행동(클릭/담기/찜/구매) — 중국 모바일 쇼핑 퍼널 비율 비교.

**D19. Tmall Repeat Buyers (IJCAI-15, Tianchi dataId=42).** Flags: `[TS-day] [DEMO]`
- Content: anonymized logs for the six months before Double 11 and the day itself. User profile has age range and gender. Items have category, brand and merchant. Context has timestamp and action type. — [HIEN paper, arXiv 2206.00510](https://arxiv.org/pdf/2206.00510); [IJCAI-15 call](https://groups.google.com/g/resys/c/oK8DzKHho1c)
- Studies train on roughly 200k users. — [ICDMW 2019 record](https://publications.goettingen-research-online.de/handle/2/63192?cs=mla)
- TwinStore metrics it can validate: **click / cart / purchase / favourite rates by age group and gender**, and promotion-day (deal_hunt) behaviour.
- KR: 티몰 광군제 로그+연령대·성별 — 인구통계별 행동 비교 가능한 드문 공개 데이터.

**D20. JD.com MSOM 2020 Data Driven Research Challenge.** Flags: `[TS] [DEMO-partial] [PRICE] [PROMO]`
- Content: over 2.5M customers (457,298 of them purchased) and 31,868 SKUs in one anonymized category, for March 2018. — [MSOM 2024 26(1):2–10, DOI 10.1287/msom.2020.0900](https://pubsonline.informs.org/doi/fpi/10.1287/msom.2020.0900); [SUFE summary](https://academicnewsletter.sufe.edu.cn/info/381827)
- Structure: 7 tables covering users, orders, delivery, inventory and more. User fields include a membership flag, gender and purchase power, some of them estimated. — [Atlantis Press paper](https://www.atlantis-press.com/article/125982184.pdf)
- Access: originally offered to MSOM members. — [INFORMS SUFE summary](https://academicnewsletter.sufe.edu.cn/info/381827)
- TwinStore metrics it can validate: click → order conversion, promotion and discount effects, and gender or membership segments.
- KR: JD 2018년 3월 250만 고객 클릭·주문·프로모션+일부 인구통계 — 할인(deal_hunt) 효과·세그먼트 비교.

#### C. Search-centric datasets (query logs, search relevance)

**D21. JDsearch (SIGIR 2023).** Flags: `[TS] [SEARCH-HASH]`
- Content: about 170k active users sampled on one date, with one year of their history. About 12M products, 9.4M real searches and 26M interactions (click, add-to-cart, follow, purchase). — [arXiv 2305.14810](https://arxiv.org/abs/2305.14810v1)
- Access: download through JD Cloud Disk with a password given in the repo. — [GitHub rucliujn/jdsearch](https://github.com/rucliujn/jdsearch)
- The text is anonymized. — [KuaiSearch paper](https://arxiv.org/html/2602.11518v1)
- TwinStore metrics it can validate: searches per user and session, search → click → cart → purchase from search, and query length in tokens.
- KR: JD 실검색 940만 건+클릭/담기/구매 — 검색 기반 퍼널 검증(텍스트는 익명화).

**D22. KuaiSearch (2026, Kuaishou e-commerce search).** Flags: `[SEARCH-TEXT]`
- Built from real user search interactions on Kuaishou. It "preserves authentic queries and natural-language product texts", keeps cold-start users and long-tail products, and covers recall, ranking and relevance. Size and license are not given on the abstract page. Code: GitHub benchen4395/KuaiSearch. — [arXiv 2602.11518](https://arxiv.org/abs/2602.11518)
- TwinStore metrics it can validate: **real query text distributions** (length, wording) to compare with the simulated `search_text`. The query language is Chinese.
- KR: 2026 공개 콰이쇼우 커머스 검색 데이터(실제 쿼리 원문) — 검색어 텍스트 분포 비교 후보.

**D23. Amazon Shopping Queries Dataset (ESCI, KDD Cup 2022).** Flags: `[SEARCH-TEXT]` (relevance labels, not behavior)
- Content: about 130k unique queries and 2.6M human-labelled query–product judgments (Exact / Substitute / Complement / Irrelevant) in English, Japanese and Spanish, with up to 40 results per query. — [arXiv 2206.06588](https://arxiv.org/abs/2206.06588v1); [SQID, arXiv 2405.15190](https://arxiv.org/pdf/2405.15190)
- The competition drew more than 9,200 submissions. — [Amazon Science](https://www.amazon.science/blog/amazon-product-query-competition-draws-more-than-9-200-submissions)
- TwinStore metrics it can validate: realism of query text only (length, specificity). It has no clicks or sessions.
- KR: 아마존 실검색어 13만(영/일/스) — 검색어 문장 분포 비교용(행동 로그 아님).

**D24. Diginetica (D12) and Coveo (D13)** also belong in this category. Diginetica has hashed query tokens and Coveo has query vectors.

#### D. Travel and marketplace session logs with UI actions and position

**D25. trivago RecSys Challenge 2019 (session-based hotel search).** Flags: `[TS] [DEV] [POS] [PRICE] [FILTER/SORT]`
- Fields: session ID, timestamp, step, action type, reference, platform (country), city, device, current filters, impressions. — [arXiv 2012.06052](https://arxiv.org/pdf/2012.06052)
- Action types cover search, filter/sort, deals, clickout, rating, info and image interactions. — [Polito thesis](https://webthesis.biblio.polito.it/12407/1/tesi.pdf)
- Dataset paper: Adamczak et al., DOI 10.1145/3412379. — [KIT record](https://publikationen.bibliothek.kit.edu/1000133071)
- A filtered version reports 1,202,064 sessions, 981,655 users and 19,715,327 actions. — [arXiv 2210.07814](https://arxiv.org/pdf/2210.07814)
- Access: account plus acceptance of terms. — [challenge announcement](https://lists.uni-bielefeld.de/mailman2/unibi/public/iva-list/2019/000615.html)
- The challenge host `recsys.trivago.cloud` **no longer resolves (DNS failure, probe)**. A Zenodo record from Sept 2025 surfaced in search but was not verified. — [Zenodo search hit](https://zenodo.org/records/17202694)
- TwinStore metrics it can validate:
  - **Action-transition matrices across UI actions** (filter, sort, image, info, deal, clickout).
  - Desktop / mobile / tablet breakdown.
  - Position of the clicked item in the impression list, and price sensitivity.
- KR: 트리바고 호텔검색 세션(필터·정렬·이미지·클릭아웃, 기기) — UI 액션 전이행렬·기기별 비교에 최적, 원 호스트 소멸.

**D26. Expedia "Personalize Expedia Hotel Searches" (ICDM 2013 / Kaggle).** Flags: `[POS] [PRICE] [RANDOMIZED]`
- Content: about 10M hotel impressions. `position` is the display rank. `click_bool`, `booking_bool` and `random_bool` are flags, where `random_bool` = 1 means a randomized ordering. About 30% of searches are randomized, which allows pure position-bias estimates. — [arXiv 2605.17238](https://arxiv.org/pdf/2605.17238); [arXiv 1311.7679](https://arxiv.org/pdf/1311.7679)
- TwinStore metrics it can validate: **position effects**, meaning CTR and booking by list rank under random ordering. This is a clean benchmark for whether LLM shoppers pick numbered options with a human-like primacy bias.
- KR: 무작위 정렬 30% 포함 호텔 노출 1천만 — 목록 순위별 클릭·예약(위치 편향) 비교용.

**D27. Avito Context Ad Clicks (Kaggle 2015).** Flags: `[TS] [SEARCH] [POS] [ADS] [DEV?]`
- Content: 8 tables with about 20.7M rows in the RelBench version, starting 2015-04-25. The main search file has about 400M records. Contents are users, ads shown, searches, visits and phone requests to sellers. — [RelBench rel-avito](https://relbench.stanford.edu/datasets/rel-avito); [Adam Drake](https://adamdrake.com/a-quick-overview-on-the-kaggle-competition-for-avito.html)
- TwinStore metrics it can validate: contextual ad CTR by position, the search → view → contact funnel, and marketplace ad behaviour.
- KR: 러시아 Avito 검색·광고노출·연락요청 로그 — 광고 CTR·위치효과 비교.

#### E. Ad and attribution logs (impressions, CTR, conversion)

**D28. Criteo Attribution Modeling for Bidding (2017).** Flags: `[TS-relative] [ADS] [PRICE-transformed]`
- Content: a sample of 30 days of live traffic, one row per banner impression.
- Fields: timestamp (relative), uid, campaign, conversion (within 30 days), conversion_timestamp, conversion_id, attribution, click, click_pos, click_nb, cost and cpo (both transformed), time_since_last_click, cat1–cat9.
- File: 623 MB compressed.
- — [Criteo AI Lab](https://ailab.criteo.com/criteo-attribution-modeling-bidding-dataset/)
- About 16M impressions. — [arXiv 2308.13510](https://arxiv.org/pdf/2308.13510)
- Paper: arXiv 1707.06409. — [arXiv](https://arxiv.org/pdf/1707.06409)
- The legacy zip URL `go.criteo.net/criteo-research-attribution-dataset.zip` returned 404 (probe). Use the AI Lab page link.
- TwinStore metrics it can validate: ad impression → click → conversion rates, multi-touch paths and conversion delay.
- KR: 크리테오 30일 광고 노출·클릭·전환·기여 로그 — 광고 CTR·전환율 비교.

**D29. Criteo Sponsored Search Conversion Log.** Flags: `[TS] [DEV] [PRICE] [ADS]`
- Content: 90 days of Criteo Predictive Search traffic, about 6.4 GB.
- Fields: Sale, SalesAmountInEuro, time_delay_for_conversion, click_timestamp, nb_clicks_1week, product_price, product_age_group, device_type, audience_id, product_gender, product brand / category / country / id / title, partner_id, user_id.
- Note that `product_age_group` and `product_gender` describe the product's target, not the user.
- — [Criteo AI Lab](https://ailab.criteo.com/criteo-sponsored-search-conversion-log-dataset/)
- TwinStore metrics it can validate: post-click conversion by device, sale amount (AOV for ad-driven sessions) and conversion delay.
- KR: 쇼핑광고 클릭→30일 내 구매·매출·기기 — 광고 유입 세션 전환율·AOV 비교.

**D30. Criteo Display Advertising Challenge (Kaggle 2014) and Criteo 1TB.** Flags: `[ADS]`
- Kaggle 2014: about 45M samples over 7 days, with 13 integer and 26 hashed categorical features. — [Papers with Code / search summary](https://paperswithcode.com/dataset/criteo-display-advertising-challenge); [DLRM paper](https://arxiv.org/pdf/1906.00091)
- Terabyte logs: 24 days. — [DLRM paper](https://arxiv.org/pdf/1906.00091)
- TwinStore metrics it can validate: baseline display-ad CTR only. The features are anonymous.
- KR: 대규모 디스플레이 광고 CTR 기준치.

**D31. Avazu CTR (Kaggle 2014).** Flags: `[ADS] [DEV]`
- Content: 10 days of mobile ad logs, over 40M impressions. Fields include hour (YYMMDDHH), banner position, site category and domain, device type and device model. — [TIB Avazu](https://service.tib.eu/ldmservice/dataset/avazu-dataset); [arXiv 2101.02342](https://arxiv.org/pdf/2101.02342)
- TwinStore metrics it can validate: mobile ad CTR by device type and banner position.
- KR: 모바일 광고 CTR(기기·배너위치).

**D32. Taobao Display Ad Click (Ali_Display_Ad_Click, Tianchi dataId=56).** Flags: `[TS] [ADS] [DEMO]`
- raw_sample: 1.14M users and 26M ad display / click records over 8 days (2017-05-06 to 05-13), with fields pid (scenario) and noclk.
- ad_feature: category, campaign, brand, advertiser.
- user_profile: 1.06M users with gender, age_level, consumption grade (pvalue_level), shopping depth, occupation (college student) and city level.
- behavior_log: 22 days with about 700M records.
- — [Kaggle mirror description](https://www.kaggle.com/datasets/pavansanagapati/ad-displayclick-data-on-taobaocom); [TIB Alimama](https://service.tib.eu/ldmservice/dataset/alimama)
- TwinStore metrics it can validate: **ad CTR by age group and gender**, and shopping depth segments.
- KR: 타오바오 광고 노출·클릭+성별·연령·구매력 — 인구통계별 광고 CTR 비교.

**D33. Ali-CCP (Alibaba Click and Conversion Prediction, the ESMM dataset).** Flags: `[ADS/REC] [CTR→CVR]`
- Content: from Taobao recommender traffic logs. About 84M exposures, 3.4M clicks, about 18k conversions, about 0.4M users and 4.3M items. Counts vary by preprocessing (another paper reports 85.3M / 3.3M / 18.4K). — [arXiv 2502.08277](https://arxiv.org/pdf/2502.08277); [arXiv 1910.09337](https://arxiv.org/pdf/1910.09337)
- Tianchi page 408 is associated with a later Ali-CCP release. — [TIB](https://service.tib.eu/ldmservice/dataset/ali-ccp5)
- TwinStore metrics it can validate: impression → click → purchase rates for recommended products (feed-level funnel).
- KR: 노출→클릭→구매 3단계 추천 퍼널(8,400만 노출).

#### F. Transaction and order datasets (purchase side only: AOV, basket, demographics)

**D34. Recruit Ponpare "Coupon Purchase Prediction" (Kaggle 2015).** Flags: `[TS] [SRC] [DEMO] [PRICE]`
- Content: Ponpare is a Japanese group-discount coupon site. The data is about one year of purchase and browsing history, from a competition run 16 Jul – 30 Sep 2015. — [Recruit press release](https://oldrelease.recruit-holdings.com/news_data/release/pdf/20150716_02.pdf)
- Schema — [TsinghuaDatabaseGroup schema](https://github.com/TsinghuaDatabaseGroup/datasets):
  - coupon_visit_train: PURCHASE_FLG, I_DATE, PAGE_SERIAL, REFERRER_hash, VIEW_COUPON_ID_hash, USER_ID_hash, SESSION_ID_hash, PURCHASEID_hash.
  - user_list: REG_DATE, SEX_ID, AGE, WITHDRAW_DATE, PREF_NAME.
  - coupon_list: genre, price rate, catalog and discount price, display period, and more.
- TwinStore metrics it can validate:
  - **Session-level browse → purchase with referrer, by age and gender.**
  - Pages per session (PAGE_SERIAL) and coupon-view conversion.
  - deal_hunt-style shopping, which fits a discount-site mission.
- KR: 일본 쿠폰몰 세션 열람로그(리퍼러·페이지순번)+성별·나이 — 인구통계·유입경로별 전환 비교 가능.

**D35. H&M Personalized Fashion Recommendations (Kaggle 2022).** Flags: `[DEMO-age] [PRICE] [CHANNEL]`
- Content: about 31–32M transactions over 2 years from about 1.37M customers and over 100k articles, covering both online and physical-store transactions. — [shaped.ai](https://www.shaped.ai/blog/h-m-dataset-powering-personalized-fashion-recommendations-at-scale); [RelBench rel-hm](https://relbench.stanford.edu/databases/hm)
- Customer features: age, postal code, membership status, fashion-news frequency. — [Polimi thesis](https://www.politesi.polimi.it/bitstream/10589/204133/1/Master_Thesis_With_Summary_Arcangelo-Pisa.pdf)
- License: non-commercial and academic research. — [RelBench rel-hm](https://relbench.stanford.edu/databases/hm)
- TwinStore metrics it can validate: purchase price and basket size by age group, and online versus store channel. There is no browsing data.
- KR: H&M 3,100만 거래+고객 연령 — 연령대별 객단가·구매 품목 비교(탐색 로그 없음).

**D36. Instacart Online Grocery Shopping Dataset 2017.** Flags: `[TS-coarse]`
- Content: over 3M orders from more than 200,000 users, with 4–100 orders per user. Each order has its product sequence (add-to-cart order), the day of week and hour it was placed, and a relative time between orders. — [Instacart tech blog](https://tech.instacart.com/3-million-instacart-orders-open-sourced-d40d29ead6f2)
- Terms: non-commercial use under Instacart's T&C. — [Instacart tech blog](https://tech.instacart.com/3-million-instacart-orders-open-sourced-d40d29ead6f2)
- The official download page `instacart.com/datasets/grocery-shopping-2017` returned **404** (probe), so the data is now obtained from the Kaggle "Instacart Market Basket Analysis" competition or mirrors. — [Cornell uchoice-Instacart](https://www.cs.cornell.edu/~arb/data/uchoice-Instacart/index.html)
- TwinStore metrics it can validate: the **replenish** mission (reorder share, days between orders), basket size, and add-to-cart order. There are no prices.
- KR: 인스타카트 300만 주문(재구매·주문간격·담은 순서) — '재구매(replenish)' 미션 검증용, 원 링크 404.

**D37. Olist Brazilian E-Commerce.** Flags: `[PRICE] [PAYMENT] [GEO]`
- Content: 100k orders from 2016–2018 across Brazilian marketplaces. It covers order status, price, payment, freight, customer location, product attributes and reviews. — [Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
- License: CC BY-NC-SA 4.0. — [Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
- A companion "Marketing Funnel" set has 8k seller leads (B2B, not shoppers). — [Kaggle](https://www.kaggle.com/datasets/olistbr/marketing-funnel-olist)
- TwinStore metrics it can validate: AOV distribution, payment-method mix and order-status outcomes. It has no browsing data.
- KR: 브라질 10만 주문(결제수단·가격·리뷰) — AOV·결제수단 분포 비교.

**D38. UCI Online Retail (I) and Online Retail II.** Flags: `[PRICE] [GEO]`
- Online Retail II: 1,067,371 rows from 01/12/2009 to 09/12/2011, from a UK non-store online retailer. Fields: Invoice ("c" prefix = cancellation), StockCode, Description, Quantity, InvoiceDate, Price, CustomerID, Country. License CC BY 4.0. Citation: Chen (2012). — [UCI](https://archive.ics.uci.edu/dataset/502/online+retail+ii)
- Online Retail (I): covers 01/12/2010 – 09/12/2011. Many customers are wholesalers. — [Kaggle mirror citing UCI](https://www.kaggle.com/datasets/carrie1/ecommerce-data)
- TwinStore metrics it can validate: AOV and basket-size distributions, and the cancellation rate. Wholesale buyers skew AOV, so interpret it with care.
- KR: 영국 온라인 기념품몰 거래 107만 행 — AOV·장바구니 크기(도매 비중 주의).

**D39. Rakuten Data Release (NII IDR).** Not a behavior log.
- Content: Ichiba product data (about 283M items), about 70M item reviews and about 22.5M shop reviews, plus Travel, GORA and Recipe data. — [NII IDR Rakuten](https://www.nii.ac.jp/dsc/idr/en/rakuten)
- Access: research use only, for university and public research institution researchers. — [NII IDR](https://www.nii.ac.jp/dsc/idr/en/rakuten); [Rakuten Data Release](https://rit.rakuten.com/data_release/)
- No purchase or click logs were found in the listing.
- KR: 라쿠텐 상품·리뷰 데이터(행동로그 없음) — 검증용 부적합.

**D40. Online-shopper agent and trajectory datasets.** These are listed in Q4: OPeRA, ShopCART (not public), WebShop, Mind2Web, Online-Mind2Web and WebLINX.

### Inferences
- **Capability matrix.** This is my mapping of each dataset's verified fields to TwinStore outputs. ✓ means directly available, ~ means derivable with assumptions or proxies, and blank means absent.

| Dataset | Funnel view→cart→checkout→pay→buy | Conv. rate / outcome shares | AOV / rev per session | Bounce / exit | Pages per session | Duration / dwell | Search use | Device | Traffic source | Age / gender | Ads | Click / list position |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D1 UCI Online Shoppers | ~ (Revenue only) | ✓ | ~ (PageValues) | ✓ (page-level avg) | ✓ | ✓ (per page type) | | ~ (OS / browser codes) | ~ (codes) | | | |
| D2 GA360 sample | ✓ incl. checkout steps | ✓ | ✓ | ✓ | ✓ | ✓ | ~ (pagePath) | ✓ | ✓ | | ~ (cpc medium) | ✓ list position |
| D3 GA4 obfuscated | ✓ (obfuscated) | ✓ | ✓ | ~ | ✓ | ✓ | ~ (search_term) | ✓* | ✓* | | | |
| D4 Kaggle GA revenue | ~ | ✓ | ✓ | ✓ | ✓ | ✓ | | ✓ | ✓ | | | |
| D5 KDD Cup 2000 | ~ | ✓ | ✓ | ✓ | ✓ | ✓ | | ~ browser | ✓ referrer | ~ logged-in only | | |
| D6 UCI clickstream 2008 | | | ~ price | ~ | ✓ | | | | | | | ✓ screen region |
| D7–9 REES46 | ✓ view / cart / (remove) / purchase | ✓ | ✓ | ~ (1-event sessions) | ✓ (product events) | ✓ | | | | | | |
| D10 Retailrocket | ✓ (no session ID) | ~ | ~ | ~ | ~ | ✓ | | | | | | |
| D11 YOOCHOOSE | ~ click / buy | ✓ | ✓ | ~ | ✓ | ✓ | | | | | | |
| D12 Diginetica | ~ view / click / buy | ✓ | ~ | ~ | ✓ | ✓ | ✓ (hashed) | | | | | ✓ result rank |
| D13 Coveo | ✓ detail / add / remove / purchase | ✓ | ~ (price bucket) | ~ | ✓ (page views) | ✓ | ✓ (vector) | | | | | ✓ impressions |
| D14 OTTO | ✓ click / cart / order | ✓ | | ~ | ✓ | ✓ | | | | | | |
| D15 Dressipi | (purchase-only) | | | | ✓ | ~ | | | | | | |
| D16 Amazon-M2 | | | | | ✓ | | | | | | | |
| D17 Synerise | ✓ cart / remove / buy + page visit | ✓ | | ~ | ✓ | ✓ | ✓ (embedding) | | | | | |
| D18 Taobao UserBehavior | ✓ pv / cart / fav / buy | ~ | | ~ | ~ | ✓ | | | | | | |
| D19 Tmall IJCAI-15 | ✓ click / cart / fav / buy | ~ | | | | ~ | | | | ✓ | | |
| D20 JD MSOM | ~ click / order | ✓ | ✓ | | | ✓ | | ~ (channel)? | | ~ gender | | |
| D21 JDsearch | ~ | ~ | | | | ✓ | ✓ (anon.) | | | | | |
| D25 trivago | ~ clickout | ~ | ~ price | | ✓ | ✓ | ✓ (destination search) | ✓ | | | | ✓ impressions |
| D26 Expedia | ~ click / book | ✓ | ~ | | | | | | | | | ✓ randomized rank |
| D28–33 Criteo / Avazu / Taobao ads / Ali-CCP | | ✓ (post-click CVR) | ~ (D29 sales) | | | | | ✓ (D29, D31) | | ✓ (D32) | ✓ | ~ (banner position) |
| D34 Ponpare | ~ view / purchase | ✓ | ✓ | ~ | ✓ (PAGE_SERIAL) | ✓ | | | ✓ (referrer hash) | ✓ | | |
| D35–38 H&M / Instacart / Olist / Online Retail | purchase only | | ✓ | | | | | | | ✓ (H&M age) | | |

  \*GA4 device and traffic_source come from the GA4 export schema. They were not verified in this session; confirm them by query.
- A defensible "ground-truth panel" for a paper would combine:
  1. **GA360 sample (D2)** for the full web funnel, bounce, duration, exit pages, device and source.
  2. **UCI Online Shoppers (D1)** for an independent session-level conversion and page-mix check.
  3. **REES46 (D7/D8)** and **OTTO (D14)** for large-sample event transition matrices and add-to-cart / abandonment.
  4. **Coveo (D13)** and **Diginetica (D12)** for search usage and post-search behaviour.
  5. **trivago (D25)** for UI-action transitions and device.
  6. **Tmall (D19)**, **Taobao ads (D32)** and **Ponpare (D34)** for age and gender segments.
  7. **Expedia (D26)** for position bias.
  8. **UCI clickstream 2008 (D6)** for on-screen click position.
  9. **Criteo (D28/D29)** for ad CTR and conversion.
- Because several of these sets come from different countries (US, Germany, Poland, China, Japan, Russia, Brazil), the paper should treat them as an *envelope* of plausible human behaviour rather than a single target. Example: conversion is 15.5% of sessions in D1, versus 18,025 purchases over 573,935 sessions (about 3%) in D12, and much lower still per session in Retailrocket.

### Gaps
- No exact session counts were verified for the GA360 sample (D2) or the GA4 sample (D3). BigQuery could not be queried from this environment (no GCP project). Run Google's sample `COUNT(DISTINCT user_pseudo_id)` query to obtain them.
- The GA4 event-name inventory for the obfuscated set (whether `add_shipping_info`, `add_payment_info` and `view_search_results` with `search_term` actually appear) was not verified.
- The multi-category REES46 event-type list was not shown in full, and the Kaggle file table wrongly says "Only one kind of event: purchase". It was not confirmed whether `remove_from_cart` exists there; it is documented for the cosmetics set.
- The JD MSOM user-table columns beyond gender, purchase power and membership (age, education, marital status, city level) and the clicks-table fields (channel) were not confirmed. The INFORMS page requires login.
- IJCAI-18 Alimama search-ad conversion data (Tianchi) was not verified. It is believed to have user gender and age, search-result page number and predicted query category, but treat it as unverified. Tianchi pages could not be fetched (redirect or login).
- Ali-CCP's user-demographic feature fields were not verified.
- Home Depot Product Search Relevance (Kaggle 2016), Mercari, Zalando and KuaiRand were not verified in this session. To my knowledge none of them provides shopper session logs: Home Depot is human relevance scores, Mercari is listing prices, KuaiRand is short-video and not e-commerce. No public Zalando behavior log was found.
- trivago's official statistics (unfiltered session and action counts, the price field) and the current download location were not verified, because the host no longer resolves.
- No public dataset with a real **"timed_out"** outcome or a **shopping-mission label** (purchase / browse / compare / deal_hunt / gift / replenish) was found. These must be inferred; see Q5.

---

## Q2. Which datasets include real checkout or payment funnel steps, page types, bounce or exit rates, session duration, device or traffic source?

### Takeaway
Explicit checkout and payment steps plus device and traffic source exist publicly only in the Google Merchandise Store analytics exports (GA360 sample, GA4 obfuscated sample, Kaggle GA revenue). Bounce and exit metrics are also native to UCI Online Shoppers and partly KDD Cup 2000. Every timestamped event log allows session duration and inter-event dwell. Device appears in trivago, Criteo Sponsored Search and Avazu. Referrer appears in Ponpare and KDD Cup 2000.

### Cited Findings
- **Checkout and payment steps:**
  - GA360 `hits.eCommerceAction.action_type` has 5 = checkout, 8 = checkout options and 6 = completed purchase, and `eCommerceAction.step` records the checkout step. — [UA export schema](https://support.google.com/analytics/answer/3437719?hl=en)
  - GA4 has `begin_checkout` and `add_payment_info` events, and the GA4 sample uses the standard ecommerce implementation. — [gtag reference](https://developers.google.com/gtagjs/reference/event?authuser=1); [GA4 sample doc](https://developers.google.com/analytics/bigquery/web-ecommerce-demo-dataset)
  - Olist has payment information, but only after the order. — [Kaggle Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
- **Page types and flows:**
  - UCI Online Shoppers has counts and durations by Administrative, Informational and ProductRelated page type. — [UCI](https://archive.ics.uci.edu/dataset/468/online+shoppers+purchasing+intention+dataset)
  - GA360 has `hits.page.pagePath` plus `isEntrance` and `isExit`. — [UA schema](https://support.google.com/analytics/answer/3437719?hl=en)
  - Coveo has `hashed_url` per pageview. — [Coveo GitHub](https://github.com/coveooss/SIGIR-ecom-data-challenge)
  - Synerise has `page_visit` with a url ID. — [Synerise](https://recsys.synerise.com/summary)
  - KDD Cup 2000 has page URL and assortment. — [UW notes](https://courses.cs.washington.edu/courses/csep546/03sp/proj1/proj1_data.html)
  - UCI clickstream 2008 has main category and page number. — [UCI](https://archive.ics.uci.edu/dataset/553/clickstream+data+for+online+shopping)
- **Bounce and exit:**
  - GA360 has `totals.bounces` and `hits.isExit`. — [UA schema](https://support.google.com/analytics/answer/3437719?hl=en)
  - UCI Online Shoppers has BounceRates and ExitRates as GA page metrics. — [UCI](https://archive.ics.uci.edu/dataset/468/online+shoppers+purchasing+intention+dataset)
  - KDD Cup 2000's question was whether a visitor would view another page or leave, plus "killer pages". — [organizer report summary](https://courses.cs.washington.edu/courses/csep546/07sp/proj1/kddOrganizerReport.pdf)
- **Session duration and dwell:**
  - GA360 has `totals.timeOnSite` and `hits.time`. — [UA schema](https://support.google.com/analytics/answer/3437719?hl=en)
  - UCI Online Shoppers has per-page-type durations. — [UCI](https://archive.ics.uci.edu/dataset/468/online+shoppers+purchasing+intention+dataset)
  - Millisecond or second timestamps exist in Coveo, OTTO, REES46 and Retailrocket. — [Coveo](https://github.com/coveooss/SIGIR-ecom-data-challenge); [OTTO](https://github.com/otto-de/recsys-dataset); [REES46](https://www.kaggle.com/datasets/mkechinov/ecommerce-behavior-data-from-multi-category-store); [Retailrocket](https://www.kaggle.com/datasets/retailrocket/ecommerce-dataset)
  - Synerise page_visit timestamps are minute-level only. — [Synerise](https://recsys.synerise.com/summary)
  - Amazon-M2 sessions are product-ID lists with no timestamps. — [arXiv 2307.09688](https://arxiv.org/pdf/2307.09688)
- **Device:**
  - GA360 `device.deviceCategory` is Mobile, Tablet or Desktop. — [UA schema](https://support.google.com/analytics/answer/3437719?hl=en)
  - Kaggle GA revenue has a `device` JSON column. — [GitHub](https://github.com/abdkumar/Google-Analytics-Customer-Revenue-Prediction)
  - trivago has `device` and `platform`. — [arXiv 2012.06052](https://arxiv.org/pdf/2012.06052)
  - Criteo Sponsored Search has `device_type`. — [Criteo](https://ailab.criteo.com/criteo-sponsored-search-conversion-log-dataset/)
  - Avazu has device type and model. — [TIB Avazu](https://service.tib.eu/ldmservice/dataset/avazu-dataset)
  - UCI Online Shoppers has OS and Browser codes. — [UCI](https://archive.ics.uci.edu/dataset/468/online+shoppers+purchasing+intention+dataset)
  - KDD Cup 2000 has browser. — [UW notes](https://courses.cs.washington.edu/courses/csep546/03sp/proj1/proj1_data.html)
- **Traffic source:**
  - GA360 `trafficSource.source` and `trafficSource.medium` cover organic, cpc, referral and utm values. — [UA schema](https://support.google.com/analytics/answer/3437719?hl=en)
  - UCI Online Shoppers TrafficType is an unlabelled code. — [UCI](https://archive.ics.uci.edu/dataset/468/online+shoppers+purchasing+intention+dataset)
  - Ponpare has `REFERRER_hash`. — [schema](https://github.com/TsinghuaDatabaseGroup/datasets)
  - KDD Cup 2000 has referrer. — [UW notes](https://courses.cs.washington.edu/courses/csep546/03sp/proj1/proj1_data.html)
- **Search usage:**
  - Diginetica distinguishes full-text queries from query-less category browsing (53,427 vs 869,700). — [arXiv 1708.04479](https://arxiv.org/pdf/1708.04479)
  - Coveo search events carry impressions and clicks. — [Coveo GitHub](https://github.com/coveooss/SIGIR-ecom-data-challenge)
  - JDsearch has 9.4M real searches. — [arXiv 2305.14810](https://arxiv.org/abs/2305.14810v1)
  - Synerise has search_query events. — [Synerise](https://recsys.synerise.com/summary)
- **Position:**
  - GA360 has `productListPosition`. — [UA schema](https://support.google.com/analytics/answer/3437719?hl=en)
  - Expedia has `position` with randomized ordering in about 30% of searches. — [arXiv 2605.17238](https://arxiv.org/pdf/2605.17238)
  - Criteo attribution has `click_pos`, which is the click's order in the path, not its screen position. — [Criteo](https://ailab.criteo.com/criteo-attribution-modeling-bidding-dataset/)
  - UCI clickstream 2008 records the photo's screen location in six regions. — [UCI](https://archive.ics.uci.edu/dataset/553/clickstream+data+for+online+shopping)

### Inferences
- GA360 (D2) is the only public, non-competition-gated, real (lightly obfuscated) dataset that can validate checkout-step drop-off. It is the primary target for TwinStore's checkout → payment → purchase funnel. GA4 (D3) can corroborate it but must be labelled obfuscated, with limited internal consistency.
- Two kinds of "bounce" must be kept apart. For GA-based sets it is a native session flag. For product-event logs it can only be proxied as "sessions with exactly one recorded event", and because those logs record product events only, landing-page-only visits are invisible and the proxy is biased.
- The simulator's direct / search engine / social / email split can be mapped to GA `trafficSource.medium`: (none) → direct, organic → search engine, referral/social → social, email → email. No other public dataset labels these channels in human-readable form.

### Gaps
- The checkout-step definitions (step numbers to page names) used by the Google Merchandise Store in 2016–2017 were not verified. They must be inferred from `pagePath` values such as basket, checkout and payment URLs.
- No public dataset was found with real checkout-page **form abandonment** at the field level, or **payment failure** events.

---

## Q3. Which datasets include user demographics (age, gender) for comparing segment behavior?

### Takeaway
Real behavior logs with user age and gender come mainly from Alibaba (Tmall IJCAI-15 and the Taobao display-ad user profiles), Recruit Ponpare (age, sex, prefecture with session-level browsing) and JD MSOM (gender, purchase power). H&M has age with purchases only. KDD Cup 2000 has perturbed demographics for logged-in users only. None of the Western web-analytics sets (GA360, UCI Online Shoppers) has age or gender.

### Cited Findings
- Tmall IJCAI-15: the user profile has an age range and gender, linked to action-type logs (click, add-to-cart, purchase, favourite). — [arXiv 2206.00510](https://arxiv.org/pdf/2206.00510)
- Taobao display ads: the user_profile covers 1.06M users with gender (1 male / 2 female), age_level, consumption grade (low / mid / high), shopping depth (shallow / moderate / depth), college-student flag and city level, linked to 26M ad impressions and clicks and to 22 days of shopping behaviour. — [Kaggle mirror](https://www.kaggle.com/datasets/pavansanagapati/ad-displayclick-data-on-taobaocom)
- Ponpare: `user_list` has SEX_ID, AGE and PREF_NAME, joinable to `coupon_visit_train` (session, page serial, referrer, purchase flag). — [schema](https://github.com/TsinghuaDatabaseGroup/datasets)
- JD MSOM 2020: user fields include membership, gender and purchase power (some estimated). — [Atlantis Press](https://www.atlantis-press.com/article/125982184.pdf)
- H&M: customer features include age, postal code, club membership and fashion-news frequency. — [Polimi thesis](https://www.politesi.polimi.it/bitstream/10589/204133/1/Master_Thesis_With_Summary_Arcangelo-Pisa.pdf)
- KDD Cup 2000: customer attributes and questionnaire responses were attached only when a registered user logged in, with personal information removed or perturbed. — [search summary of organizer material](https://www.kdnuggets.com/news/2000/n10/3i.html)
- OPeRA: personas come from surveys and interviews covering demographics, personality and shopping preferences, for 51 users. — [arXiv 2506.05606](https://arxiv.org/pdf/2506.05606)
- GA360 sample: no age or gender fields. — [UA schema](https://support.google.com/analytics/answer/3437719?hl=en)
- Criteo Sponsored Search `product_age_group` and `product_gender` are product attributes, not user demographics. — [Criteo](https://ailab.criteo.com/criteo-sponsored-search-conversion-log-dataset/)

### Inferences
- To test TwinStore's age-group and gender differences, the strongest options are:
  - **Tmall** for click / cart / purchase by age and gender.
  - **Taobao display ads** for ad CTR by age and gender.
  - **Ponpare** for browsing-session length, referrer and conversion by age and gender, on a Japanese deal site.
  - **H&M** for spend by age.
- All of these come from Asian or European platforms in 2015–2022. Effect *directions*, such as whether older shoppers convert more or browse fewer pages, are a safer comparison than absolute levels.
- Age bins differ across datasets: Tmall uses age_range codes, Taobao age_level, Ponpare and H&M exact age. A harmonization table to TwinStore's 10s–60s groups is needed.

### Gaps
- No public Western (US or EU) web clickstream with user-level age and gender was found.
- The Tmall age_range code mapping and the Taobao age_level bins were not verified from Tianchi pages, which could not be fetched.

---

## Q4. Are there public datasets of real shoppers' web navigation trajectories with screenshots or actions?

### Takeaway
Yes, but they are small or task-directed:
- **OPeRA** (2025) is the closest match to TwinStore. It has real users' own shopping sessions with HTML and screenshot observations, actions, self-reported rationales and survey personas (692 sessions, 51 users).
- **ShopCART** (Amazon / Northeastern, 2025) has 31,865 real sessions but is **not released**. Its paper is still a key reference because it directly measures LLM-versus-human action alignment.
- **WebShop**, **Mind2Web**, **Online-Mind2Web** and **WebLINX** hold crowdsourced, instruction-following demonstrations rather than natural shopping.

### Cited Findings
- **OPeRA** (Observation, Persona, Rationale, Action; arXiv 2506.05606; ACL 2026; NeurIPS 2025 workshop) — [arXiv](https://arxiv.org/pdf/2506.05606); [ACL Anthology](https://aclanthology.org/2026.acl-long.2033/):
  - Full version: 692 sessions, 28,904 action–observation pairs, 604 rationales. Filtered version: 527 sessions, 5,856 pairs, 207 rationales. 51 users.
  - Observations are page HTML, simplified HTML and a screenshot.
  - Collected with a questionnaire and a custom browser plugin.
  - It provides a benchmark for next-action and rationale prediction.
- **ShopCART** ("Can LLM Agents Simulate Multi-Turn Human Behavior? Evidence from Real Online Customer Behavior Data", arXiv 2503.20749) — [arXiv HTML v7](https://arxiv.org/html/2503.20749v7):
  - Data: 31,865 sessions from 3,526 users, with 230,965 actions, 4,432 purchases and 27,433 terminations. Actions are click, type_and_submit and terminate, with simplified HTML context.
  - Release: **not public**, for privacy.
  - Results: prompt-only LLMs reached about 11.7–11.9% next-action accuracy (DeepSeek-R1 11.86%, Claude 3.5 Sonnet v2 11.69%). Fine-tuned Qwen2.5-7B with reasoning reached 17.26% accuracy and 33.86% purchase-vs-terminate F1.
  - Behaviour: humans average 2.82 searches per session and rarely use filters. Prompt-only LLMs bought more often than humans and repeated the initial search instead of refining it.
- **Customer-R1** (NeurIPS 2025): RL-trained persona-conditioned agents evaluated on OPeRA better match individual users' action distributions. RL-only training reward-hacks toward frequent simple actions. — [NeurIPS listing](https://neurips.cc/virtual/2025/128075)
- **WebShop** (arXiv 2207.01206): about 1.18M real products, 12,087 crowd-sourced instructions and over 1,600 human demonstrations. Human experts succeed about 59% of the time versus about 29% for the best agent. It is a simulated shop. — [arXiv](https://arxiv.org/abs/2207.01206)
- **Mind2Web**: over 2,000 open-ended tasks from 137 websites across 31 domains, with crowdsourced action sequences. — [Mind2Web summary](https://cdnjs.deepai.org/publication/mind2web-towards-a-generalist-agent-for-the-web)
- **Online-Mind2Web**: 300 tasks across 136 live websites, including shopping. 36 tasks were updated in Nov 2025. — [arXiv 2504.01382](https://arxiv.org/html/2504.01382v4); [GitHub](https://github.com/OSU-NLP-Group/Online-Mind2Web)
- **WebLINX**: 2,337 expert demonstrations of conversational web navigation across 155 real websites. — [arXiv 2402.05930](https://www.arxiv-vanity.com/papers/2402.05930)

### Inferences
- For a TwinStore paper, ShopCART's findings set an **expected failure-mode baseline**: LLM shoppers over-purchase and under-refine search. The paper should test explicitly whether TwinStore's purchase share and search-refinement rate fall in the human range, using GA360, REES46 and Coveo as references.
- OPeRA is the only public set pairing *screenshots* and personas with real actions. It is small, but it allows step-level comparison of TwinStore's numbered-option choice against the human next action, plus persona-conditioned differences.
- Mind2Web, WebLINX and WebShop measure task competence, not natural shopping behaviour. Use them only to argue that the agent can navigate, not that it behaves like the population.

### Gaps
- OPeRA's host website (e.g., Amazon) and its license and download location were not confirmed in this session.
- The WebShop human-demonstration collection platform and the data license were not confirmed.
- No public large-scale (more than 10k sessions) human shopping trajectory set with screenshots was found.

---

## Q5. What preprocessing is needed to derive metrics comparable to TwinStore outputs?

### Takeaway
Comparable metrics require four things:
1. A common **session definition**, usually a 30-minute inactivity split.
2. An explicit **event-type mapping** to TwinStore's funnel states.
3. Careful handling of **censoring**: last-page dwell is unobserved, and test sessions are truncated.
4. Clear labelling of what cannot be measured in a given dataset, such as bounce in product-event-only logs or conversion in purchase-only sessions.

### Cited Findings
- Coveo's sessions already use a 30-minute inactivity rule, and its timestamps are shifted by an unspecified number of weeks, so absolute dates and seasonality are unusable. — [Coveo GitHub](https://github.com/coveooss/SIGIR-ecom-data-challenge)
- REES46 `user_session` "is changed every time user come back to online store from a long pause". Multiple purchase events in one session form one order. — [Kaggle REES46](https://www.kaggle.com/datasets/mkechinov/ecommerce-events-history-in-cosmetics-shop)
- Retailrocket has visitorId and timestamp but no session ID. Its item properties are weekly snapshots, so prices must be time-joined. — [Kaggle Retailrocket](https://www.kaggle.com/datasets/retailrocket/ecommerce-dataset)
- GA360 `hits.time` is measured in ms from session start, `totals.timeOnSite` is in seconds, and bounces are a native flag. — [UA schema](https://support.google.com/analytics/answer/3437719?hl=en)
- Dressipi sessions all end in a purchase. — [ETH](https://www.research-collection.ethz.ch/items/558fe8bb-63e0-47c9-a97f-ed5d9a493058)
- Amazon-M2 sessions are product-ID lists only. — [arXiv 2307.09688](https://arxiv.org/pdf/2307.09688)
- Expedia's randomized subset (`random_bool` = 1) isolates pure position bias. — [arXiv 2605.17238](https://arxiv.org/pdf/2605.17238)
- The Criteo attribution timestamps start at 0, and its cost and CPO values are transformed. — [Criteo](https://ailab.criteo.com/criteo-attribution-modeling-bidding-dataset/)
- In the GA4 obfuscated data, placeholders (`<Other>`, NULL, '') and limited internal consistency mean joins across fields can mislead. — [Google Developers](https://developers.google.com/analytics/bigquery/web-ecommerce-demo-dataset)

### Inferences

**1. Sessionization.** This is the recommended preprocessing, derived by me from the field definitions above.
- Use native session IDs where they exist: GA360 visitId, REES46 user_session, Coveo, OTTO, YOOCHOOSE, Diginetica, Ponpare, trivago.
- Otherwise use a 30-minute inactivity split per user: Retailrocket, Taobao UserBehavior, Tmall, Synerise.
- Report sensitivity of the results to 15, 30 and 60 minute splits.

**2. Event mapping to the TwinStore funnel.**

| TwinStore stage | GA360 | REES46 | Coveo | OTTO | Retailrocket | Taobao |
|---|---|---|---|---|---|---|
| visit | session | session | session | session | session | session |
| product_view | action_type 2 | view | detail | clicks | view | pv |
| add_to_cart | 3 | cart | add | carts | addtocart | cart |
| checkout | 5 / step | – | – | – | – | – |
| payment | 8 / step ≥ n | – | – | – | – | – |
| purchase | 6 | purchase | purchase | orders | transaction | buy |

- Only GA360 and GA4 have checkout and payment states. For the other sets, collapse TwinStore's checkout and payment states into "cart → purchase".

**3. Outcome shares.** These map TwinStore's outcomes onto human logs.
- purchased: the session has a purchase.
- abandoned_cart: the session has add_to_cart but no purchase.
- bounced: the session has one pageview (GA) or one event (event logs, flagged as a proxy).
- left: everything else.
- timed_out has no human analogue. Either drop it or map it to sessions that hit TwinStore's step cap, and report it separately.

**4. Dwell time.**
- Dwell is the difference between consecutive event timestamps.
- The last page's dwell is unobserved in all logs. GA timeOnSite also excludes it. Compute TwinStore's dwell the same way, excluding the last page, for a fair comparison.
- Winsorize gaps above 30 minutes, because they are session breaks.
- Coveo and Synerise page_visit timestamps are coarse or shifted, so use them for relative gaps only.

**5. Pages per session.**
- GA `totals.pageviews` maps to TwinStore steps.
- For product-event logs, count events. Note that this counts product interactions, not pages, so it undercounts the home, category and search pages that TwinStore records.

**6. Search metrics.**
- Diginetica: share of queries that are full-text versus browse, as the share of sessions with a text query.
- Coveo: share of sessions with a search event. A zero-result proxy is a search whose `product_skus_hash` is empty (to be verified).
- JDsearch: searches per session.
- Query text exists only in ESCI and KuaiSearch, and GA4 if `search_term` survives obfuscation. Elsewhere, compare query length in tokens (Diginetica and JDsearch hashed tokens) or embedding similarity (Coveo and Synerise vectors), not wording.

**7. AOV and revenue per session.**
- Sum price × quantity per purchase session in REES46, YOOCHOOSE and GA360.
- Treat multiple purchase rows in a REES46 session as one order.
- Exclude cancellations ("C" invoices) in Online Retail.
- Convert currencies and deflate where comparing across years. Compare distribution shapes (log-normal fit, CV), since absolute price levels depend on the store.

**8. Transition matrices.** Build first-order Markov matrices over the mapped event alphabet and compare them to TwinStore with:
- Jensen–Shannon divergence per row.
- Stationary distributions.
- Absorbing-state probabilities, such as P(purchase | cart).

**9. Position effects.** Use Expedia `random_bool` = 1 rows to estimate CTR by rank, then compare to TwinStore's chosen-option-index distribution. UCI clickstream 2008 gives the click share across the six screen regions.

**10. Segments.**
- Device and source come only from GA360 / GA4 / Kaggle GA; trivago adds device. Age and gender come from Tmall, Taobao ads, Ponpare and H&M.
- Missions are not labelled anywhere. Proxy them as follows:
  - purchase: a session with a search followed by a cart within N steps.
  - browse: many views, no cart.
  - compare: repeated views within one category.
  - deal_hunt: SpecialDay / Double 11 / coupon-site sessions.
  - replenish: Instacart reorders.
  - gift: no proxy found.

**11. Bot and outlier filtering.** Drop sessions with more than 200–500 events or sub-second inter-event times (REES46 and OTTO contain heavy users) before comparing distributions. The thresholds must be reported.

### Gaps
- No standard published preprocessing for "bounce" or "cart abandonment" on REES46, OTTO or Coveo was found. Papers mostly use these data for next-item prediction. The definitions above are proposals.
- Whether Coveo search rows with empty `product_skus_hash` really indicate zero-result searches was not verified.
- No dataset has a mission label, a gift-purchase flag or a session-timeout outcome comparable to TwinStore's `timed_out`.
