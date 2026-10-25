# Causal evidence on how online-store design levers change real shopper behavior (benchmarks for TwinStore A/B validation)

Scope note: for each TwinStore lever this file lists the best quantitative evidence found, with study, setting, design, outcome, effect size and link. Evidence grades used throughout:
**A** = randomized field experiment / RCT on real shoppers, peer-reviewed or regulator; **B** = natural/quasi-experiment or large observational panel; **C** = lab/online-panel experiment or survey; **D** = vendor/consultant case study (low quality, often unreplicated, selection-biased toward "wins"). Where only C/D evidence exists this is stated explicitly.

## Overview: which levers have strong causal benchmarks for directional/magnitude agreement?

### Takeaway
Only a handful of levers have peer-reviewed field-experiment benchmarks with effect sizes on real purchases: drip pricing (StubHub RCT), shipping fees/free-shipping (Lewis-Singh-Fay; Shehu et al.), dark-pattern add-ons/defaults (Luguri & Strahilevitz, large online panels plus default meta-analysis), position/ranking (Ursu, Expedia RCT), sponsored listings (Blake-Nosko-Tadelis eBay; Moshary), recommendations (Lee & Hosanagar), discount emails/retargeting (Sahni et al.), trust seals (Özpolat et al.), one-click checkout (Unal & Park) and BNPL (Berg et al.). Page speed, guest checkout, one-page checkout, promo-code boxes, popups, abandoned-cart emails, large-text mode, grid density and quick-add are supported mainly by observational industry data or vendor case studies.

### Cited Findings (summary table; details and links in the sections below)

