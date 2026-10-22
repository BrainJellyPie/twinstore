// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, it, vi } from "vitest";
import * as marketing from "@/shared/api/marketing";
import type { Store } from "@/shared/types/domain";
import { SurveyBuilder } from "../SurveyBuilder";
import { ConjointBuilder } from "../ConjointBuilder";
import { ShelfTestBuilder } from "../ShelfTest";
import { ExperimentBuilder } from "../ExperimentBuilder";
vi.mock("@/shared/api/client",async original=>({...await original<typeof import("@/shared/api/client")>(),getModels:vi.fn().mockResolvedValue([])}));
vi.mock("@/shared/api/marketing",async original=>({...await original<typeof import("@/shared/api/marketing")>(),designSurvey:vi.fn(),designShelfTest:vi.fn(),designConjoint:vi.fn(),designExperiment:vi.fn(),startSurvey:vi.fn(),startShelfTest:vi.fn(),startConjoint:vi.fn(),startExperiment:vi.fn(),previewShelf:vi.fn().mockResolvedValue({face:"N",control:"control.png",test:"test.png",applied:[],warnings:[]})}));
vi.mock("../hooks",()=>({usePackages:()=>({data:[{asset_id:"gold",name:"Gold"}]})}));
vi.mock("../ProductLibrary",()=>({ProductDrop:()=>null}));
const clients:QueryClient[]=[];
afterEach(()=>{cleanup();clients.splice(0).forEach(c=>c.clear());vi.clearAllMocks();});
const store={id:"s",name:"Store",racks:[{id:"r",type:"shelf",rack_name:"Tea",rack_desc:"",levels:4,slots:[{block:0,face:"N",level:1,items:[{sku:"tea",name:"Tea",price:199,promo:""}]}]}]} as unknown as Store;
const products=[{sku:"tea",name:"Tea",price:199,regularPrice:0,promo:"",facings:1,racks:["Tea"]}];
const started=()=>{};
const cases=[{currency:"USD",minor:9007199254740990,shown:"90071992547409.90"},{currency:"GBP",minor:9007199254740990,shown:"90071992547409.90"},{currency:"USD",minor:9007199254740991,shown:"90071992547409.91"},{currency:"EUR",minor:9007199254740991,shown:"90071992547409.91"},{currency:"GBP",minor:9007199254740991,shown:"90071992547409.91"},{currency:"USD",minor:9007199254740989,shown:"90071992547409.89"},{currency:"KRW",minor:9007199254740991,shown:"9007199254740991"},{currency:"JPY",minor:9007199254740991,shown:"9007199254740991"},{currency:"USD",minor:1,shown:"0.01"},{currency:"USD",minor:0,shown:"0"}];
function mount(child:React.ReactNode){const client=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});clients.push(client);render(<QueryClientProvider client={client}>{child}</QueryClientProvider>);}
function mockStart(){const job={job_id:"fake",kind:"survey",name:"",status:"pending",stage:"",progress:0,error:"",created_at:"",finished_at:""} as marketing.JobStatus;vi.mocked(marketing.startSurvey).mockResolvedValue(job);vi.mocked(marketing.startShelfTest).mockResolvedValue(job);vi.mocked(marketing.startConjoint).mockResolvedValue(job);}
it.each(cases)("preserves survey price $minor in $currency without editing",async({currency,minor,shown})=>{
 mockStart();mount(<SurveyBuilder projectId="p" personaCount={60} initial={{stimuli:["gold"],stimulus_names:["Gold"],questions:["appeal"],reference_price:minor,currency,panel:60}} onStarted={started}/>);
 expect((screen.getByLabelText("Shelf price shown with A (optional)") as HTMLInputElement).value).toBe(shown.endsWith(".90")?shown.slice(0,-1):shown);
 fireEvent.click(screen.getByRole("button",{name:"Field the survey"}));await waitFor(()=>expect(marketing.startSurvey).toHaveBeenCalled());expect(vi.mocked(marketing.startSurvey).mock.calls[0]![1].reference_price).toBe(minor);
});
it.each(cases)("preserves shelf price $minor in $currency without editing",async({currency,minor,shown})=>{
 mockStart();mount(<ShelfTestBuilder projectId="p" setupId="s" store={store} currency={currency} initial={{setup_id:"s",rack_id:"r",target_sku:"tea",changes:[{kind:"price",sku:"tea",price:minor}],panel:60}} onStarted={started}/>);
 const expected=currency==="USD"&&minor===0?"0.00":shown;
 expect((screen.getByPlaceholderText(/leave empty to keep/) as HTMLInputElement).value).toBe(expected);
 fireEvent.click(screen.getByRole("button",{name:"Run shelf test"}));await waitFor(()=>expect(marketing.startShelfTest).toHaveBeenCalled());expect(vi.mocked(marketing.startShelfTest).mock.calls[0]![1].changes[0]!.price).toBe(minor);
});
it.each(cases)("preserves conjoint price levels near $minor in $currency",async({currency,minor,shown})=>{
 mockStart();const other=minor>100?minor-100:minor+1;
 mount(<ConjointBuilder projectId="p" personaCount={60} initial={{product:"Tea",attributes:[{name:"Pack",levels:["Can","Bottle"]}],prices:[minor,other],currency,tasks:8,options:3,none_option:true,panel:60,age_groups:[],genders:[],model:""}} onStarted={started}/>);
 expect((screen.getByLabelText(/Price levels/) as HTMLInputElement).value.split(", ")[0]).toBe(shown.endsWith(".90")?shown.slice(0,-1):shown);
 fireEvent.click(screen.getByRole("button",{name:"Field the study"}));await waitFor(()=>expect(marketing.startConjoint).toHaveBeenCalled());expect(vi.mocked(marketing.startConjoint).mock.calls[0]![1].prices).toEqual([minor,other]);
});
it.each(cases)("shows the exact experiment price $minor in $currency",({currency,minor,shown})=>{
 mount(<ExperimentBuilder projectId="p" setupId="s" products={products} store={store} currency={currency} initial={{setup_id:"s",variants:[{name:"Price test",changes:[{kind:"price",sku:"tea",price:minor}]}],focus_skus:["tea"],engine:"rule",panel:300}} onStarted={started}/>);
 expect((screen.getByLabelText("New price") as HTMLInputElement).value).toBe(currency==="USD"&&minor===0?"0.00":shown);
});

