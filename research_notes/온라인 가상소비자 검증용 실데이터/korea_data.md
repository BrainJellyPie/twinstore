# 한국 온라인 쇼핑 행동 실데이터 카탈로그 (TwinStore 온라인 가상소비자 검증용)

Scope: Korea-only sources (official statistics, government/consumer-agency surveys, public datasets, industry reports, academic work) usable to calibrate or validate TwinStore's simulated online shoppers. Research date: 2026-10-25. Every figure carries its year. Entries are numbered K01–K30 so the report writer can cross-reference them. "Verified" means the figure was read on the cited page. "Snippet-only" means the figure came from a search-engine summary and the page itself was not opened. Treat snippet-only figures as leads, not citations.

Abbreviations: 국가데이터처 = Statistics Korea's successor name (the former 통계청; recent releases use the new name). NIA = 한국지능정보사회진흥원. KCA = 한국소비자원. FTC = 공정거래위원회. BOK = 한국은행. MSIT = 과학기술정보통신부.

---

## Q1. 공식 통계 (Official statistics): 온라인쇼핑동향조사, 인터넷이용실태조사, 한국은행 전자지급, 기타 정부 실태조사

### Takeaway
Korea's official monthly statistics give a hard benchmark for **mobile share of transaction value: 78.1% (Aug 2026)**. Category mix and mall-type splits are also available, free and without registration. The BOK puts **daily simple-pay (간편지급) volume at ₩1.1053조 / 35.57M transactions (2025)**, with fintech "pays" (Naver/Kakao/Toss) holding 54.9%. MSIT/NIA surveys give participation, multihoming and digital-divide context. The 2025 shopping-specific age breakdowns were not retrievable in this session.

### Cited Findings

