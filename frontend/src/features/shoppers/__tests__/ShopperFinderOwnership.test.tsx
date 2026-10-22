// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ComponentProps } from "react";
import { afterEach, expect, it, vi } from "vitest";
import * as interview from "@/shared/api/interview";
import type { CustomerResult, Persona, Store } from "@/shared/types/domain";
import { useAssistStore } from "@/stores/assistStore";
import { useSimulationStore } from "@/stores/simulationStore";
import { ShopperPanel } from "../ShopperPanel";
vi.mock("@/shared/api/interview",async original=>({...await original<typeof import("@/shared/api/interview")>(),findShoppers:vi.fn(),listGroups:vi.fn().mockResolvedValue([]),getJourney:vi.fn().mockImplementation(()=>new Promise(()=>{})),askGroup:vi.fn(),suggestGroupQuestions:vi.fn(),deleteGroup:vi.fn()}));
vi.mock("@/shared/api/client",async original=>({...await original<typeof import("@/shared/api/client")>(),getModels:vi.fn().mockResolvedValue([])}));
const clients:QueryClient[]=[];
afterEach(()=>{cleanup();clients.splice(0).forEach(c=>c.clear());vi.clearAllMocks();useAssistStore.setState({pending:null});useSimulationStore.setState({currency:"USD",highlightId:null});});
const customers=["one","two","three"].map(persona_id=>({persona_id,day:1,arrival_time:"15:00:00",leave_time:"15:10:00",total_spent:0,timeline:[]} as unknown as CustomerResult));
const personas=customers.map(c=>({id:c.persona_id,identity:c.persona_id,age_group:"20s",gender:"Female"} as unknown as Persona));
const result:interview.ShopperMatch={label:"Old shoppers",persona_ids:["one","two"],total:3,criteria:["Old criteria"],warnings:[],sort:"spent",near_misses:[]};
function deferred(){let resolve!:(r:interview.ShopperMatch)=>void,reject!:(e:Error)=>void;const promise=new Promise<interview.ShopperMatch>((a,b)=>{resolve=a;reject=b;});return{promise,resolve,reject};}
const input=()=>screen.getByLabelText("Describe shoppers to find");
const button=()=>screen.getByRole("button",{name:"Find"}) as HTMLButtonElement;
function mount(){
 const client=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});clients.push(client);
 let props:ComponentProps<typeof ShopperPanel>={projectId:"p",runId:"r",customers,personas,store:{name:"Store",racks:[]} as unknown as Store};
 const draw=()=> <QueryClientProvider client={client}><ShopperPanel {...props}/></QueryClientProvider>;const view=render(draw());
 return{client,async change(kind:string){await act(async()=>{
  if(kind==="description")fireEvent.change(input(),{target:{value:"Find my newer shoppers"}});
  if(kind==="project")props={...props,projectId:"other"};
  if(kind==="run")props={...props,runId:"other"};
  if(kind==="customers")props={...props,customers:customers.slice(1)};
  if(kind==="personas")props={...props,personas:personas.map(p=>({...p,identity:p.identity+" changed"}))};
  if(kind==="store")props={...props,store:{...props.store,name:"Other store"}};
  if(kind==="currency")useSimulationStore.setState({currency:"JPY"});
  view.rerender(draw());
 });}};
}
function begin(text="Find afternoon shoppers"){fireEvent.change(input(),{target:{value:text}});fireEvent.click(button());}
const changes=["description","project","run","customers","personas","store","currency"];
it.each(changes)("ignores a search reply after changing %s",async kind=>{
 const pending=deferred();vi.mocked(interview.findShoppers).mockReturnValue(pending.promise);const view=mount();begin();await waitFor(()=>expect(interview.findShoppers).toHaveBeenCalledTimes(1));await view.change(kind);
 await act(async()=>{pending.resolve(result);await pending.promise;});await waitFor(()=>expect(view.client.isMutating()).toBe(0));expect(screen.queryByRole("region",{name:"Found shoppers"})).toBeNull();expect(screen.queryByText(result.label)).toBeNull();
});
it.each(changes)("hides a stale search error after changing %s",async kind=>{
 const pending=deferred();vi.mocked(interview.findShoppers).mockReturnValue(pending.promise);const view=mount();begin();await waitFor(()=>expect(interview.findShoppers).toHaveBeenCalledTimes(1));await view.change(kind);
 await act(async()=>pending.reject(new Error("Old search error")));await waitFor(()=>expect(view.client.isMutating()).toBe(0));expect(screen.queryByText("Old search error")).toBeNull();
});
it.each(changes)("retires accepted matches after changing %s",async kind=>{
 vi.mocked(interview.findShoppers).mockResolvedValue(result);const view=mount();begin();await screen.findByRole("region",{name:"Found shoppers"});await view.change(kind);expect(screen.queryByRole("region",{name:"Found shoppers"})).toBeNull();
});
it("does not restore a cleared group when its repeat search arrives",async()=>{
 const pending=deferred();vi.mocked(interview.findShoppers).mockResolvedValueOnce(result).mockReturnValueOnce(pending.promise);const view=mount();begin();await screen.findByRole("region",{name:"Found shoppers"});fireEvent.click(button());await waitFor(()=>expect(interview.findShoppers).toHaveBeenCalledTimes(2));fireEvent.click(screen.getByRole("button",{name:"Clear the found shoppers"}));await act(async()=>{pending.resolve(result);await pending.promise;});await waitFor(()=>expect(view.client.isMutating()).toBe(0));expect(screen.queryByRole("region",{name:"Found shoppers"})).toBeNull();
});
it("keeps the latest explicitly routed search when replies arrive in reverse",async()=>{
 const old=deferred(),current=deferred();vi.mocked(interview.findShoppers).mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise);const view=mount();begin();await waitFor(()=>expect(interview.findShoppers).toHaveBeenCalledTimes(1));
 await act(async()=>useAssistStore.getState().send({projectId:"p",destination:"find_shoppers",text:"Find the current shoppers"}));await waitFor(()=>expect(interview.findShoppers).toHaveBeenCalledTimes(2));await act(async()=>{current.resolve({...result,label:"Current shoppers",persona_ids:["three"]});await current.promise;});await screen.findByText("Current shoppers");await act(async()=>{old.resolve(result);await old.promise;});await waitFor(()=>expect(view.client.isMutating()).toBe(0));expect(screen.getByText("Current shoppers")).toBeTruthy();expect(screen.queryByText("Old shoppers")).toBeNull();
});
it.each(["project","run"])("returns to the current shopper list when %s changes during a group interview",async kind=>{
 const view=mount();fireEvent.click(screen.getByRole("button",{name:/Group interview.*Ask many shoppers/}));await screen.findByLabelText("Question");await view.change(kind);expect(screen.queryByLabelText("Question")).toBeNull();expect(input()).toBeTruthy();
});
it.each(["project","run"])("clears selected shopper detail when %s changes",async kind=>{
 const view=mount();fireEvent.click(screen.getByRole("button",{name:/one.*Day 1/}));await screen.findByRole("button",{name:"All shoppers"});await view.change(kind);expect(input()).toBeTruthy();
});
it.each(["학생쇼퍼찾아줘","查找下午的顾客","午後の買い物客を探して","Find late shoppers","Buscar compradores","Chercher des clients"])("ignores composition Enter for %s",async text=>{
 mount();fireEvent.change(input(),{target:{value:text}});for(const flags of [{isComposing:true},{keyCode:229}])fireEvent.keyDown(input(),{key:"Enter",...flags});await act(async()=>{});expect(interview.findShoppers).not.toHaveBeenCalled();
});
it.each(["detail","group"])("opens the found list when a new search is routed from %s",async kind=>{
 vi.mocked(interview.findShoppers).mockResolvedValue(result);mount();
 fireEvent.click(screen.getByRole("button",{name:kind==="group"?/Group interview.*Ask many shoppers/:/one.*Day 1/}));
 await act(async()=>useAssistStore.getState().send({projectId:"p",destination:"find_shoppers",text:"Find new shoppers now"}));
 await screen.findByRole("region",{name:"Found shoppers"});expect(input()).toBeTruthy();expect(interview.askGroup).not.toHaveBeenCalled();
});