for (const kind of ["survey", "shelf", "conjoint", "experiment"] as const) {
  it.each(cases.filter(c => c.currency === "USD" || c.currency === "JPY"))(`preserves ${kind} draft price $minor in $currency`, async ({ currency, minor, shown }) => {
    mockStart();
    const common = { name: "Drafted price", rationale: "Exact price rationale", warnings: [] };
    const changes: marketing.VariantChange[] = [{ kind: "price", sku: "tea", price: minor }];
    vi.mocked(marketing.designSurvey).mockResolvedValue({ ...common, stimuli: ["gold"], stimulus_names: ["Gold"], questions: ["appeal"], context: "Tea", reference_price: minor, currency, age_groups: [], genders: [] });
    vi.mocked(marketing.designShelfTest).mockResolvedValue({ ...common, rack_id: "r", target_sku: "tea", changes, age_groups: [] });
    vi.mocked(marketing.designConjoint).mockResolvedValue({ ...common, product: "Tea", context: "Tea", attributes: [{ name: "Pack", levels: ["Can", "Bottle"] }], prices: [minor, minor > 0 ? minor - 1 : 1], currency, comparable: [] });
    vi.mocked(marketing.designExperiment).mockResolvedValue({ ...common, variants: [{ name: "Price", changes }], focus_skus: ["tea"], engine: "rule" });
    const commonProps = { projectId: "p", setupId: "s", currency, defaultCurrency: currency, onStarted: started };
    if (kind === "survey") mount(<SurveyBuilder {...commonProps} personaCount={60} />);
    if (kind === "shelf") mount(<ShelfTestBuilder {...commonProps} store={store} />);
    if (kind === "conjoint") mount(<ConjointBuilder {...commonProps} personaCount={60} />);
    if (kind === "experiment") mount(<ExperimentBuilder {...commonProps} store={store} products={products} />);
    fireEvent.change(screen.getByLabelText(/Question for/), { target: { value: "Compare this exact price" } });
    fireEvent.keyDown(screen.getByLabelText(/Question for/), { key: "Enter" });
    await screen.findByText(/Exact price rationale/);
    const input = kind === "shelf" ? screen.getByPlaceholderText(/leave empty to keep/)
      : screen.getByLabelText(kind === "survey" ? "Shelf price shown with A (optional)" : kind === "conjoint" ? "Price levels" : "New price");
    const expected = kind === "shelf" || kind === "experiment" ? (minor === 0 ? "0.00" : shown) : shown.replace(/(\.\d*?)0+$/, "$1").replace(/\.$/, "");
    expect((input as HTMLInputElement).value.split(", ")[0]).toBe(expected);
    if (kind === "survey") { fireEvent.click(screen.getByRole("button", { name: "Field the survey" })); await waitFor(() => expect(marketing.startSurvey).toHaveBeenCalled()); expect(vi.mocked(marketing.startSurvey).mock.calls[0]![1].reference_price).toBe(minor); }
    if (kind === "shelf") { fireEvent.click(screen.getByRole("button", { name: "Run shelf test" })); await waitFor(() => expect(marketing.startShelfTest).toHaveBeenCalled()); expect(vi.mocked(marketing.startShelfTest).mock.calls[0]![1].changes[0]!.price).toBe(minor); }
    if (kind === "conjoint") { fireEvent.click(screen.getByRole("button", { name: "Field the study" })); await waitFor(() => expect(marketing.startConjoint).toHaveBeenCalled()); expect(vi.mocked(marketing.startConjoint).mock.calls[0]![1].prices[0]).toBe(minor); }
  });
}