#### K01. 온라인쇼핑동향조사 (Online Shopping Trend Survey), monthly
- Publisher: 국가데이터처 경제통계국 서비스업동향과 (formerly 통계청). Monthly release, about 1 month after the reference month. The latest edition seen is **2026년 8월 온라인쇼핑 동향, released 2026-10-01** (44-page PDF, D26100007.pdf). — [KDI 경제정보센터 mirror of release](https://eiec.kdi.re.kr/policy/materialView.do?num=287670)
- Access: free, no registration. Press-release PDF from 국가데이터처/KDI EIEC. Time series on KOSIS (kosis.kr → 도소매·서비스 → 온라인쇼핑동향조사), e.g., the tables "온라인쇼핑몰 판매매체별/상품군별 거래액" and "취급상품범위별/상품군별 거래액". (The KOSIS table ID could not be verified because KOSIS redirected to SSO in this session; see Gaps.)
- Method: census-type survey of online shopping operators (business-reported transaction values). It is **not** a consumer or session survey, so it measures value (GMV), not visits.
- Aug 2026 figures (verified):
  - Total online shopping transaction value ₩24조 2,118억 (+7.3% YoY). Mobile ₩18조 9,021억 (+5.8%). **Mobile share 78.1%** (Aug 2025: 79.2%, −1.1%p). — [KDI EIEC](https://eiec.kdi.re.kr/policy/materialView.do?num=287670)
  - Category composition: 음식서비스 16.4%, 음·식료품 14.6%, 여행 및 교통서비스 13.5% (top 3). YoY: 의복 −4.4%, 음식료품 +9.8%, 음식서비스 +7.6%, 여행·교통 +8.7%. — [KDI EIEC](https://eiec.kdi.re.kr/policy/materialView.do?num=287670)
  - Mobile share by category (top 3): 음식서비스 99.1%, 이쿠폰서비스 92.3%, 아동·유아용품 84.4%. — [KDI EIEC](https://eiec.kdi.re.kr/policy/materialView.do?num=287670)
  - 취급상품범위별: 종합몰 ₩12조 8,655억 (+7.4%), 전문몰 ₩11조 3,463억 (+7.1%). 운영형태별: 온라인몰 ₩18조 7,577억 (+6.9%), 온·오프라인병행몰 ₩5조 4,541억 (+8.6%). — [KDI EIEC](https://eiec.kdi.re.kr/policy/materialView.do?num=287670)
- Adjacent months: July 2026 total ₩25조 954억, mobile share 78.0% (−0.6%p YoY) — [비건뉴스](https://www.vegannews.co.kr/news/article.html?no=385676). June 2026 mobile share 76.9% (−0.7%p) — [데일리안](https://www.dailian.co.kr/news/view/1673809/) (snippet-only).
- TwinStore metrics validated: **device mix (mobile share of purchase value)**, **product-category mix of purchases**, generalist vs specialist mall share. It does not validate conversion, sessions or AOV.

#### K02. 인터넷이용실태조사 (Survey on Internet Usage), annual, National Approved Statistics No. 120005
- Publisher: 과학기술정보통신부 · 한국지능정보사회진흥원(NIA). **2025 edition announced 2026-03-31.** Sample: 22,671 households and 50,750 household members aged 3+, nationwide household survey (interview mode not verified here). Internet use rate 95.0% (+0.5%p). 44.5% have used generative AI. — [korea.kr 보도자료](https://www.korea.kr/briefing/pressReleaseView.do?newsId=156751949&pWise=main&pWiseMain=L1); [뉴스서울](https://newsseoul.co.kr/news/view/1065588010791034)
- Snippet-only: 95.2% of users go online at least once a day; average 21.6 hours/week (2025). — [korea.kr](https://www.korea.kr/briefing/pressReleaseView.do?newsId=156751949&pWise=main&pWiseMain=L1)
- Snippet-only: the 2024 edition reported overseas direct purchase (해외직구) use rising from 20% (2023) to 34.3% (2024). — [KDI EIEC, 2024 인터넷이용실태조사 결과](https://eiec.kdi.re.kr/policy/materialView.do?num=264952)
- Older shopping-by-age benchmark (2021 edition, snippet-only): 인터넷쇼핑 이용률 73.7% overall; **60대 41.2% (+9.8%p YoY)**. — [뉴스토마토](https://newstomato.com/ReadNews.aspx?no=1028734)
- Indicator portal (e-나라지표 idx 1346): internet use rate 94.5% in July 2024. The page links the 2025 요약보고서 and 보도자료 (dated 2026-04-27). — [index.go.kr](https://www.index.go.kr/unity/potal/main/EachDtlPageDetail.do?idx_cd=1346)
- Public data file: **공공데이터포털 dataset 15086936, 「한국지능정보사회진흥원_인터넷이용실태조사 통계자료_20251231」**. XLSX plus codebook, annual updates, registered 2026-04-27. License KOGL Type 2 (attribution, no commercial use). Free download. The page states the topics include usage purpose (쇼핑, 금융 …), devices (smartphone/PC/tablet/smart TV) and main websites (shopping malls). The listed period metadata is inconsistent (Aug 2020–Aug 2023). — [data.go.kr 15086936](https://www.data.go.kr/data/15086936/fileData.do)
- TwinStore metrics validated: **shopping participation by age group/gender** (for panel age weights), device ownership and use, and online-purchase prevalence among 60대+.

#### K03. 한국은행 「2025년중 전자지급서비스 이용현황」 (Electronic Payment Services Usage, 2025)
- Publisher: 한국은행 금융결제국. Released **2026-03-20**. Attachments in HWP and PDF. Free. Semiannual and annual editions. Simple-pay and simple-remittance figures have been collected since 2016. — [BOK 보도자료](https://www.bok.or.kr/portal/bbs/B0000502/view.do?nttId=10097038&menuNo=201265)
- 2025 daily averages (verified on the BOK page):
  - **간편지급 (simple payment): 3,557만건, ₩1조 1,053억** (+14.9%, +14.6%)
  - 간편송금: 742만건, ₩9,785억 (+2.9%, +7.3%)
  - 전자지급결제대행(PG): 3,364만건, ₩1조 5,542억 (+11.8%, +9.2%)
  - 선불전자지급수단: 3,654만건, ₩1조 3,051억 (+8.0%, +11.0%)
  - — [BOK](https://www.bok.or.kr/portal/bbs/B0000502/view.do?nttId=10097038&menuNo=201265)
- Simple-pay share by provider type, 2025: **전자금융업자 (Naver Pay, Kakao Pay, Toss Pay, etc.) 54.9% (+4.4%p)**, 휴대폰제조사 (Samsung/Apple Pay) 23.7% (from 25.4%), 금융회사 (card companies, etc.) 21.5% (from 24.2%). Daily simple-pay amount history: ₩8,834억 (2023), ₩9,644억 (2024), ₩1조 1,053억 (2025). — [서울파이낸스](https://www.seoulfn.com/news/articleView.html?idxno=624139)
- Revision note: the March 2025 release reported 2024 simple pay as ₩9,594억/day (+9.6%) with 전자금융업자 at 50.2% — [뉴시스](https://www.newsis.com/view/NISX20250320_0003106215). The 2026 release uses ₩9,644억 for 2024. Cite the latest release and note the revision.
- 2025 H1: simple pay ₩1조 464억/day (+11.4%), the first time above ₩1조. — [한국경제](https://www.hankyung.com/article/202509294322i)
- TwinStore metric validated: **payment-method choice** (easy pay vs card). The figures cover both online and offline, and no online/offline split was reported (see Gaps).

#### K04. 부가통신사업 실태조사 2025 (Value-added Telecom Services Survey; includes e-commerce platforms)
- Publisher: 과학기술정보통신부. Results published in 2026. Consumer module: 2,500 adults aged 19–69 in 17 시·도. Reference period Oct–Dec 2025. — [한국시사경제](https://www.hksisaeconomy.com/news/article.html?no=1148464)
- **E-commerce platform use in the last 3 months 95.6%. Multihoming (2+ platforms) 83.9%**, the highest of all service types, averaging 3+ platforms. **E-commerce membership subscribers 75.9% (n=1,897).** Main memberships: 쿠팡 와우, 네이버플러스, 신세계 유니버스, 우주패스. Main platform-choice factors: "빠른 배송과 저렴한 가격". — [한국시사경제](https://www.hksisaeconomy.com/news/article.html?no=1148464)
- TwinStore metrics validated: **shopping-mission drivers** (fast delivery, low price), **membership share** (affects free-shipping sensitivity), and comparison shopping/multihoming (supports exit-to-competitor behavior).

#### K05. 2025 디지털정보격차 실태조사 (Digital Divide Survey)
- Publisher: 과학기술정보통신부 · NIA. Released **2026-03-26**. Digitally vulnerable groups (older adults 55+, people with disabilities, low-income, farmers/fishers) reached **77.9% of the general public's digital-information level**, up for 5 straight years, with gains in access, competency and use for every group. — [KDI EIEC](https://eiec.kdi.re.kr/policy/materialView.do?num=278528)
- Snippet-only (press, not checked against the report): access level 96.6% vs competency 65.9% among vulnerable groups. Older-adult AI-service experience 30.2% vs 59.4% for the general public. Older-adult kiosk use 54.2%. — [머니투데이](https://www.mt.co.kr/tech/2026/03/27/2026032710093798860)
- TwinStore metric validated: **60대+ persona difficulty** (slower task completion, higher abandonment, lower search use). The report's 활용 sub-index includes online shopping/e-commerce items in the full PDF (not opened here).

#### K06. 2025 웹 접근성 실태조사 (Web Accessibility Survey)
- Publisher: 과학기술정보통신부 · NIA. Released 2026-03-26. **1,000 websites in 8 industries. Average score 70.4 (+3.7). 금융·보험 highest at 79.0. 도매·소매업 (retail incl. shopping malls) lowest at 65.7.** Firms with 300+ employees scored 78.2. — [KDI EIEC](https://eiec.kdi.re.kr/policy/materialView.do?num=278528)
- Older mobile-app accessibility rounds: 2020, 300 apps, average 69.2 (shopping and delivery apps fell); 2021, average 75.2 — snippet-only, [더나은미래](https://futurechosun.com/?p=59421).
- TwinStore metric validated: accessibility-related friction for older or impaired personas (ease-of-use scores in the exit survey).

### Inferences
- The official mobile share (78–79% of value, 2025–26) is far above TwinStore's default ~55% mobile. For a Korean venue, a default nearer 75–85% mobile is better supported (see K15 for a self-report check). Caveat: value share ≠ session share, and desktop sessions may carry larger baskets.
- The 온라인쇼핑동향 category mix is dominated by 음식서비스 (food delivery), 음식료품 and 여행. A TwinStore validation on a general-merchandise web shop should compare against goods categories only (exclude 음식서비스/여행/이쿠폰) before comparing category shares.
- BOK data supports modelling easy-pay as roughly co-equal with cards in Korea (see K15: 44.9% vs 48.4% as first-choice online method). Within easy pay, fintech "pays" hold more than half.

### Gaps
- KOSIS table IDs for 온라인쇼핑동향조사 could not be verified: KOSIS redirected to SSO in this session. DT_1KE10041 was tried but its title was not confirmed. The report writer should list KOSIS tables by name, or verify the IDs manually.
- 2025 인터넷이용실태조사 shopping-specific figures (online-shopping use rate by age/gender, purchase frequency, payment means, device for shopping) were not retrievable. The press release covered internet use and AI. The 요약보고서 PDF (posted 2026-04-27) and the data.go.kr XLSX would hold them.
- The 2025 annual 온라인쇼핑 total (press reports say "272조원 이상", from the 국가데이터처 「2025년 12월 및 연간 온라인쇼핑 동향」) was snippet-only; the primary release was not opened.
- The BOK does not split simple pay into online vs offline in the parts read here.
- 정보통신정책연구원(KISDI) 한국미디어패널조사 and 방송통신위원회 surveys were not reached in this session (time budget). Both have microdata (KISDI via its 미디어통계포털 with registration). Shopping items were not verified.

---

## Q2. 소비자보호·다크패턴 (Consumer protection, dark patterns, satisfaction, complaints)

### Takeaway
Korea has unusually rich, recent official dark-pattern evidence. The **KCA 2023 audit of 76 e-commerce apps/sites found 429 dark patterns (avg 5.6 per service)**, with social-proof prompts on 93.4% and pre-selected options on 48.7%. The **amended 전자상거래법 (in force 2025-02-14)** now bans six types, including **순차공개 가격책정 (drip pricing)**, **특정옵션의 사전선택 (pre-ticked options)** and **반복간섭 (nagging popups)**. KCA also publishes 5-point satisfaction benchmarks for the major platforms (composite 3.71–3.83).

### Cited Findings

#### K07. 한국소비자원 「온라인 다크패턴 실태조사」 (2023) — e-commerce apps & websites
- Publisher: 한국소비자원. Announced **2023-11-06**. Audit of **76 major e-commerce apps and websites** (including Naver Shopping and Coupang). — [머니투데이방송 MTN](https://news.mtn.co.kr/news-detail/2023110612532895104)
- **429 dark patterns in total, average 5.6 per service.** Prevalence by type (share of the 76): other-consumer-activity alerts (사회적 증거) 71 (93.4%), emotional language 66 (86.8%), time-limit alerts 57 (75.0%), **pre-selected options 37 (48.7%)**, hidden information 34 (44.7%). — [MTN](https://news.mtn.co.kr/news-detail/2023110612532895104)
- For the FTC's 13 "harmful" types: 188 instances, average 2.5 types per service. Most common were pre-selected options, then hidden information, bait-type sales and false recommendations. — [MTN](https://news.mtn.co.kr/news-detail/2023110612532895104)
- Access: KCA press release and report PDF on kca.go.kr (보도자료), free.
- TwinStore metrics validated: **prevalence priors for popups, urgency timers, social proof and pre-ticked add-ons** in a "realistic Korean shop" condition. It also gives a reference point for how often agents should encounter each pattern.

#### K08. 한국소비자원 모바일 앱 다크패턴 조사 (2021)
- **97% of 100 domestic e-commerce mobile apps** had at least one dark pattern. — [메트로서울](https://www.metroseoul.co.kr/article/20230421500071)
- Snippet-only (source not opened; treat with caution): 268 patterns, about 2.7 per app, with top types 개인정보 공유 19.8%, 자동결제 13.8%, 선택 강요 10.4%, 해지 방해·압박 판매 10.1% each, 사회적 증거 9.6%. Possibly from a KoreaScience paper on the same data. — [koreascience JAKO202207957604793](https://koreascience.or.kr/article/JAKO202207957604793.pdf) (content not verified)

#### K09. 공정거래위원회 「온라인 다크패턴 자율관리 가이드라인」 (2023-07-31)
- **4 categories (편취형, 오도형, 방해형, 압박형) and 19 sub-types.** Non-binding self-regulation guideline. Recommends explicit consent and **notice at least 7 days before** free-to-paid conversion or a price increase (숨은 갱신). Applies to e-commerce under 전자상거래법 and online ads under 표시광고법. — [뉴스1](https://www.news1.kr/amp/economy/trend/5125656); [디자인컴패스](https://designcompass.org/2023/08/09/dark-pattern-guideline/); [위픽레터](https://letter.wepick.kr/post/900)
- 2026 revision: the FTC published 「다크패턴 방지를 위한 온라인 인터페이스 운영 가이드라인」, merging the 2023 guideline with the six-type Q&A. It is reorganised into **4 categories and 13 sub-types**, and remains non-binding. — [법무법인 세종(신김) 뉴스레터](https://www.shinkim.com/kor/media/newsletter/3545)
- TwinStore metric validated: the **taxonomy for the dark-pattern conditions** (drip pricing, pre-ticked add-ons, forced sign-up, popups) in Korean regulatory terms.

#### K10. 전자상거래법 개정 — dark-pattern provisions (in force 2025-02-14) and enforcement
- **Six regulated types: 숨은갱신, 순차공개 가격책정 (drip pricing), 특정옵션의 사전선택 (pre-ticked), 잘못된 계층구조 (false hierarchy), 취소·탈퇴 등의 방해 (obstruction), 반복간섭 (nagging).** Effective 2025-02-14. The FTC distributed a six-type Q&A. Platforms (통신판매중개자) must also manage their own interfaces. — [서울시 경제 누리집 (FTC release)](https://news.seoul.go.kr/economy/archives/566114); [뉴시스 Q&A](https://mobile.newsis.com/view/NISX20250213_0003063585)
- Grace period ended **2025-08-13**. — [법률신문](https://www.lawtimes.co.kr/news/articleViewAmp.html?idxno=215573)
- FTC monitoring (announced 2025-09-30): **45 suspected cases at 36 businesses**, mainly obstruction of cancellation and missing consent on free-trial-to-paid conversion. — [아주경제](https://www.ajunews.com/view/20250930090054869)
- First sanctions (Oct 2025): 4 businesses, including online shopping malls, fined a combined ₩1,050만 (deceptive inducement, cancellation obstruction, information duties). — [법률신문](https://www.lawtimes.co.kr/news/articleViewAmp.html?idxno=215573)
- TwinStore metric validated: the legal definition of the drip-pricing and pre-ticked conditions, and the argument that these conditions are policy-relevant in Korea after 2025.

#### K11. 한국소비자원 온라인쇼핑몰(오픈마켓) 소비자 만족도 조사 (published 2024-02-08)
- Publisher: 한국소비자원. Five platforms: 네이버쇼핑, 쿠팡, 11번가, G마켓, 카카오쇼핑. — [경향신문](https://www.khan.co.kr/article/202402080735001)
- **Composite satisfaction (5-pt): 쿠팡 3.83, 네이버쇼핑 3.79, G마켓 3.75, 11번가 3.72, 카카오쇼핑 3.71.** Order/payment/delivery stage **4.21** (Naver 4.27, Coupang 4.24, G마켓 4.21, 11번가 4.20, Kakao 4.14). Product dimension **3.66**. In service-experience items, negative emotions outnumbered positive ones at all five. — [경향신문](https://www.khan.co.kr/article/202402080735001)
- **Spend: ₩63,500 average per purchase. ₩207,200 average per month.** Monthly spend bands: ₩25만+ 27.4%, ₩10–15만 21.6%, ₩5–10만 16.9%, ₩20–25만 15.6%. **Purchase frequency: 2–3 times/month 31.0%, once a week 30.3%, 2–3 times/week 19.3%.** — [경향신문](https://www.khan.co.kr/article/202402080735001)
- Main switching reasons: Coupang for lower prices, Kakao for app ease, Naver/11번가/G마켓 for extra benefits. — [경향신문](https://www.khan.co.kr/article/202402080735001)
- TwinStore metrics validated: **AOV (₩63.5k)**, **purchase frequency**, and **exit-survey satisfaction scale** (a 5-pt composite of ~3.7–3.8 as the real-world anchor; checkout stage > product stage).

#### K12. 공정거래위원회_1372 소비자상담 판매유형별 접수통계 (Open API)
- 공공데이터포털 **dataset 15142643 (Open API)**. Monthly counts of 1372 consumer-counselling cases by sales type (판매유형코드/명/건수), including e-commerce channels. — [data.go.kr 15142643](https://www.data.go.kr/data/15142643/openapi.do)
- TwinStore metric validated: indirect, a complaint-incidence baseline by channel. It is not behavioral.

### Inferences
- Korean dark-pattern prevalence is high enough (avg 5.6 per service; 48.7% pre-ticked; 75% countdown timers) that a "Korean realistic" TwinStore condition should include several patterns at once rather than one isolated pattern.
- The 2025 law names exactly the patterns TwinStore simulates (drip pricing, pre-ticked add-ons, repeated popups, obstruction). This framing strengthens the paper's relevance to Korean policy evaluation.
- KCA's satisfaction structure (checkout/delivery 4.21 > product 3.66) is a testable pattern: TwinStore exit surveys should show higher "ease" than "product satisfaction" if they are realistic.

### Gaps
- No Korean source found that quantifies **behavioral effects** of dark patterns (e.g., the % of users who keep a pre-ticked add-on, or abandonment uplift from drip pricing). Only prevalence audits and regulation were found. The KCA 2023 report may contain a consumer survey section (not opened).
- The KCA 2024 satisfaction survey's sample size, method and fieldwork dates were not in the article. Check the original KCA release on kca.go.kr.
- 서울시 전자상거래센터 annual mall evaluations exist (e.g., 2022: Coupang 84.14 points among open markets — snippet-only via [서울시](https://news.seoul.go.kr/economy/archives/87352)) but were not examined.

---

## Q3. 산업 리포트 (Industry reports): 나스미디어 NPR, 오픈서베이, 와이즈앱, 쿠팡 IR, 데이터랩, 전환율 벤치마크

### Takeaway
The most useful industry source is **나스미디어 2025 NPR** (N=2,000 aged 15–69, Jan 2025, Opensurvey panel). It gives the share of shopping by channel (**mobile 61.4%, offline 26.9%, PC 10.2%**), first-choice online payment (**card 48.4%, easy pay 44.9%**, with age gradients), platform use, and ad-type contact→click→purchase funnels. Korean **mall-level conversion / cart-abandonment benchmarks are scarce**: the only widely cited figure is **1.33% average conversion (빅인사이트, 2020)**.

### Cited Findings

#### K13. 나스미디어 「2025 NPR (Netizen Profile Research) 인터넷 이용자 조사」 요약보고서
- Publisher: kt nasmedia. Annual. **Fieldwork 2025-01-13~15. Mobile self-administered survey via Opensurvey. N=2,000 internet users aged 15–69.** The summary report analyzes ages 15–59 only (N=1,900). Respondents: male 51.4 / female 48.6. 10대 17.4, 20대 20.6, 30대 20.9, 40대 23.8, 50대 17.4 (%). Free PDF, no registration. — [NPR 2025 요약보고서 PDF](https://www.nasmedia.co.kr/wp-content/uploads/2025/05/2025_NPR_요약보고서_f.pdf)
- **Share of shopping by method (purchasers in the past year, N=1,834, numeric allocation): mobile 61.4%, offline 26.9%, PC 10.2%, other 1.6%.** Mobile is above 50% in every age group. By segment (mobile / offline / PC, parsed from the chart; each row sums to ≈100):
  - 남 57.5 / 27.4 / 14.0
  - 여 65.3 / 26.4 / 6.2
  - 10대 61.3 / 31.8 / 6.5
  - 20대 66.1 / 24.1 / 9.5
  - 30대 64.3 / 22.4 / 12.3
  - 40대 60.6 / 26.2 / 11.1
  - 50대 53.3 / 32.3 / 10.5
  - — [NPR 2025](https://www.nasmedia.co.kr/wp-content/uploads/2025/05/2025_NPR_요약보고서_f.pdf)
- **Main shopping malls (N=1,740, top-5 multi-rank): 쿠팡 70.9%, 네이버쇼핑 60.1%, 올리브영 22.9%, 무신사 22.6%, G마켓 21.7%.** Coupang is #1 in every age group except 30대 (네이버쇼핑 75.1% vs 쿠팡 72.4%). 10대 #2 is 에이블리 (39.2%). 50대 #3 is G마켓 (30.5%). — [NPR 2025](https://www.nasmedia.co.kr/wp-content/uploads/2025/05/2025_NPR_요약보고서_f.pdf)
- **First-choice online payment method (N=1,768): 카드결제 48.4%, 간편결제 44.9%, 현금입금 (bank transfer/virtual account) 4.1%, 포인트결제 2.7%.** By age (card / easy pay / cash transfer / points; parsed from the chart, each row sums to 100):
  - 10대 47.3 / 39.4 / 11.1 / 2.2
  - **20대 35.6 / 57.2 / 3.5 / 3.7**
  - 30대 43.7 / 49.5 / 3.7 / 3.1
  - 40대 52.1 / 44.4 / 1.9 / 1.6
  - **50대 65.7 / 29.4 / 2.3 / 2.6**
  - Easy pay by gender is about 45% for both (44.7 / 45.0).
  - — [NPR 2025](https://www.nasmedia.co.kr/wp-content/uploads/2025/05/2025_NPR_요약보고서_f.pdf)
- **Easy-pay services used (easy-pay users, N=1,360, multi): 네이버페이 81.3%, 카카오페이 76.0%, 토스페이 50.4%, 삼성페이 34.9%**, 페이코 (5th; total not parsed). Naver Pay by age: 10대 56.9, 20대 85.6, 30대 89.7, 40대 85.3, 50대 75.5. — [NPR 2025](https://www.nasmedia.co.kr/wp-content/uploads/2025/05/2025_NPR_요약보고서_f.pdf)
- **Paid shopping membership: 65.4% overall (30대 78.6%, 40대 75.2%). Coupang 로켓와우 47.4%** (#1). — [NPR 2025](https://www.nasmedia.co.kr/wp-content/uploads/2025/05/2025_NPR_요약보고서_f.pdf)
- **Ad-type funnel (N=1,900; % contacted → clicked → purchased; purchase/contact):**
  - 검색광고 73.3 → 31.8 → 15.4 (**21%**)
  - 배너 73.0 → 22.2 → 7.9 (11%)
  - 카카오 메신저 68.0 → 21.2 → 7.9 (12%)
  - 동영상 60.2 → 17.9 → 5.9 (10%)
  - 숏폼 54.8 → 20.5 → 8.1 (15%)
  - SNS 피드 44.2 → 14.2 → 5.0 (11%)
  - 포인트/캐시 충전 38.4 → 11.7 → 4.3 (11%)
  - — [NPR 2025](https://www.nasmedia.co.kr/wp-content/uploads/2025/05/2025_NPR_요약보고서_f.pdf)
- Non-work daily mobile internet time: 10대 5h23m weekday / 6h36m weekend; 20대 4h52m / 6h01m. — [NPR 2025](https://www.nasmedia.co.kr/wp-content/uploads/2025/05/2025_NPR_요약보고서_f.pdf)
- TwinStore metrics validated: **device mix by age/gender**, **payment-method choice by age**, **traffic source (search vs display vs social) relative conversion**, and membership (free-shipping eligibility).

#### K14. 오픈서베이 「온라인 쇼핑 트렌드 리포트 2025」
- Publisher: 오픈서베이 (Opensurvey). Nationwide consumers aged 15–69. The blog does not state the sample size or fieldwork dates; the full report is downloadable (free, email gate). — [오픈서베이 블로그](https://blog.opensurvey.co.kr/article/online-shopping-2025-2/)
- **Coupang: 69.9% used in the last month, 47.5% weekly, average 1.65 purchases/week** (highest). Main categories: household goods, food/groceries, kitchenware. **Naver Shopping: 56.0% last month, 22.6% weekly. Average spend per purchase ₩61,200 (6.12만원)**, the highest of the platforms. — [오픈서베이](https://blog.opensurvey.co.kr/article/online-shopping-2025-2/)
- Toss Shopping: 42.0% aware, 27.1% ever used (discovered while browsing the Toss app; first purchase driven by low price and promotions). Brand-owned malls (자사몰): 80.0% ever used, 20.0% in the last month. Price-seeking behaviors: cross-site price comparison, waiting for events, reviews for points (no %). — [오픈서베이](https://blog.opensurvey.co.kr/article/online-shopping-2025-2/)
- TwinStore metrics validated: **AOV per order (~₩61k on Naver)**, **purchase frequency**, **price-comparison/exit behavior**, and the low last-month reach of brand-owned malls (20%). That last figure is relevant if TwinStore renders a standalone D2C shop.

#### K15. 와이즈앱·리테일 (WiseApp·Retail) — app usage and card-payment estimates
- Method: panel-based estimates of Korean credit/check-card payments (excludes bank transfer, cash, gift cards) and app MAU. Commercial; press releases are free.
- **Coupang 2025 estimated payment amount ₩66조 2,109억 (+~13% from ₩58조 7,137억 in 2024).** Coupang Eats ₩11조 3,629억 (+58%). — [스마트투데이](https://www.smarttoday.co.kr/ko-kr/articles/102248)
- Snippet-only (individual articles not opened): Sept 2025 shopping-app MAU 쿠팡 3,427만, 올리브영 959만, 에이블리 938만, 네이버플러스 스토어 513만. Naver Plus Store MAU 347.9만 (Jun 2025) → 908.0만 (Jun 2026), +161%, while Coupang went 3,362.99만 → 3,509.17만 (+4.3%). — [바이라인네트워크](https://byline.network/2026/01/27_192773/); [아시아경제](https://view.asiae.co.kr/article/2026072016251065967)
- TwinStore metrics validated: platform-level reach and spend context. It does not validate session behavior.

#### K16. 쿠팡 Inc. 실적 (Coupang SEC filings / IR), Q2 2026
- **Product Commerce active customers 24.7M (+3% YoY from 23.9M). Revenue per active customer $301 for the quarter (−2% in USD, +5% in constant currency).** Product Commerce revenue $7.425B. Total revenue $8.856B (≈₩13.3조, +4%, +10% cc). Operating loss $556M after a ₩6,246.81억 PIPC privacy fine. — [뉴데일리](https://biz.newdaily.co.kr/site/data/html/2026/08/05/2026080500014.html)
- Access: Coupang IR site / SEC EDGAR (10-Q), free.
- TwinStore metric validated: per-customer spend over time, as a sanity check on AOV × frequency.

#### K17. 네이버 데이터랩 쇼핑인사이트 (Naver DataLab Shopping Insight) + API
- Free web tool (datalab.naver.com) and Open API (Naver Developers / NCP API docs). Daily, weekly or monthly **relative click indices** (max = 100) for shopping categories (up to the 4th level) and keywords. Filters: **device (PC/mobile)** and **age (10, 20, … 60 = 60+)**. A gender breakdown for Shopping Insight was not confirmed in this session; the docs pages seen cover device and age. Check the docs for a gender endpoint. — [NCP API docs: device](https://api.ncloud-docs.com/docs/naver-api-hub-shopping-insight-device); [age](https://api.ncloud-docs.com/docs/naver-api-hub-shopping-insight-age); [keyword-age](https://api.ncloud-docs.com/docs/naver-api-hub-shopping-insight-keyword-age.md)
- Caveat: values are relative ratios, not counts. — [디지털마케터](https://www.digitalmarketer.co.kr/insights/naver-datalab-api-data-for-non-developers)
- TwinStore metrics validated: **category interest by age and device** and **site-search keyword plausibility** (do simulated 20대 women search fashion terms in proportions like the real trends?).

#### K18. 국내 이커머스 평균 구매전환율 1.33% (빅인사이트, 2020 DMS presentation)
- Widely re-cited Korean benchmark: **average e-commerce purchase conversion 1.33%**, from a presentation by 빅인사이트 CEO 홍승표 at DMS 2020. Secondary sources only; the underlying mall sample is not disclosed in the pages seen. — [아이보스](https://www.i-boss.co.kr/ab-74668-3359); [디지털인사이트 (403 in this session)](https://ditoday.com/국내-이커머스-평균-전환율-문제의-파악-그리고-희망/)
- TwinStore metric validated: **overall conversion rate** (weak, old, single-vendor).

### Inferences
- NPR's mobile/PC allocation implies **mobile ≈ 85.8% of online shopping** (61.4 / (61.4 + 10.2)). It is ≈91% for women and ≈80% for men, and ~84–90% across 10대–50대. This is consistent with the official 78% value share. Both point to TwinStore's 55% mobile default being too low for Korea. A gender split (women more mobile) is a cheap realism check.
- Payment priors for Korean personas (from K13): easy pay ≈ 45%, card ≈ 48%, bank transfer ≈ 4%, points ≈ 3%. Use a steep age gradient: 20대 easy pay 57% vs 50대 29%. No source supports a material share for cash-on-delivery in Korea; it should be ~0 in a Korean scenario. BNPL is niche (see K28).
- NPR's search-ad purchase/contact ratio (21%) is about 2× display/banner (11%). TwinStore traffic-source breakdowns should show search > social/display in conversion if they are realistic.
- AOV anchors in KRW: ₩61–64k per order (KCA 2024: ₩63.5k; Opensurvey 2025 Naver: ₩61.2k).

### Gaps
- **No recent (2023–2026) Korean benchmark for cart abandonment, add-to-cart rate, bounce rate, pages per session or session duration** was found from Cafe24, 고도몰 (NHN커머스) or 메이크샵. Cafe24 and NHN커머스 publish marketing help pages but no aggregate statistics were located. This is the largest gap for TwinStore's funnel validation; the L.POINT clickstream (K22) is the best substitute.
- 나스미디어 2026 NPR (likely published ~May 2026) was not found. The 2025 edition is the latest confirmed.
- Not reached in this session (time budget): 메조미디어 업종 분석 리포트, 대학내일20대연구소, 코리안클릭/닐슨 web/app traffic, 한국온라인쇼핑협회, 삼정KPMG/Deloitte Korea, 신한카드/BC카드 빅데이터, Google/Kantar Korea. Their availability and figures are unverified.

---

## Q4. 공개 데이터셋 (Public datasets): 공공데이터포털, AI Hub, L.POINT, 기타

### Takeaway
There is **no openly downloadable Korean e-commerce clickstream** with sessions, hits and funnel actions comparable to the GA sample. The L.POINT competitions (롯데멤버스) distributed transformed online-behavior data only to registered entrants. AI Hub offers Korean review-sentiment and product-image data, approved for Korean nationals only. data.go.kr offers aggregate survey and complaint statistics.

### Cited Findings

#### K19. 공공데이터포털 — 인터넷이용실태조사 통계자료 (dataset 15086936)
- See K02. XLSX plus codebook, KOGL Type 2, free download, annual. — [data.go.kr 15086936](https://www.data.go.kr/data/15086936/fileData.do)

#### K20. 공공데이터포털 — 공정거래위원회 1372 소비자상담 판매유형별 접수통계 (dataset 15142643, Open API)
- See K12. — [data.go.kr 15142643](https://www.data.go.kr/data/15142643/openapi.do)

#### K21. AI Hub 「속성기반 감정분석 데이터」 (Aspect-Based Sentiment Analysis), dataSetSn=71603
- Built 2022. v1.0 released 2023-07-31, v1.1 released 2023-12-15. **250,312 records: 225,300 shopping-mall reviews (90%) and 25,012 SNS reviews.** Domains: fashion (women's/men's clothing, shoes, accessories), cosmetics, appliances, IT devices, household goods. Each review has aspect spans (comfort, design, price, material…) with polarity labels. JSON/txt. **Access: application and approval required; Korean nationals only ("내국인만 데이터 신청이 가능합니다").** — [AI Hub 71603](https://www.aihub.or.kr/aihubdata/data/view.do?currMenu=115&topMenu=100&dataSetSn=71603)
- TwinStore use: compare the aspect/sentiment distribution of simulated **exit-survey free text and product reviews** with real Korean mall reviews (e.g., price vs design vs size mentions by category).

#### K22. 롯데멤버스 「L.POINT Big Data Competition」 — 온라인 행동 데이터
- **제5회 엘포인트 빅데이터 컴피티션 (2018-10-22 ~ 2019-01-16), theme "Digital Trend Analyzer — 온라인 행동 기반 트렌드 예측".** Provided data: **"온라인 행동 데이터, 상품분류정보"**. The page states the data is transformed and differs from real market data. Downloads were for registered team leaders only (2018-12-03 ~ 2019-01-16). Official site competition.lpoint.com. — [위비티 대회 페이지](https://www.wevity.com/index_university.php?c=find&s=_university&gbn=viewok&gp=1434&ix=27028)
- 제6회 (2019, registration 2019-10-21 ~ 11-26): Audience Targeting using non-identified online prospects' behavior/consumption patterns, plus AI hyper-personalized content recommendation. — [위비티 제6회](https://www.wevity.com/index_university.php?c=find&s=_university&gbn=viewok&gp=49&ix=36778); [링커리어](https://linkareer.com/activity/29236)
- 제7회 롯데멤버스 빅데이터 경진대회 (2022): customer **purchase** data, prediction plus personalized marketing. — [PyTorch Korea](https://discuss.pytorch.kr/t/topic/330)
- L.POINT's commercial data service (DeepVision) describes L.POINT big data as 온·오프라인 구매정보, 온라인 행동정보, 위치정보, 리서치 데이터. — [L.POINT DeepVision](https://deepvision.lpoint.com/app/deepVision/BPPA100100.do?mCode=M104&smCode=01)
- TwinStore metrics potentially validated: session-level **funnel (search → product view → cart → checkout → purchase)**, **site-search keywords**, **device**, **traffic source**, **pages/session and session time**, by **age/gender**. This depends on the field list (see Gaps).

#### K23. AI Hub 「상품 이미지」 and 「의류 통합 데이터(착용 이미지, 치수 및 원단 정보)」
- 상품 이미지 (aidata/34145): product images for small-retailer automated-store product classification, multi-angle shots. Snippet-only: about 10,000+ products in 14 major classes. — [AI Hub 상품 이미지](https://aihub.or.kr/aidata/34145)
- 의류 통합 데이터 (dataSetSn=71501): wear images, size and fabric information. — [AI Hub 71501](https://www.aihub.or.kr/aihubdata/data/view.do?currMenu=115&topMenu=100&dataSetSn=71501)
- TwinStore use: realistic Korean product imagery and attributes for rendered shops. These are not behavioral.

### Inferences
- If the authors can obtain the L.POINT 5th-competition online behavior file (e.g., via past entrants, theses that used it, or a request to 롯데멤버스), it is the closest Korean analogue to TwinStore's session logs. Otherwise the paper must rely on aggregate Korean statistics (K01, K13) plus non-Korean clickstream for funnel shape.
- AI Hub's Korean-nationals-only rule matters for international co-authors. Only a Korean co-author can apply.

### Gaps
- **The L.POINT online-behavior field schema could not be verified.** Searches for the column names that later analyses reportedly used (session ID, hit sequence, action type, search keyword, device category, traffic source, page-view count, session time) returned nothing citable. The report writer should not state the schema or the action-type codes without a primary source (competition.lpoint.com archive, or a thesis/KCI paper that used the data).
- No DACON e-commerce clickstream competition was verified in this session.
- 금융데이터거래소, KDX 한국데이터거래소 and 문화·유통 빅데이터 플랫폼 consumption datasets were not examined (time budget). They are commercial or registration-gated, and their availability is unverified.
- A search for KCA "소비자위해정보" turned up injury data, which is not relevant to shopping behavior.

---

## Q5. 학술 연구 (Korean academic studies): cart abandonment, conversion, dark patterns, mobile, older adults

### Takeaway
Searches surfaced few citable recent Korean empirical papers on cart abandonment or conversion. The items found are older or unverified. A dedicated KCI/RISS/DBpia pass is still needed. Use the government digital-divide and accessibility surveys (K05, K06) as the older-adult and accessibility evidence base.

### Cited Findings
- K24. 「인터넷 소비자의 구매지연행동에 영향을 미치는 요인: 상황적 요인과 지각된 불확실성을 중심으로」 (KoreaScience, 2014). Studies online purchase delay driven by situational factors and perceived uncertainty, a related construct to cart abandonment. The design and results were not read. — [KoreaScience JAKO201423261321562](https://www.Koreascience.or.kr/article/JAKO201423261321562.page)
- K25. 「온라인 행동 로그 분석을 통한 사용자 행동 예측」 (서울대 S-Space). Analyzes online action logs grouped by user and product, relating product-page views and time-to-purchase to purchase rates. Snippet-only summary. — [SNU S-Space 10371/123143](https://s-space.snu.ac.kr/handle/10371/123143)
- K26. KoreaScience dark-pattern paper (JAKO202207957604793, 2022). It appeared in dark-pattern searches and may report the 2021 KCA 100-app breakdown (K08). Content not verified. — [KoreaScience PDF](https://koreascience.or.kr/article/JAKO202207957604793.pdf)
- K27. 행태 기반 추천시스템 (KAIST thesis, "Behavior-based recommender system using big data analysis"). It appeared in L.POINT searches. Whether it used L.POINT online-behavior data is unverified. — [KAIST DSpace 10203/241659](https://dspace.kaist.ac.kr/handle/10203/241659)

### Inferences
- For the paper's related-work section, Korean academic evidence on online funnel metrics looks thin compared with official and industry statistics. That gap itself supports the value of a simulator plus validation against aggregate Korean benchmarks.

### Gaps
- No verified 2023–2026 Korean KCI paper reporting measured cart-abandonment or conversion rates was found. Suggested queries for RISS/KCI/DBpia: "장바구니 포기", "구매 포기 의도", "모바일 쇼핑 구매전환", "다크패턴 소비자 반응 실험", "고령층 온라인 쇼핑 어려움".
- The older adults' online-shopping difficulty items in the 디지털정보격차 report were not opened (PDF D2603326).

---

## Q6. 결제수단·배송·무료배송·쇼핑동기 (Payment shares, delivery and free-shipping expectations, shopping missions)

### Takeaway
Payment-method priors are well supported: **card ≈ 48% vs easy pay ≈ 45% first-choice online (NPR 2025)**, with fintech pays dominating easy pay (BOK 2025: 54.9%). **Fast delivery and low price are the dominant platform-choice motives** (MSIT 2025), and paid memberships with free shipping are mainstream (65–76%). **No Korean survey on free-shipping threshold expectations was found.**

### Cited Findings
- First-choice online payment (2025): card 48.4%, easy pay 44.9%, cash transfer 4.1%, points 2.7%. 20대 easy pay 57.2%, 50대 29.4%. — [NPR 2025](https://www.nasmedia.co.kr/wp-content/uploads/2025/05/2025_NPR_요약보고서_f.pdf)
- Easy-pay brand reach among easy-pay users: Naver Pay 81.3%, Kakao Pay 76.0%, Toss Pay 50.4%, Samsung Pay 34.9%. — [NPR 2025](https://www.nasmedia.co.kr/wp-content/uploads/2025/05/2025_NPR_요약보고서_f.pdf)
- Daily simple-pay volume ₩1조 1,053억 (2025). 전자금융업자 54.9%, 휴대폰제조사 23.7%, 금융회사 21.5%. — [BOK](https://www.bok.or.kr/portal/bbs/B0000502/view.do?nttId=10097038&menuNo=201265); [서울파이낸스](https://www.seoulfn.com/news/articleView.html?idxno=624139)
- K28. BNPL (후불결제), older data: as of end-June 2023, cumulative BNPL subscribers at the three big-tech firms (Naver Financial, Kakao Pay, Toss) were **3.02M (+13.4% QoQ)**. Reported average delinquency was 5.8% at end-June (the year is not stated in the snippet). Naver Pay BNPL limit up to ₩30만/month. — [뉴시스 2023-08-16](https://www.newsis.com/view/NISX20230816_0002415890); [뉴시스 2022-05-10](https://mobile.newsis.com/view/NISX20220510_0001865899)
- Platform choice driven by "빠른 배송과 저렴한 가격". 95.6% used e-commerce platforms in Q4 2025. 83.9% multihome. 75.9% hold a commerce membership. — [한국시사경제 (MSIT 부가통신사업 실태조사)](https://www.hksisaeconomy.com/news/article.html?no=1148464)
- Paid shopping membership 65.4%. Coupang 로켓와우 47.4%. — [NPR 2025](https://www.nasmedia.co.kr/wp-content/uploads/2025/05/2025_NPR_요약보고서_f.pdf)
- Coupang main categories: household goods, food, kitchenware. Naver relatively higher in fashion. Kakao in health and cosmetics. — [오픈서베이](https://blog.opensurvey.co.kr/article/online-shopping-2025-2/)

### Inferences
- With ~half of Korean online shoppers on free-shipping memberships (Rocket WOW 47%), simulated Korean personas facing a free-shipping threshold on an unfamiliar shop are being compared with consumers accustomed to no threshold. Expect higher sensitivity to delivery fees than in markets with lower membership penetration. The paper can frame threshold reactions against that baseline.
- Shopping-mission priors: "fast delivery" and "low price" should be the most frequent stated motives in exit surveys of Korean personas.

### Gaps
- No Korean consumer survey on **free-shipping threshold expectations** (e.g., expected minimum order for 무료배송, acceptable delivery fee) was found. The same applies to coupon or popup response rates.
- No 2025–26 official BNPL usage figures (FSC/FSS) were found.
- Cash on delivery: no Korean usage statistic found. It appears negligible in Korean e-commerce, but that is an unsupported inference.

---

## Q7. TwinStore 패널 보정 및 지표별 매핑 (Calibration of default panel + metric → source map)

### Takeaway
Korean data supports recalibrating **device share** (mobile ~78% of value, ~86% of self-reported online shopping vs TwinStore's 55%) and **payment-method shares by age**. It gives anchors for **AOV (~₩61–64k)**, **purchase frequency** and **satisfaction (5-pt ~3.7–3.8)**. **Funnel-stage rates (add-to-cart, abandonment, bounce, pages/session, duration) lack recent Korean public benchmarks.** The age weights (10s 8%, 20s 24%, 30s 24%, 40s 19%, 50s 14%, 60s+ 11%) could not be checked against a Korean online-shopper age distribution in this session.

### Cited Findings
- Mobile share of online shopping value 78.1% (Aug 2026). — [KDI EIEC / 국가데이터처](https://eiec.kdi.re.kr/policy/materialView.do?num=287670)
- Shopping-method allocation mobile 61.4 / offline 26.9 / PC 10.2 (2025), with women more mobile than men (65.3 vs 57.5) and 50대 the least mobile (53.3). — [NPR 2025](https://www.nasmedia.co.kr/wp-content/uploads/2025/05/2025_NPR_요약보고서_f.pdf)
- 60대 internet-shopping use 41.2% (2021 survey) vs 73.7% overall. — [뉴스토마토](https://newstomato.com/ReadNews.aspx?no=1028734)
- Metric → Korean source map (entry numbers above):

| TwinStore output | Best Korean source(s) | Strength |
|---|---|---|
| Device mix (mobile/desktop) | K01 (78.1% value share), K13 (by age/gender) | Strong |
| Product-category mix | K01 (category shares and mobile share by category), K17 (interest by age/device) | Strong (value), medium (interest) |
| Payment method choice | K13 (by age), K03 (easy-pay volume and provider split) | Strong |
| AOV (KRW) | K11 (₩63.5k), K14 (Naver ₩61.2k), K16 ($301/quarter per Coupang customer) | Medium |
| Purchase frequency / return intent | K11 (frequency bands), K14 (Coupang 1.65/week), K04 (multihoming 83.9%) | Medium |
| Conversion rate | K18 (1.33%, 2020, secondary) | Weak |
| Funnel steps, add-to-cart, cart abandonment, bounce, pages/session, duration, site search, exit pages | K22 (L.POINT online behavior, access-limited); otherwise none found | Gap |
| Traffic source | K13 (ad-type contact→click→purchase) | Medium (self-report) |
| Age / gender breakdowns | K13, K02 (2025 tables not retrieved), K17 | Medium |
| Shopping mission / motives | K04 (fast delivery and low price), K14, K11 (switching reasons) | Medium |
| Dark patterns (exposure / regulation) | K07, K08, K09, K10 | Strong (prevalence); behavioral effects are a gap |
| Exit survey (satisfaction, ease) | K11 (5-pt composite and stage scores) | Medium |
| NPS / "would return" | none found | Gap |
| Older-adult difficulty / accessibility | K05, K06, K02 (60대 shopping rate) | Medium |
| Free-text reviews / sentiment | K21 (AI Hub ABSA, 225k mall reviews) | Medium |

### Inferences
- Recommended Korean scenario defaults, inferred from the sources above:
  - mobile 80–85%
  - women more mobile than men by ~6–10 pp
  - 50대+ the least mobile
  - payment shares with age gradients as in K13
  - COD ≈ 0
  - BNPL ≤ a few %
- NPR's sample quotas (10대 17.4 … 50대 17.4) are survey quotas, not a population distribution, and should not be used to set age weights.

### Gaps
- A Korean **age distribution of online shoppers** (needed to check 10s 8% / 20s 24% / 30s 24% / 40s 19% / 50s 14% / 60s+ 11%) was not obtained. Candidates: 인터넷이용실태조사 2025 tables or microdata (K02/K19) on online-shopping use rate by age × population by age (KOSIS 주민등록인구); 와이즈앱 app-user age composition (commercial).
- No Korean NPS benchmark for e-commerce was found.