| TwinStore lever | Expected direction on real shoppers | Best evidence (grade) | Headline magnitude |
|---|---|---|---|
| Shipping fee / free-shipping threshold | Fees ↓ conversion; free shipping ↑ orders & basket but ↑ returns; raising threshold ↓ spend | Lewis, Singh & Fay 2006 (B, retailer's own fee experiments); Shehu et al. 2020 (B + field test); Gümüş et al. (B, DiD, working paper) | Free-shipping promotion: order volume +11%, profit −0.7%; threshold $80→$100: spend −19.4% |
| Drip pricing (fee shown only at review) | ↑ purchase and revenue for the firm, ↑ checkout exits, ↓ satisfaction | Blake et al. 2021 StubHub RCT (A) | Back-end fees: revenue/user +~21%, purchase propensity +14.1%, checkout-stage purchase −45% vs upfront-fee users reaching checkout |
| Pre-ticked add-on / defaults | ↑ add-on take-up | Jachimowicz et al. 2019 meta-analysis (A/C mix); Luguri & Strahilevitz 2021 (C, N=3,777) | d = 0.68; preselected default 20.1% vs 16.7% acceptance |
| Hidden information / dark patterns | ↑ acceptance; aggressive ones ↑ anger | Luguri & Strahilevitz 2021 (C, large census-weighted US panels) | Mild 25.8% / aggressive 41.9% vs 11.3% control |
| Guest checkout vs forced account | Forced account ↓ conversion | Baymard survey (C); Spool "$300M button" (D) | 18% of abandoners cite forced account; +45% purchasers after removing "Register" |
| One-page vs multi-step checkout | Small/uncertain | Elastic Path 2010 (D) | +21.8% (606 transactions; weak control) |
| One-click buy | ↑ spend & frequency | Unal & Park 2023 Mgmt Sci (B, pre/post) | Spend +28.5%, frequency +43% |
| Payment methods (wallets, BNPL, COD) | Adding methods ↑ conversion | Berg et al. 2025 JFE (BNPL, B/A); Stripe 2024 (D) | BNPL sales +20%; Apple Pay ~+10% conversion |
| Return policy | Lenient ↑ purchases (and some returns) | Janakiraman et al. 2016 meta-analysis; Bower & Maxham 2012 (B) | Fee returns: post-return spending −75% to −100% |
| Trust badges | ↑ conversion (diminishing beyond 2 seals) | Özpolat et al. 2013 ISR (A, 9,098 sessions) | Positive, significant (exact % not verified) |
| Page load time | Slower ↓ conversion | Deloitte/Google 2020 (B); Akamai 2017 (B); Bing/Google tests (A, search) | 0.1 s faster → retail conversion +8.4%; Bing +1.5 s → revenue/user −4.3% |
| Scarcity / urgency | Small positive on intentions; countdown timers often null | Barton et al. 2022 meta-analysis (mostly C); Luguri 2021 (C) | Purchase intention δ = 0.31; countdown timer 14.3% vs 14.8% (n.s.) |
| Social proof | ↑ choice, esp. niche items | Tucker & Zhang 2011 (A); Chen, Wang & Xie 2011 (B); Luguri 2021 (C) | Social proof 22.1% vs 14.8% acceptance |
| Star ratings & review counts | ↑ conversion; peak at 4.2–4.5 stars | Spiegel 2017 (B, observational); Luca (B, RD); Chevalier & Mayzlin 2006 (B) | 5 reviews vs 0: purchase likelihood +270%; +1 Yelp star → revenue +5–9% |
| Sponsored listings | ↑ sponsored sales but cannibalize organic; net platform sales ↓ | Moshary (A, 3% holdout); Blake, Nosko & Tadelis 2015 (A) | Net negative on total sales; brand-keyword ads ≈ 0 effect |
| Recommendations | ↑ conversion | Lee & Hosanagar 2016/2019 (A) | Conversion +5.9% |
| Ranking / default sort | Position ↑ clicks/search, little effect on purchase given search | Ursu 2018 (A, Expedia random ranking) | Avg position effect ≈ $2.64 (dissertation figure) |
| Cookie banner / consent | Design changes consent rates strongly; GDPR cut recorded traffic | Utz et al. 2019 (A, >80K users); Nouwens et al. 2020 (A-small); Goldberg et al. 2024 (B) | Removing first-page "reject" +22–23 pp consent; GDPR −12% recorded pageviews & revenue |
| Welcome / promo popup | Interstitials ↑ abandonment | Google+ 2015 (D/internal test) | 69% abandoned page; removal +17% 1-day actives |
| Abandoned-cart reminders / discounts | ↑ return and purchase; discount spillover | Sahni et al. 2017 (A, 70 RCTs); Sahni, Narayanan & Kalyanam 2019 (A) | Discount emails +37% spend; retargeting cart abandoners +5.4% |
| Visible promo-code field | ↓ conversion (small) | GoodUI aggregation (D) | Median ~+2.5% sales when removed; one outlier +24% revenue |
| Large-text accessibility mode | Accessibility ↑ retention of disabled users | Click-Away Pound 2019 (C, survey) | 69% of disabled shoppers click away from hard sites |
| Products per page / grid / infinite scroll / quick add-to-cart | Unclear | Etsy infinite-scroll test (D); choice-overload meta-analyses (C) | No reliable e-commerce effect size found |

### Inferences
- For a paper arguing "directional/magnitude agreement", the most defensible benchmark levers are those with grade-A/B evidence on actual purchases: drip pricing, shipping fees/thresholds, pre-ticked add-ons/dark patterns, ranking, sponsored listings, recommendations, return-fee policy, one-click checkout, BNPL and page speed. Levers with only D-grade evidence should be framed as "consistent with practitioner reports", not validation.
- Several real-world effects are **counter-intuitive or null**, which makes them strong discriminating tests for simulated agents: drip pricing *raises* revenue; countdown timers had *no* effect in a large panel; Expedia ranking affects search but not purchase conditional on search; price stakes ($2.99 vs $8.99) did not change dark-pattern acceptance; sponsored search *reduced* total platform sales; free-shipping promotions raised volume but *lowered* profit via returns. An LLM agent that simply "acts rationally" or "follows marketing folklore" would likely miss some of these.

### Gaps
- Almost no peer-reviewed RCTs exist for: one-page vs multi-step checkout, quick add-to-cart, grid columns/products per page, large-text modes, newsletter popups, search zero-result handling, hero banners and cart upsells.

## Shipping fees and free-shipping thresholds

### Takeaway
Real shoppers are highly sensitive to shipping fees: free shipping (and threshold free shipping) raises order incidence and volume, thresholds raise basket size (order padding), but returns rise and promotions are often unprofitable; raising a threshold can sharply cut spending. "Extra costs too high" is the #1 stated abandonment reason.

### Cited Findings
- **Lewis, Singh & Fay (2006), Marketing Science 25(1):51–64, DOI 10.1287/mksc.1050.0150.** Online retailer that experimented with many shipping-fee schedules; ordered-probability model of order incidence and basket size. Consumers are "very sensitive to shipping charges"; free shipping and free shipping above a threshold are "very effective in generating additional sales", but lost shipping revenue and non-response of several segments made the promotions unprofitable. Design: retailer's own fee-schedule variation over time (quasi-experimental, B). Country not stated in the abstract. — [IDEAS/RePEc abstract](https://ideas.repec.org/a/inm/ormksc/v25y2006i1p51-64.html); [INFORMS](https://pubsonline.informs.org/doi/fpi/10.1287/mksc.1050.0150)
- **Lewis (2006), Journal of Retailing 82(1):13–23, DOI 10.1016/j.jretai.2005.11.005**, "The effect of shipping fees on customer acquisition, customer retention, and purchase quantities." A later review summarizes it as finding purchase incidence higher and order size lower under free shipping than under size-dependent fees (full text not retrieved). — [Univ. of Groningen SOM report citing it](https://www.rug.nl/feb/research/som-research-reports/som-research-reports-2021/2021012-mark-def.pdf)
- **Shehu, Papies & Neslin (2020), Journal of Marketing Research 57(4):640–658, DOI 10.1177/0022243720921812.** Anonymous European multi-category online retailer (authors at CBS/Tübingen/Tuck), 154 weeks of customer data; average customer return share ≈37% of basket; free-shipping promotions active in 15% of weeks. Free-shipping promotions increase spend on high-risk (likely-returned) products and therefore return rates; validated by a field experiment, plus a field test and online lab experiment on mechanism. Profit simulation: free shipping raises total order volume **+11%** but profit falls **−0.7%** (handling costs per basket +3.7%, lost shipping revenue); an equal-value coupon raises order volume **+13%** and is profitable; average basket size **+3.23%** under free shipping. — [CBS accepted manuscript](https://research-api.cbs.dk/ws/portalfiles/portal/67886147/edlira_shehu_et_al_free_shipping_promotions_and_product_returns_acceptedversion.pdf)
- **Li, Tsekouras & Cheng (ICIS 2018), "Free shipping 3.0".** Randomized field experiment at an online retailer: unconditional free shipping produced conversion rates at least **2.2% higher** than threshold-based free shipping; scarcity information raised purchase likelihood more than popularity information (conference paper; country not verified). — [AIS eLibrary](https://aisel.aisnet.org/icis2018/economics/Presentations/12); [LSE Research Online](https://researchonline.lse.ac.uk/id/eprint/102913)
- **Gümüş et al., "How to and how not to increase free shipping thresholds" (working paper/seminar).** North American online grocery platform, difference-in-differences with transaction and clickstream data: raising the contingent-free-shipping threshold from **$80 to $100 reduced consumer spending 19.4%**, mainly via lower cart value, with smaller drop in purchase frequency; consumers bought fewer distinct and lower-priced items. — [CUHK Business School seminar abstract](https://www.bschool.cuhk.edu.hk/events/how-to-and-how-not-to-increase-free-shipping-thresholds-evidence-from-online-retail/)
- Order padding: a Wharton dissertation using an online apparel retailer's transaction data models customers inflating orders to qualify for free shipping, and finds threshold policies work best with high margins, low shipping revenue and low return probability. — [Penn repository](https://repository.upenn.edu/edissertations/2648/)
- **Shampanier, Mazar & Ariely (2007), Marketing Science 26(6):742–757.** Lab/field-style experiments: a price of zero is perceived as disproportionately more valuable ("the reduction of a price to zero is more powerful than a five-times-larger price reduction within the range of positive prices"); affect is the proposed mechanism. Relevant to "free" vs "$0.99" shipping. — [IDEAS](https://ideas.repec.org/a/inm/ormksc/v26y2007i6p742-757.html); [Duke PDF](https://people.duke.edu/~dandan/webfiles/PapersPI/Zero%20as%20a%20Special%20Price.pdf)
- **Baymard Institute (survey, US online shoppers, page updated Sept 2025):** documented average cart-abandonment rate **70.22%** (mean of 50 studies); among checkout abandoners (excluding "just browsing"), **40%** left because extra costs (shipping, tax, fees) were too high and **12%** because they couldn't see/calculate total order cost up-front. Survey N not given on the page. — [Baymard cart abandonment list](https://baymard.com/lists/cart-abandonment-rate)
- Field auction experiments (Brown, Hossain & Morgan; Yahoo Taiwan and eBay Ireland): sellers with low shipping fees gain by disclosing them upfront, while for high shipping charges shrouding raises revenue. — [Brown, Hossain & Morgan PDF](https://faculty.haas.berkeley.edu/rjmorgan/shrouding.pdf)

### Inferences
- A faithful simulator should show: fee → lower conversion; free shipping → higher conversion and orders but small/negative revenue-per-session after returns; threshold → higher AOV near the threshold; higher threshold → lower spend. The magnitude anchors (+11% order volume; −19.4% spend after a 25% threshold hike; 40% of abandoners citing extra costs) are usable for magnitude checks.

### Gaps
- The often-repeated Amazon France "1 franc / 10 cents vs free shipping" anecdote attributed to Ariely could not be verified from a primary source (secondary accounts disagree on the amount).
- Koukova, Srivastava & Steul-Fischer (2012) and Gümüş, Li, Oh & Ray (2013) on shipping-fee structure were not retrieved; no effect sizes recorded.
- Lewis-Singh-Fay exact elasticities not retrieved (abstract only).

## Drip pricing / hidden fees revealed at order review

### Takeaway
The strongest causal evidence (StubHub RCT, several million US users) shows drip pricing *increases* firm revenue (~21%) and purchase propensity (~14%) and shifts buyers to pricier items, while more shoppers drop out at checkout once fees appear; lab studies show drip-priced buyers often stick with a worse total deal and are less satisfied. Regulators (FTC, CMA, OFT) treat it as harmful.

### Cited Findings
- **Blake, Moshary, Sweeney & Tadelis, "Price Salience and Product Choice", Marketing Science 40(4), 2021 (NBER WP 25186, 2018).** StubHub (US) randomized 50/50 of users in August 2015 to Upfront Fees (all-in price from first view) vs Back-end Fees (fees ~15% of ticket price shown only at checkout); "several million users" over 10 days. Results (NBER version, Table 3): Back-end-fee users spent **~21% more** (10-day revenue per cookie +20.64%); transaction rate over the experiment **+14.1%**; within-session purchase probability **+12.43%** (implied salience elasticity 0.87); average seat price **+5.73%**; quality upgrades account for **≥28%** of the revenue difference. Funnel: back-end-fee users were ~19% more likely to click through to ticket details but **~45% less likely to purchase at the checkout/review page** (18.52% vs 33.41% click-through to purchase). Effects persisted for experienced users (top 6% of users: revenue effect 15%). — [NBER WP 25186](https://www.nber.org/papers/w25186.pdf); [AEA abstract](https://www.aeaweb.org/conference/2021/preliminary/paper/6AhfTz25)
- **Santana, Dallas & Morwitz (2020), "Consumer Reactions to Drip Pricing", Marketing Science 39(1):188–210, DOI 10.1287/mksc.2019.1207.** Six studies (lab/online experiments): when optional surcharges are revealed later, consumers more often choose a lower base-price option that ends up costing more in total, tend to keep it after the total is revealed, and report relatively more dissatisfaction; mechanisms include perceived search costs, self-justification and the belief that all firms charge similar fees. — [Columbia PDF](https://business.columbia.edu/sites/default/files-efs/pubfiles/26100/Santana%20Dallas%20Morwitz%20Marketing%20Science%20forthcoming.pdf)
- **Huck & Wallace (UCL, with London Economics) for the UK Office of Fair Trading (OFT-commissioned after a Which? super-complaint; paper 2015).** Lab experiments on price frames: all frames hurt consumers but drip pricing was "by far" the worst; consumers systematically underestimate total price and search too little. Led to 12 airlines including debit-card charges in headline prices in 2012. — [UCL impact case study](https://www.ucl.ac.uk/impact/case-studies/2014/dec/applied-research-leading-regulation-drip-pricing); [REF case study](https://impact.ref.ac.uk/casestudies/CaseStudy.aspx?Id=42605)
- **Rasch, Thöne & Wenzel (2020), J. of Economic Behavior & Organization 176:353–370.** Market lab experiment: sellers compete on base price and set maximal drip prices; few buyers pay to search drip prices; drip pricing lowers consumer surplus and raises seller profits vs a Bertrand benchmark. — [White Rose eprints](https://eprints.whiterose.ac.uk/159217); [ZEW](https://www.zew.de/PU82119)
- **Luguri & Strahilevitz (2021) Study 2 (N=3,777 US adults, 2020):** "hidden information" (price/terms de-emphasized) raised acceptance of an add-on from **14.8% to 30.1%** — the strongest content-based dark pattern tested. — [Journal of Legal Analysis 13(1):43](https://academic.oup.com/jla/article/13/1/43/6180579)
- Regulation: the US FTC Rule on Unfair or Deceptive Fees (all-in pricing for live-event tickets and short-term lodging) took effect 12 May 2025; StubHub later agreed to a $10M settlement over alleged non-all-in displays. — [JD Supra](https://www.jdsupra.com/legalnews/ftc-v-stubhub-10-million-settlement-8021470/). The UK CMA's Online Choice Architecture evidence review (April 2022) covers drip pricing under "choice pressure"; DMCC Act enforcement targets it. — [CMA evidence review](https://www.gov.uk/government/publications/online-choice-architecture-how-digital-design-can-harm-competition-and-consumers/evidence-review-of-online-choice-architecture-and-consumer-and-competition-harm); [Ashurst commentary](https://www.ashurst.com/en/insights/mind-the-nudge-the-dmccs-crackdown-on-manipulative-online-design/)

### Inferences
- The key real-world signature for TwinStore's "service fee revealed at order review" variant is two-sided: **higher conversion/revenue per session** overall, but **more drop-off at the review step** among those who reach it, and **lower satisfaction**. An agent that only abandons on fee reveal (and therefore shows lower conversion) would *disagree* with the StubHub direction; this is a sharp test.

### Gaps
- A WZB lab discussion paper (SP II 2013-314) reportedly finds drip pricing removes ~25% of consumer surplus; authors not confirmed here.
- No retrieved field evidence on drip fees in general merchandise e-commerce (StubHub is ticketing).

## Dark patterns, pre-ticked add-ons and defaults

### Takeaway
Defaults and mild dark patterns reliably raise acceptance of add-ons: a 58-study meta-analysis finds d = 0.68 for defaults; a large US experiment found mild dark patterns more than doubled and aggressive ones nearly quadrupled acceptance of an unwanted protection plan, with aggressive patterns triggering anger and drop-out. Dark patterns are near-ubiquitous on real sites.

### Cited Findings
- **Luguri & Strahilevitz (2021), "Shining a Light on Dark Patterns", Journal of Legal Analysis 13(1):43–109, DOI 10.1093/jla/laaa006.** Study 1 (US online sample; analyzed N=1,762): after being told they'd been enrolled in a fictitious data/identity-theft protection plan, acceptance was **11.3% control (73/644), 25.8% mild (155/600), 41.9% aggressive (217/518)**. Price ($2.99 vs $8.99/month) had **no significant effect** on acceptance (χ²=0.76, p=.38). Anger expressed: 5.7% control, 6.1% mild, **12.8% aggressive**; aggressive condition also had higher drop-out. Replacing "Accept/Decline" with a preselected "Accept and continue (recommended)" plus "Other options" alone nearly doubled first-screen acceptance (11.3% → 20.7%). Less-educated subjects were more susceptible to mild patterns. — [SSRN/OAG copy](https://oag.ca.gov/sites/all/files/agweb/pdfs/privacy/shining-a-light-on-dark-patterns.pdf); [SSRN](https://papers.ssrn.com/abstract=3431205)
- Same paper, **Study 2 (N=3,777, Dynata 2020, 5 content × 4 form conditions):** content — control 14.8%, hidden information 30.1%, social proof 22.1%, confirmshaming 19.6%, scarcity/countdown 14.3% (n.s., p=.78); form — control 16.7%, "recommended" label 18.1% (n.s.), **preselected default 20.1% (p=.045)**, obstruction 23.6% (p<.001); trick question raised acceptance from 19.2% to 33.4%. — [Journal of Legal Analysis](https://academic.oup.com/jla/article/13/1/43/6180579)
- **Jachimowicz, Duncan, Weber & Johnson (2019), Behavioural Public Policy 3(2):159–186.** Meta-analysis of 58 default studies (pooled N=73,675): **d = 0.68, 95% CI [0.53, 0.83]**; large heterogeneity (some null/negative); defaults are **more effective in consumer domains** and when perceived as endorsement or endowment. — [IDEAS](https://ideas.repec.org/a/cup/bpubpo/v3y2019i02p159-186_00.html); [Columbia summary](https://business.columbia.edu/press-release/cbs-press-releases/defaults-are-not-same-default)
- **Johnson, Bellman & Lohse (2002), Marketing Letters 13(1):5–15.** Online experiments (US): opt-in framing gave **48.2%** participation vs **96.3%** under opt-out (N=134); framing and defaults have additive effects. — [Columbia PDF](https://business.columbia.edu/sites/default/files-efs/imce-uploads/CDS/defaults_framing_and_privacy.pdf)
- **Mathur et al. (2019), "Dark Patterns at Scale", Proc. ACM HCI (CSCW).** Crawl of ~53K product pages on ~11K shopping sites: **1,818** dark-pattern instances, 15 types in 7 categories; **183** sites with outright deceptive practices (e.g., countdown timers resetting on reload, fake low-stock messages); 22 third-party vendors selling dark patterns as turnkey products. — [arXiv 1907.07032](https://arxiv.org/abs/1907.07032v2); [UChicago news](https://news.uchicago.edu/story/dirty-tricks-online-shopping-designed-make-you-spend-more)
- **European Commission (2022), Behavioural study on unfair commercial practices in the digital environment (DOI 10.2838/859030).** Mystery shopping found **97%** of the most popular EU websites/apps used at least one dark pattern; most frequent: hidden information/false hierarchy, preselection, nagging, difficult cancellation, forced registration. — [Digital Policy Alert](https://digitalpolicyalert.org/event/4904-published-ec-study-on-dark-patterns); [deceptive.design summary](https://deceptive.design/articles/behavioural-study-on-unfair-commercial-practices-in-the-digital-environment-dark-patterns-and-manipulative-personalisation)
- **UK CMA (2022) OCA evidence review** catalogs harms from defaults, drip pricing, scarcity/popularity claims. — [gov.uk](https://www.gov.uk/government/publications/online-choice-architecture-how-digital-design-can-harm-competition-and-consumers/evidence-review-of-online-choice-architecture-and-consumer-and-competition-harm)

### Inferences
- For TwinStore's "pre-ticked protection plan": real data predict substantially higher attach rate with pre-ticking (order of +3 to +15 percentage points depending on context; d≈0.68 in meta-analysis) and little sensitivity to the plan's price within a small range. A validation could check that simulated attach rates rise under pre-ticking and that satisfaction/NPS falls mainly under aggressive variants.

### Gaps
- The EU 2022 study's own consumer experiments (effect sizes) were not retrieved.
- The OECD "Dark commercial patterns" report (2022) was not retrieved in this pass.
- No real-store field RCT of pre-ticked add-ons in e-commerce checkout found (Luguri is a realistic panel experiment, not a live store).

## Forced account creation vs guest checkout; checkout length; one-click "buy now"

### Takeaway
Forced registration and long checkouts are among the top stated abandonment reasons; the famous "$300 million button" anecdote reports +45% purchasers after removing mandatory registration, and the best academic evidence on friction removal (one-click buying) shows large spend increases. Evidence specifically comparing one-page vs multi-step checkout is vendor-grade only.

### Cited Findings
- **Baymard Institute abandonment survey (US):** 18% of checkout abandoners left because the "site wanted me to create an account"; 17% because the checkout process was too long/complicated; 17% due to errors/crashes; 19% didn't trust the site with card details; 10% card declined. Baymard estimates the average large e-commerce site could gain **35.26%** conversion by fixing checkout usability issues. — [Baymard](https://baymard.com/lists/cart-abandonment-rate)
- **Spool (2009), "The $300 Million Button" (UIE, consultant case; D):** a major (unnamed) US retailer replaced the Register button with "Continue" and a note that registration was not needed; customers purchasing **+45%**, **+$15M** in the first month, **~$300M** in the first year. No methodology or controls published. — [UIE archive](https://archive.uie.com/brainsparks/2015/10/21/uie-article-the-300-million-button); [CMSWire](https://www.cmswire.com/cms/web-content/web-design-the-300-million-button-003809.php)
- **Elastic Path (2010) A/B test, Official Vancouver 2010 Olympic Store (D):** single-page checkout outperformed the out-of-the-box multi-step checkout by **21.8%**, 50/50 split, stopped after 606 transactions. Baymard cautions that such tests typically compare an unoptimized multi-step control against an optimized one-page design. — [Elastic Path](https://www.elasticpath.com/blog/single-vs-two-page-checkout); [Baymard on one-page checkout](https://baymard.com/blog/one-page-checkout)
- **Unal & Park (2023), "Fewer Clicks, More Purchases", Management Science.** Large Asian online retailer that launched one-click checkout in 2017; 977 customers who adopted it; Jan 2016–Aug 2018 clickstream; before/after comparison; an MSI working paper on (apparently) the same setting uses clickstream data and generalized random forests. Over 15 months after adoption: spending **+28.5%**, purchase frequency **+43%**, items **+36%**, site visits **+7%**, pages viewed **+9.3%**, time per visit **+7.8%**. Caveat: adopters self-select. — [Cornell Chronicle](https://news.cornell.edu/node/325992); [MSI working paper](https://www.msi.org/wp-content/uploads/2021/01/MSI_Report_20-144.pdf)

### Inferences
- Direction for TwinStore: forced account → lower conversion and higher abandonment at the account step; one-click "buy now" → higher conversion and fewer steps. Magnitudes from real data range widely (+21.8% to +45%) and are vendor-grade, so magnitude agreement should be framed loosely.

### Gaps
- No peer-reviewed RCT of guest checkout vs forced registration found. No peer-reviewed RCT of one-page vs multi-step checkout found.

## Payment options: cards, PayPal, Apple Pay, BNPL, bank transfer, cash on delivery

### Takeaway
BNPL has credible academic evidence of raising merchant sales (~20%) and consumer spending; wallet (Apple Pay/Link) effects come from processor A/B tests (vendor). Only ~9% of abandoners cite too few payment methods. Cash on delivery is dominant in some markets but lacks causal conversion evidence.

### Cited Findings
- **Berg, Burg, Keil & Puri, "The Economics of 'Buy Now, Pay Later': A Merchant's Perspective", Journal of Financial Economics (2025; NBER WP 33152, 2024).** BNPL increases merchant **sales by 20%**, driven by low-creditworthiness customers and products where market power is larger; benefits significantly exceed costs for the merchant (mechanism: subsidized loan enables price discrimination). — [NBER WP 33152](https://nber.org/system/files/working_papers/w33152/w33152.pdf); [ISB summary](https://www.isb.edu/faculty-and-research/research-directory/the-economics-of-buy-now-pay-later-a-merchant-s-perspective/)
- **Di Maggio, Katz & Williams (2022), NBER WP 30508.** US bank/card transaction data on ~10M consumers (BNPL users ~400K): BNPL access raises total spending and the retail share of spending ("liquidity flypaper"), including for non-liquidity-constrained users; press coverage cites ~+$60/week persistent increase. — [NBER](https://www.nber.org/papers/w30508); [HBS Working Knowledge](https://www.library.hbs.edu/working-knowledge/buy-now-pay-later-how-retails-hot-feature-hurts-lower-income-shoppers)
- **Stripe (2024 Sessions talk; vendor A/B on aggregated merchant data; D):** adding Apple Pay produced a statistically significant **~10% conversion uplift**; offering Link gave **+14%** returning-user conversion; wallet checkouts ~3× faster median. — [Stripe Sessions 2024](https://stripe.com/sessions/2024/a-look-under-stripes-hood-using-data-to-demystify-payments)
- Baymard: **9%** of checkout abandoners cite "not enough payment methods"; 10% "credit card declined". — [Baymard](https://baymard.com/lists/cart-abandonment-rate)
- Cash on delivery: a Sri Lankan survey study reports COD accounts for **>60%** of e-commerce transactions there; an Indian survey (N=387) finds COD adoption driven by perceived security/trust. Vendor blogs claim 15–35% conversion uplift from COD with 2–5× higher refusal rates, without disclosed methods. — [SLIIT repository](https://rda.sliit.lk/handle/123456789/2414); [Inderscience (Sharma et al.)](https://inderscience.com/filter.php?aid=134118); [Sendcloud (vendor)](https://www.sendcloud.com/blog/cash-on-delivery-shipping/)

### Inferences
- TwinStore's payment-method lever should show modest positive effects of adding wallets/BNPL (single-digit to ~20% relative), concentrated in shoppers who would otherwise lack a preferred method; COD effects should be market-dependent (strong in South/Southeast Asia and the Middle East, weak in card-dominated markets).

### Gaps
- No peer-reviewed field RCT on adding PayPal, bank transfer or COD to a checkout was found. The setting/design details of Berg et al. (randomization vs observational) were not verified in this pass.

## Page load time / site speed

### Takeaway
Faster pages are consistently associated with higher conversion: a 0.1 s mobile speed improvement was associated with +8.4% retail conversion and +9.2% order value (observational, 37 brands), Akamai reported −7% conversion per +100 ms, and large search-engine RCTs showed revenue/user −4.3% from +1.5 s latency. Most retail numbers are correlational industry studies, not RCTs.

### Cited Findings
- **Deloitte Digital & 55 for Google, "Milliseconds Make Millions" (2020).** 37 European/US brand sites, >30M sessions over 4 weeks (observational). A **0.1 s** improvement across four speed metrics was associated with retail conversion **+8.4%** and average order value **+9.2%**; PLP→PDP progression +3.2%, PDP→add-to-basket **+9.1%**. Every page in the journey had to improve. — [web.dev case study](https://web.dev/case-studies/milliseconds-make-millions); [Deloitte PDF](https://www2.deloitte.com/content/dam/Deloitte/ie/Documents/Consulting/Milliseconds_Make_Millions_report.pdf)
- **Akamai/SOASTA "State of Online Retail Performance" (Spring 2017).** ~10B visits to top retailers (observational): a **100 ms delay** associated with conversion **−7%**; a **2 s delay** with bounce **+103%**. A later Akamai dataset reported a smaller −2.4% desktop conversion drop for pages 100 ms slower. — [Akamai press release](https://www.akamai.com/fr/newsroom/press-release/akamai-releases-spring-2017-state-of-online-retail-performance-report); [MediaPost](https://www.mediapost.com/publications/article/306009/three-seconds-and-youre-out.html)
- **Google "mobile page speed new industry benchmarks" (2017):** 53% of mobile visits abandoned if load > 3 s; going from 1 s to 7 s load raises bounce probability **+113%** (neural-net model). — [Think with Google](https://thinkwithgoogle.com/intl/en-gb/marketing-strategies/app-and-mobile/mobile-page-speed-new-industry-benchmarks)
- **Bing/Google latency RCTs (Schurman & Brutlag, Velocity 2009), as cited by Arapakis et al. (CHIIR 2021):** Bing added **1.5 s** latency → queries/user −1.8%, **revenue/user −4.3%**, satisfaction −3.8%; Google **400 ms** delay → searches/user −0.59%, with lasting effects. Amazon reportedly found **100 ms → −1% revenue** (anecdotal, unpublished). — [Arapakis et al., arXiv 2101.09086](https://arxiv.org/pdf/2101.09086)
- **Kohavi, Tang & Xu (2020), *Trustworthy Online Controlled Experiments*, ch. "Speed Matters":** in 2017 each **100 ms** improvement at Bing was worth **$18M** incremental annual revenue; latency recommended as a guardrail metric based on replicated slowdown experiments. — [Cambridge Core](https://www.cambridge.org/core/books/trustworthy-online-controlled-experiments/speed-matters/35D34F276D4AF1AEE4B98D3E09B9E168)

### Inferences
- Real-shopper response to latency is roughly monotone and approximately linear at small delays (≈1–7% conversion per 100 ms in retail observational data; ≈1% revenue per 100–400 ms in RCTs). Simulated agents that perceive latency only as a cost in "time" but not in abandonment may under-react.

### Gaps
- No peer-reviewed randomized slowdown experiment on an e-commerce retailer with published conversion effects was found (Bing/Google are search engines; Amazon/Walmart numbers are unpublished talks).

## Scarcity / urgency messages ("only 3 left", countdown timers)

### Takeaway
Meta-analytic evidence shows a small-to-moderate positive effect of scarcity on purchase *intentions* (δ = 0.31) but it rests almost entirely on hypothetical/lab studies (only 6 field effect sizes). In a large US online experiment a countdown-timer scarcity cue had no effect; field evidence on low-stock messages is mixed and context-dependent.

### Cited Findings
- **Barton, Zlatevska & Oppewal (2022), Journal of Retailing 98(4):741–758.** Meta-analysis of 416 effect sizes from 131 studies. Scarcity → purchase intentions **δ = 0.31 (95% CI 0.25–0.37; k=193; N=22,655)**; also ↑ desirability (0.25), perceived popularity (0.71), quality (0.47), value (0.37), WTP (0.47). By type: supply-based 0.39, **time-based 0.34**, demand-based 0.28. Demand-based works best for utilitarian products, supply-based for experiences, time-based for high-involvement products. **Only 24 effect sizes measured actual behavior and only 6 came from field studies; 384 were hypothetical.** — [Bond University open-access PDF](https://pure.bond.edu.au/ws/portalfiles/portal/182976505/Scarcity_tactics_in_marketing.pdf)
- **Luguri & Strahilevitz (2021) Study 2:** a scarcity/countdown-timer condition produced **14.3% vs 14.8%** control acceptance (n.s., p=.78). — [Journal of Legal Analysis](https://academic.oup.com/jla/article/13/1/43/6180579)
- **Li, Tsekouras & Cheng (ICIS 2018)** randomized field experiment at an online retailer: scarcity information significantly raised purchase likelihood and outperformed popularity info and the combination. — [AIS eLibrary](https://aisel.aisnet.org/icis2018/economics/Presentations/12)
- **Park, Rabinovich, Tang & Yin (ASU working paper; observational retailer sales data):** outside special sales events, "only X left" notices *reduced* daily purchases, especially for items usually bought in larger quantities. — [ASU W. P. Carey Knowledge](https://news.wpcarey.asu.edu/20200327-%E2%80%98only-2-left-stock-order-now%E2%80%99-does-it-work)
- Instacart low-stock warnings (UCLA research, secondary coverage only): customers warned an item was low spent ~5.8% more over six months; per-order lift small. — [UCLA Anderson Review](https://anderson-review.ucla.edu/inventory-scarcity/) (primary paper not retrieved)
- Regulation: CMA treats urgency cues such as countdown timers as unlawful unless they reflect genuine time limits; Mathur et al. found fake timers resetting on reload. — [Ashurst](https://www.ashurst.com/en/insights/mind-the-nudge-the-dmccs-crackdown-on-manipulative-online-design/); [UChicago](https://news.uchicago.edu/story/dirty-tricks-online-shopping-designed-make-you-spend-more)

### Inferences
- Real-world benchmark for TwinStore's urgency lever is "small positive or null on conversion, possibly negative on satisfaction/trust". A simulator showing large conversion jumps from countdown timers would be *inconsistent* with the best behavioral evidence.

### Gaps
- No published peer-reviewed Booking.com/Etsy/Alibaba field RCT with effect sizes for scarcity or urgency banners was found.

## Social proof ("128 bought this week", popularity)

### Takeaway
Popularity information shifts real choices, more so for niche products; positive observational-learning cues raise sales while negative ones have little effect; in a large online panel, a social-proof message raised add-on acceptance from 14.8% to 22.1%.

### Cited Findings
- **Tucker & Zhang (2011), Management Science 57(5):828–842.** Field experiment on a US wedding-services vendor website: displaying popularity information benefited narrow-appeal (niche) vendors more than equally popular broad-appeal vendors ("long tail" effect). — [MIT DSpace](https://dspace.mit.edu/handle/1721.1/64921)
- **Chen, Wang & Xie (2011), JMR 48(2):238–254.** Natural experiment on Amazon (digital cameras; display of "% of customers who bought after viewing" added/removed): positive observational-learning info increased sales; negative OL had little/no effect; negative word of mouth more powerful than positive; OL and WOM reinforce each other. — [Binghamton news](https://discovere.binghamton.edu/features/shop-4198.html); [SocialMediaToday](https://www.socialmediatoday.com/content/new-research-impact-word-mouth-and-observational-learning-buying-decisions)
- **Luguri & Strahilevitz (2021) Study 2:** social-proof message condition **22.1% vs 14.8%** acceptance. — [Journal of Legal Analysis](https://academic.oup.com/jla/article/13/1/43/6180579)
- Li, Tsekouras & Cheng (ICIS 2018): popularity cues were less effective than scarcity cues in a randomized field experiment. — [AIS eLibrary](https://aisel.aisnet.org/icis2018/economics/Presentations/12)

### Gaps
- Effect sizes for Tucker & Zhang and Chen et al. (elasticities) were not retrieved.

## Star ratings and review counts

### Takeaway
Displaying reviews strongly raises conversion relative to no reviews (the first few reviews matter most); ratings causally move revenue (+5–9% per Yelp star), purchase likelihood peaks at 4.2–4.5 stars rather than 5, and negative reviews weigh more than positive.

### Cited Findings
- **Spiegel Research Center (Northwestern, with PowerReviews), "How Online Reviews Influence Sales" (2017).** >100,000 SKUs and 15M page views from two CPG retailers and one high-end gift retailer over a year (observational, US): purchase likelihood for a product with **5 reviews is 270% greater** than with 0 reviews; up to **380%** for higher-priced items; diminishing returns after the first reviews. — [Spiegel whitepaper (PDF)](https://www.xait.com/hubfs/Spiegel_Online-Review_eBook_Jun2017_FINAL.pdf); [MarketingProfs](https://www.marketingprofs.com/charts/2017/32629/the-measurable-impact-that-reviews-and-ratings-have-on-sales)
- Spiegel/PowerReviews star-rating analysis: across 40+ categories, purchase likelihood **peaks at 4.2–4.5 stars** and declines toward 5.0; little effect of stars between 1 and ~3. (Secondary sources often misquote this as 4.0–4.7.) — [Spiegel: Star ratings and review content](https://spiegel.medill.northwestern.edu/star-ratings-and-review-content/); [Spiegel whitepaper 2021](https://spiegel.medill.northwestern.edu/wp-content/uploads/sites/2/2021/04/Online-Reviews-Whitepaper.pdf)
- **Luca (HBS working paper 2011; "Reviews, Reputation, and Revenue: The Case of Yelp.com").** All Seattle restaurants 2003–2009, regression discontinuity on Yelp's rounding: **+1 star → revenue +5–9%** for independent restaurants; no effect for chains. — [Harvard Magazine](https://www.harvardmagazine.com/index%2Ephp/2011/10/hbs-study-finds-positive-yelp-reviews-lead-to-increased-business)
- **Anderson & Magruder (2012), Economic Journal** (authorship per standard citation; snippet confirms the finding): a **half-star** higher Yelp rating made restaurants **19 percentage points** more likely to sell out at peak times (regression-discontinuity design); the snippet retrieved does not itself name the authors/year. — [UC Berkeley faculty page](https://vcresearch.berkeley.edu/faculty/michael-l-anderson)
- **Chevalier & Mayzlin (2006), JMR 43(3):345–354.** Amazon vs Barnes & Noble (US) differences-in-differences on sales ranks: improved reviews raise a book's relative sales; for most samples **one-star reviews have larger impact than five-star**; review length matters (people read text). — [NBER WP 10148](https://www.nber.org/papers/w10148)

### Inferences
- For TwinStore's "show ratings & review counts" lever, real data predict a clear positive effect on add-to-cart/conversion, concentrated on products with few reviews vs none, and a non-monotone star effect (very high 4.9–5.0 ratings slightly less persuasive than 4.2–4.5).

### Gaps
- Spiegel results are observational (no randomization of review display); no published retailer RCT that hides/shows reviews was retrieved.

## Ranking position, default sort order, sponsored product slots, recommendations, ad placements

### Takeaway
Randomized ranking at Expedia shows position causally drives what people click/search but not purchase conditional on search; sponsored ads at eBay had near-zero incremental value for brand keywords; a large e-commerce holdout found sponsored search cannibalizes organic sales and reduces total platform sales (though profitable to the platform); recommendations raise conversion ~6%.

### Cited Findings
- **Ursu (2018), "The Power of Rankings", Marketing Science 37(4):530–552.** Expedia hotel search; ~1/3 of searches used a **randomly generated ranking**. Rankings causally affect search (clicks) but, conditional on search, **do not affect purchase**; average position effect estimated at **$2.64** (dissertation abstract), lower than non-experimental estimates. — [Ursu working paper](https://wwws.law.northwestern.edu/research-faculty/clbe/events/internet/documents/ursu-ranking_v2.pdf); [UChicago dissertation](https://knowledge.uchicago.edu/record/1646/files/Ursu_uchicago_0330D_13283.pdf)
- **Blake, Nosko & Tadelis (2015), Econometrica 83(1):155–174.** Large-scale field experiments at eBay (US): halting **brand-keyword** paid search ads → nearly all traffic recaptured by organic search (no measurable short-term benefit); for non-brand keywords, positive effects only for new/infrequent users; frequent users (most spend) unaffected → **average ROI negative**; experimental returns are a fraction of observational estimates. — [NBER WP 20171](https://www.nber.org/papers/w20171); [Berkeley PDF](https://faculty.haas.berkeley.edu/stadelis/BNT_ECMA_rev.pdf)
- **Moshary, "Sponsored Search in Equilibrium" (2021 WP) / Management Science 2025 ("Does Sponsored Search Advertising Augment Organic Search?").** Anonymous e-commerce platform field experiment blocking all sponsored listings for **3%** of traffic: users who see ads buy more sponsored and **less organic**; net effect **reduces total platform sales**; still profitable to the platform because ad revenue exceeds lost commissions; natural experiment suggests ads push prices up. — [Berkeley SICS 2021 paper](https://sics.haas.berkeley.edu/pdf_2021/paper_m.pdf); [Management Science DOI 10.1287/mnsc.2024.04792](https://pubsonline.informs.org/doi/references/10.1287/mnsc.2024.04792)
- **Sahni & Nair (2020), Marketing Science, "Sponsorship Disclosure and Consumer Deception".** Randomized experiments on >200,000 users of a mobile restaurant-search platform varying native-ad format and disclosure: native ads benefit advertisers; **no evidence of deception** under standard disclosure; gains come from users seeing the ad and later choosing the advertiser's organic listing. — [FTC-hosted paper](https://www.ftc.gov/system/files/documents/public_events/966823/sahninair_native_advertisingsponsorshipdisclosureandconsumerdeception.pdf); [INFORMS release](https://www.informs.org/News-Room/INFORMS-Releases/News-Releases/Researchers-Find-that-Native-Advertising-Builds-Credibility-Not-Perceived-as-Tricking-Visitors)
- **Dinerstein, Einav, Levin & Sundaresan (2018), AER 108(7):1820–59.** eBay browsing data; structural search model explains most effects of a major redesign of eBay's product search; retail margins ~10%; narrowing choice sets can be pro-competitive; a follow-up eBay A/B test showed design is harder for differentiated products. — [AER](https://www.aeaweb.org/doi/10.1257/aer.20171218); [NBER WP 20415](https://www.nber.org/papers/w20415.pdf)
- **Lee & Hosanagar (WWW 2016; ISR 2019).** Randomized field experiment at a major North American retailer (184,375 users in WWW paper): recommender systems raised baseline **conversion +5.9%**; ISR paper (82,290 products, ~1.14M users): purchase-based collaborative filters had larger effects than view-based; individual diversity can rise while aggregate sales diversity falls. — [WWW 2016 PDF](https://archives.iw3c2.org/www2016/WWW2016-Proceedings/proceedings/p85.pdf); [ISR summary](https://d3.harvard.edu/?p=2816)

### Inferences
- Ranking/default sort in TwinStore should mainly change *what is viewed and clicked*, with smaller changes in conversion; sponsored slots should shift share toward sponsored items with flat-to-negative total revenue per session; recommendations should give single-digit-percent conversion gains.

### Gaps
- No academic evidence found on hero-banner or cart-upsell ad placements; retail-media "incrementality" numbers outside Moshary are vendor-reported.

## Search quality, products per page, grid density, quick add-to-cart

### Takeaway
Evidence is thin. Etsy's infinite-scroll test reduced search engagement (fewer clicks and favorites from search) without lowering overall purchases; choice-overload meta-analyses find near-zero average effect of assortment size with strong moderators. No credible effect sizes were found for quick-add buttons, grid columns or zero-result handling.

### Cited Findings
- **Etsy infinite-scroll A/B test (McKinley, "Design for Continuous Experimentation"; D):** infinite scroll on search produced fewer clicks on results and fewer favorites; users "stopped using search" to find items but overall purchases did not fall. Secondary claims of −22% conversion are unverified. — [McKinley](https://mcfunley.com/continuous-experimentation/); [danwin.com summary](https://danwin.com/2013/01/infinite-scroll-fail-etsy/)
- **Scheibehenne, Greifeneder & Todd (2010)** meta-analysis (63 conditions, 50 experiments): mean choice-overload effect ≈ 0; **Chernev, Böckenholt & Goodman (2015, J. Consumer Psychology)**: effect significant once moderators (task difficulty, set complexity, preference uncertainty, effort-minimizing goal) are included. — [Scheibehenne et al. reply PDF](https://abcwest.cogs.indiana.edu/pmwiki/pdf/scheibehenne.reply.2011.pdf); [Kellogg record](https://www.kellogg.northwestern.edu/faculty/research/detail/2015/when-product-assortment-leads-to-choice-overload-a-conceptual)
- Dinerstein et al. (2018): eBay's search redesign changed prices and choices (see above). — [AER](https://www.aeaweb.org/doi/10.1257/aer.20171218)

### Gaps
- No peer-reviewed or regulator evidence found on: search quality (smart/exact/off) or zero-results rates vs conversion; products per page or grid columns; quick add-to-cart on product cards. Only vendor claims (e.g., search-vendor marketing) exist; these were not collected because they lack methodology.

## Welcome popups and cookie-consent banners

### Takeaway
Consent-banner design causally and strongly changes consent rates (e.g., removing "reject" from the first layer +22–23 pp), and GDPR consent requirements reduced recorded EU e-commerce pageviews and revenue by ~12%. For promotional popups, the best evidence is Google's internal test showing 69% abandonment at a full-page interstitial; ecommerce newsletter/coupon popup evidence is vendor-only.

### Cited Findings
- **Utz, Degeling, Fahl, Schaub & Holz (2019), ACM CCS, "(Un)informed Consent".** Three field experiments with **>80,000** unique users on a German website: notices in the **lower-left** get more interaction; binary accept/decline yields more acceptance than per-category/per-vendor choices; nudging (preselection, highlighted buttons) has a large effect on choices. — [arXiv 1909.02638](https://arxiv.org/abs/1909.02638v1); [RUB CASA](https://www.casa.rub.de/forschung/publikationen/detail/uninformed-consent-studying-gdpr-consent-notices-in-the-field)
- **Nouwens, Liccardi, Veale, Karger & Kagal (2020), CHI.** Scrape of popular UK websites using consent-management platforms: only **11.8%** met minimal GDPR requirements; field experiment (40 participants): removing the opt-out button from the first page **+22–23 pp** consent; granular controls on first page **−8 to −20 pp**; banner vs barrier no effect. — [arXiv 2001.02479](https://arxiv.org/abs/2001.02479v1); [MIT PDF](https://people.csail.mit.edu/ilaria/papers/Midas-MITCHI2020.pdf)
- **Goldberg, Johnson & Shriver (2024), AEJ: Economic Policy, "Regulating Privacy Online".** 1,084 firms on Adobe Analytics, DiD: after GDPR enforcement, recorded EU pageviews and recorded website revenue **−12%** each (earlier draft: ~−10%; e-commerce revenue −8.3%). Proposed channels: higher legal risk for email/display marketing, and consent notices changing browsing behavior; part of the drop may be measurement (fewer users recorded). — [AEA](https://www.aeaweb.org/doi/10.1257/pol.20210309); [WARC](https://www.warc.com/newsandopinion/news/gdpr_hits_online_visits_and_revenues_in_europe/42412)
- **Google+ mobile interstitial test (2014, published 2015; internal, D):** a full-page "get the app" interstitial — **69%** of visits abandoned the page; ~9% clicked "Get the app"; replacing it with a smaller banner gave **+17% one-day active users**, with app installs only −2%. — [TechCrunch](https://techcrunch.com/?p=1187579); [MarTech](https://martech.org/google-data-show-users-hate-app-promotion-interstitials)
- Vendor popup tests (D): simplified signup popup on 5 news sites raised signup rate 0.9% → 1.45% (+61%, before/after); a discount signup popup vs redirect exit popup +2.9% e-commerce conversion and +4% AOV; a 10% vs 15% discount popup test showed higher signup with 10% but more sales with 15%. — [BlueLena](https://bluelena.io/2023/10/10/how-a-b-testing-a-simplified-email-signup-popup-boosted-conversions-on-newspack-sites/); [Blend Commerce](https://blendcommerce.com/blogs/ab-tests-shopify/4-increase-in-average-order-value); [OptiMonk](https://www.optimonk.com/templates/use-cases/offer-a-b-test)

### Inferences
- TwinStore's cookie-banner lever should mainly add steps/time and reduce ease; direct conversion effects in real data are small and mostly about tracking measurement. A welcome popup should increase early exits on mobile and reduce ease; coupon popups may raise conversion among those who stay.

### Gaps
- No peer-reviewed RCT of e-commerce welcome/newsletter popups on purchase conversion was found.

## Abandoned-cart reminders, discount emails and promo codes (public vs popup-only; visible coupon field)

### Takeaway
Randomized evidence shows targeted discount emails raise spending far beyond redemptions (+37%, ~90% of the lift from non-redeemers) and retargeting brings back ~5% more cart abandoners; rigorous cart-reminder RCTs with vs without discount are scarce. Removing a visible coupon field yields small average gains (~2.5%) in vendor test aggregates.

### Cited Findings
- **Sahni, Zou & Chintagunta (2017), Management Science 63(8):2688–2705, "Do Targeted Discount Offers Serve as Advertising? Evidence from 70 Field Experiments".** Large online ticket-resale platform (country not stated in summary), randomized email offers (15–30 day validity): recipients spent **+37%** during the promotion period; only **~10%** of the increase came from redeemed offers; **+25%** carryover the week after expiry; example: redemption cost $1,178 vs $185,972 incremental spending. — [Stanford GSB](https://www.gsb.stanford.edu/insights/navdeep-sahni-email-promotions-prospective-customers-really-do-work); [INFORMS](https://pubsonline.informs.org/doi/references/10.1287/mnsc.2016.2450)
- **Sahni, Narayanan & Kalyanam (2019), JMR 56(3):401–418.** Randomized retargeting experiment with >230,000 visitors to BuildDirect (Canada-based home-improvement e-tailer): retargeting made **14.6%** more early-stage (product-page) visitors return within 4 weeks; **5.4%** for late-stage cart abandoners; effect decays quickly (a third of week-1 effect on day 1). — [SCU](https://www.scu.edu/business/marketing/research/selected-publications/an-experimental-investigation-of-the-effects-of-retargeted-advertising-the-role-of-frequency-and-timing.html); [MSI Report 21-133](https://www.msi.org/wp-content/uploads/2021/09/MSI_Report_21-133-1.pdf)
- Ashish Kumar (HKU seminar abstract, "Causes and Consequences of Online Shopping Cart Abandonment"): reminder emails lowered abandonment by up to ~5% (design details not stated). — [HKU Business School](https://www.hkubs.hku.hk/sc/seminar-category/marketing-sc/page/2)
- Vendor (D): Exponea/BDsklep tested six abandoned-cart email variants; the best raised purchase completion **+25%**; Yespo found discount-plus-timer cart emails got 35% vs 19% clicks. — [Exponea](https://exponea.com/success-stories/bdsklep-pl/); [Yespo](https://yespo.io/blog/abandoned-cart-16-more-clicks)
- Visible promo-code field (D): Bionic Gloves removed gift-certificate/coupon fields → revenue **+24%**, income per visitor +17% (≈1,400 visitors, 48 days); GoodUI aggregate of 4–5 coupon-field tests gives a median ≈ **+2.5%** sales effect; a 2026 test (~41K visitors) found no significant difference. — [GoodUI Pattern #1](https://goodui.org/patterns/1/); [Curatti](https://curatti.com/ab-testing-results/)
- Shehu et al. (2020): coupons worth the shipping fee raised order volume +13% and were profitable, unlike free shipping. — [CBS manuscript](https://research-api.cbs.dk/ws/portalfiles/portal/67886147/edlira_shehu_et_al_free_shipping_promotions_and_product_returns_acceptedversion.pdf)

### Gaps
- No peer-reviewed RCT comparing cart-reminder emails **with vs without discount** on completed orders was found (an Erasmus thesis notes this gap). — [EUR thesis](https://thesis.eur.nl/pub/70103/Final-Thesis-Jaime-Zun-771)
- No academic study isolating "public vs popup-only coupon codes" was found.

## Return policy leniency (free 30-day vs paid vs hidden)

### Takeaway
A meta-analysis finds lenient return policies raise purchases more than they raise returns (monetary leniency most potent), and longitudinal retailer data show charging for returns cuts subsequent spending by 75–100%. 13% of abandoners cite an unsatisfactory returns policy.

### Cited Findings
- **Janakiraman, Syrdal & Freling (2016), Journal of Retailing, "The Effect of Return Policy Leniency on Consumer Purchase and Return Decisions: A Meta-analytic Review"** (21–22 studies). Leniency (time, money, effort, scope, exchange) increases purchases; it also increases returns, but less; **monetary leniency** most likely to boost purchases; longer time limits reduce returns. — [UT Dallas news](https://news.utdallas.edu/?p=11491); [AMA](https://ama.org/2017/09/20/lenient-return-policies-can-increase-sales)
- **Bower & Maxham (2012), Journal of Marketing 76(5), DOI 10.1509/jm.10.0419.** Two longitudinal field studies of online-retailer customer data over ~4 years (49 months per press release): customers who paid for return shipping reduced post-return spending by **75–100%** within two years; customers with free returns had post-return spending **158–457%** of pre-return spending (press release gives +58% to +357% purchases vs −74% to −100%). — [ScienceDaily](https://sciencedaily.com/releases/2012/10/121009101344.htm); [Newswise](https://www.newswise.com/articles/study-finds-free-product-returns-have-major-impact-on-future-sales)
- Baymard: **13%** of abandoners left because the returns policy wasn't satisfactory. — [Baymard](https://baymard.com/lists/cart-abandonment-rate)

### Gaps
- No RCT of *hidden* vs visible return policy was found; Bower & Maxham is observational (customers not randomized to fees).

## Trust badges / assurance seals

### Takeaway
A randomized field experiment found that displaying a third-party assurance seal raised purchase conversion; follow-up data from 493 retailers suggests diminishing or negative returns beyond two seals.

### Cited Findings
- **Özpolat, Gao, Jank & Viswanathan (2013), Information Systems Research 24(4):1100–1111.** 9,098 shopping sessions at an online retailer (an online pharmaceutical company), randomized display of a third-party seal (half saw it): seal presence significantly increased the odds of purchase. — [INFORMS](https://pubsonline.informs.org/doi/fpi/10.1287/isre.2013.0489); [URI repository](https://digitalcommons.uri.edu/cba_facpubs/326); [USF note on design](https://www.usf.edu/business/news/spotlights/faculty-jank-wolfgang.aspx)
- **Özpolat & Jank (2015), Decision Support Systems:** 288,169 transactions across 493 retailers; seals partially substitute for shopper experience and seller volume; showing more than two seals can reduce purchase completion. — [datalearner record](https://www.datalearner.com/academic/journal-papers/0167-9236/volumes-and-issues/235/paper-detail/4125)
- Baymard: 19% of abandoners "didn't trust the site with my credit card information". — [Baymard](https://baymard.com/lists/cart-abandonment-rate)

### Gaps
- Exact percentage lift in Özpolat et al. (2013) not retrieved.

## Large-text accessibility mode

### Takeaway
No causal evidence was found on large-text modes and conversion; the best available data are UK surveys showing most disabled shoppers abandon hard-to-use sites.

### Cited Findings
- **Click-Away Pound Survey 2019 (UK, published Feb 2020; survey, C):** **69%** of disabled online shoppers click away from sites with access barriers; represents 4.9M shoppers and **£17.1bn** spend (~10% of UK online spend; up from £11.75bn in 2016); 83% limit shopping to sites they know are accessible; 86% have paid more at an accessible site; only 8% contact the site owner. — [AbilityNet](https://abilitynet.org.uk/news-blogs/research-shows-businesses-lose-17-billion-ignoring-accessibility-needs); [Click-Away Pound press release](https://www.clickawaypound.com/downloads/CAP2019PR2.pdf)

### Gaps
- No experiment found that randomizes text size / accessibility mode and measures conversion, for either general or older/low-vision shoppers.
