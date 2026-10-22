// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ComponentProps } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { designShelfTest, type ShelfTestDesign } from "@/shared/api/marketing";
import type { Store } from "@/shared/types/domain";
import { ShelfTestBuilder } from "../ShelfTest";
vi.mock("@/shared/api/client",async original=>({...await original<typeof import("@/shared/api/client")>(),getModels:vi.fn().mockResolvedValue([{ref:"other",label:"Other vision",vision:true}])}));
vi.mock("@/shared/api/marketing",async original=>({...await original<typeof import("@/shared/api/marketing")>(),designShelfTest:vi.fn(),startShelfTest:vi.fn(),previewShelf:vi.fn().mockResolvedValue({face:"N",control:"control.png",test:"test.png",applied:[],warnings:[]})}));
vi.mock("../hooks",()=>({usePackages:()=>({data:[{asset_id:"gold",name:"Gold pack"},{asset_id:"leaf",name:"Leaf pack"}]})}));
const clients:QueryClient[]=[];
afterEach(()=>{cleanup();clients.splice(0).forEach(c=>c.clear());vi.clearAllMocks();});
const rack=(id:string,skus:string[])=>({id,type:"shelf",rack_name:id,rack_desc:"",levels:4,slots:[{block:0,face:"N",level:1,items:skus.map(sku=>({sku,name:sku,price:299,promo:""}))}]});
const store={id:"store",name:"Store",currency:"USD",racks:[rack("drinks",["cola"]),rack("tea",["tea","coffee"])]} as unknown as Store;
const result:ShelfTestDesign={name:"Old shelf test",rack_id:"drinks",target_sku:"cola",changes:[{kind:"price",sku:"cola",price:199,keep_reference:true},{kind:"package",sku:"cola",asset_id:"leaf"},{kind:"promo",sku:"cola",promo:"SALE"}],age_groups:["20s"],rationale:"Old shelf rationale",warnings:[]};
function deferred(){let resolve!:(d:ShelfTestDesign)=>void,reject!:(e:Error)=>void;const promise=new Promise<ShelfTestDesign>((a,b)=>{resolve=a;reject=b;});return{promise,resolve,reject};}
const question=()=>screen.getByLabelText("Question for the shelf test");
const button=()=>screen.getByRole("button",{name:"Draft the test"}) as HTMLButtonElement;
const change=(e:HTMLElement,value:string)=>fireEvent.change(e,{target:{value}});
function mount(){
 const client=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});clients.push(client);
 let props:ComponentProps<typeof ShelfTestBuilder>={projectId:"p",setupId:"s",store,currency:"USD",onStarted:vi.fn(),initial:{name:"My test",setup_id:"s",rack_id:"tea",target_sku:"tea",changes:[{kind:"price",sku:"tea",price:299},{kind:"package",sku:"tea",asset_id:"gold"}],panel:60,age_groups:[],model:""}};
 const draw=()=> <QueryClientProvider client={client}><ShelfTestBuilder {...props}/></QueryClientProvider>;const view=render(draw());
 return{client,change(kind:string){
  if(kind==="question")change(question(),"Would another shelf sign work?");
  if(kind==="shelf")change(screen.getByRole("combobox",{name:"Shelf"}),"drinks");
  if(kind==="product")change(screen.getByRole("combobox",{name:"Product under test"}),"coffee");
  if(kind==="pack")fireEvent.click(screen.getByTitle("Leaf pack"));
  if(kind==="price")change(screen.getByPlaceholderText(/leave empty to keep/),"8.99");
  if(kind==="promo")fireEvent.click(screen.getByRole("button",{name:"NEW"}));
  if(kind==="panel")change(screen.getByLabelText("Respondents"),"90");
  if(kind==="age")fireEvent.click(screen.getByRole("button",{name:"40s"}));
  if(kind==="model")change(screen.getByLabelText("Vision model"),"other");
  if(kind==="name")change(screen.getByPlaceholderText("Test name (optional)"),"My revised test");
  if(kind==="project")props={...props,projectId:"other"};
  if(kind==="layout")props={...props,setupId:"other"};
  if(kind==="currency")props={...props,currency:"KRW"};
  if(kind==="catalog")props={...props,store:{...store,name:"Updated catalog"}};
  view.rerender(draw());
 }};
}
function begin(){change(question(),"Would a different pack stand out?");fireEvent.click(button());}
function values(){return Array.from(document.querySelectorAll<HTMLInputElement|HTMLSelectElement|HTMLTextAreaElement>("input,select,textarea")).map(e=>e.value);}
const changes=["question","shelf","product","pack","price","promo","panel","age","model","name","project","layout","currency","catalog"];
it.each(changes)("preserves newer %s after a late shelf draft",async kind=>{
 const pending=deferred();vi.mocked(designShelfTest).mockReturnValue(pending.promise);const view=mount();await screen.findByRole("option",{name:"Other vision"});begin();await waitFor(()=>expect(designShelfTest).toHaveBeenCalledTimes(1));view.change(kind);const before=values();
 await act(async()=>{pending.resolve(result);await pending.promise;});await waitFor(()=>expect(view.client.isMutating()).toBe(0));expect(values()).toEqual(before);expect(screen.queryByText(/Old shelf rationale/)).toBeNull();
});
it.each(changes)("hides obsolete shelf errors after changing %s",async kind=>{
 const pending=deferred();vi.mocked(designShelfTest).mockReturnValue(pending.promise);const view=mount();await screen.findByRole("option",{name:"Other vision"});begin();await waitFor(()=>expect(designShelfTest).toHaveBeenCalledTimes(1));view.change(kind);
 await act(async()=>pending.reject(new Error("Old shelf failure")));await waitFor(()=>expect(view.client.isMutating()).toBe(0));expect(screen.queryByText("Old shelf failure")).toBeNull();expect(button().disabled).toBe(false);
});
it.each(["price","promo","age","name","project","layout"])("hides accepted shelf rationale after changing %s",async kind=>{
 vi.mocked(designShelfTest).mockResolvedValue(result);const view=mount();begin();await screen.findByText(/Old shelf rationale/);view.change(kind);expect(screen.queryByText(/Old shelf rationale/)).toBeNull();
});
it("keeps the latest shelf draft when responses arrive in reverse order",async()=>{
 const old=deferred(),current=deferred();vi.mocked(designShelfTest).mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise);const view=mount();begin();await waitFor(()=>expect(designShelfTest).toHaveBeenCalledTimes(1));view.change("question");fireEvent.click(button());await waitFor(()=>expect(designShelfTest).toHaveBeenCalledTimes(2));
 await act(async()=>{current.resolve({...result,rationale:"Current shelf rationale",changes:[{kind:"price",sku:"cola",price:599}]});await current.promise;});await screen.findByText(/Current shelf rationale/);
 await act(async()=>{old.resolve(result);await old.promise;});await waitFor(()=>expect(view.client.isMutating()).toBe(0));expect(screen.getByDisplayValue("5.99")).toBeTruthy();expect(screen.getByText(/Current shelf rationale/)).toBeTruthy();
});
it.each(["상품 진열을 비교해줘","比较货架陈列效果","棚の陳列を比較して","Compare shelf signs","Comparar los carteles","Comparer les affiches"])("ignores composition Enter: %s",async text=>{
 mount();change(question(),text);for(const flags of [{isComposing:true},{keyCode:229}])fireEvent.keyDown(question(),{key:"Enter",...flags});await act(async()=>{});expect(designShelfTest).not.toHaveBeenCalled();
});
it("counts full Unicode characters at the question boundaries",()=>{mount();change(question(),"a".repeat(499)+"🛒x");expect((question() as HTMLInputElement).value).toBe("a".repeat(499)+"🛒");change(question(),"🛒".repeat(4));expect(button().disabled).toBe(true);});
