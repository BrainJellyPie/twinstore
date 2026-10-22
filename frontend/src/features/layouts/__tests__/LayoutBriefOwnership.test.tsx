// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useLayoutEffect, useState } from "react";
import { afterEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import { useLocale } from "@/shared/i18n/i18n";
import { LayoutBriefField } from "../components/LayoutBriefField";
import { DEFAULT_TEMPLATE_CHOICE, type TemplateChoice } from "../templateOptions";
vi.mock("@/shared/api/client", async original => ({ ...await original<typeof import("@/shared/api/client")>(), readLayoutBrief: vi.fn() }));
const clients: QueryClient[] = [];
afterEach(() => { cleanup(); clients.splice(0).forEach(c => c.clear()); vi.clearAllMocks(); useLocale.setState({ locale: "en" }); });
const result: api.BriefReading = { options: { width: 18, design_colors: { wall: "#112233" } }, applied: ["Width: 18 cells"], not_expressible: [], warnings: [], rationale: "Old brief rationale" };
function deferred() { let resolve!: (r: api.BriefReading) => void, reject!: (e: Error) => void; const promise = new Promise<api.BriefReading>((a,b) => { resolve=a; reject=b; }); return { promise, resolve, reject }; }
const input = () => screen.getByLabelText("Additional design brief");
const button = () => screen.getByRole("button", { name: "Apply to the options" }) as HTMLButtonElement;
function mount() {
 const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } }); clients.push(client);
 let latest = { ...DEFAULT_TEMPLATE_CHOICE, requirements: "Make a spacious store", width: 12 };
 let change!: (patch: Partial<TemplateChoice>) => void;
 const applied = vi.fn();
 function Harness() { const [value,setValue] = useState<TemplateChoice>(latest); useLayoutEffect(()=>{latest=value as typeof latest;change=patch=>setValue(v=>({...v,...patch}));},[value]); return <LayoutBriefField value={value} onApply={patch=>{applied(patch);change(patch);}} onBriefChange={requirements=>change({requirements})}/>; }
 const view=render(<QueryClientProvider client={client}><Harness/></QueryClientProvider>);
 return { client, applied, unmount:view.unmount, value:()=>latest, change:async(patch:Partial<TemplateChoice>)=>act(async()=>change(patch)) };
}
const changes: [string, Partial<TemplateChoice>][] = [
 ["brief",{requirements:"Use my revised plan"}], ["format",{templateId:"supermarket"}], ["source",{sourceSetupId:"other"}],
 ["currency",{currency:"JPY"}], ["seed",{seed:2}], ["size",{width:24}], ["colors",{design_colors:{wall:"#ffffff",floor:"#000000"}}],
 ["density",{density:"dense"}], ["excluded categories",{excluded_categories:["water_sports"]}], ["reserved areas",{reserved_areas:[{label:"Desk",x:1,y:1,width:2,height:2}]}],
];
it.each(changes)("preserves newer %s after a late reading",async(_label,patch)=>{
 const pending=deferred();vi.mocked(api.readLayoutBrief).mockReturnValue(pending.promise);const view=mount();fireEvent.click(button());await waitFor(()=>expect(api.readLayoutBrief).toHaveBeenCalledTimes(1));await view.change(patch);const before=view.value();
 await act(async()=>{pending.resolve(result);await pending.promise;});await waitFor(()=>expect(view.client.isMutating()).toBe(0));expect(view.applied).not.toHaveBeenCalled();expect(view.value()).toEqual(before);expect(screen.queryByText(result.rationale)).toBeNull();expect(button().disabled).toBe(false);
});
it.each(changes)("hides obsolete reading errors after changing %s",async(_label,patch)=>{
 const pending=deferred();vi.mocked(api.readLayoutBrief).mockReturnValue(pending.promise);const view=mount();fireEvent.click(button());await waitFor(()=>expect(api.readLayoutBrief).toHaveBeenCalledTimes(1));await view.change(patch);
 await act(async()=>pending.reject(new Error("Old brief failure")));await waitFor(()=>expect(view.client.isMutating()).toBe(0));expect(screen.queryByText("Old brief failure")).toBeNull();expect(button().disabled).toBe(false);
});
it.each(changes)("retires accepted reading after changing %s",async(_label,patch)=>{
 vi.mocked(api.readLayoutBrief).mockResolvedValue(result);const view=mount();fireEvent.click(button());await screen.findByText(result.rationale);await view.change(patch);expect(screen.queryByText(result.rationale)).toBeNull();
});
it("does not apply an old reply after the field is unmounted",async()=>{
 const pending=deferred();vi.mocked(api.readLayoutBrief).mockReturnValue(pending.promise);const view=mount();fireEvent.click(button());await waitFor(()=>expect(api.readLayoutBrief).toHaveBeenCalledTimes(1));view.unmount();await act(async()=>{pending.resolve(result);await pending.promise;});expect(view.applied).not.toHaveBeenCalled();
});
it("keeps whole Unicode characters at the brief limit",()=>{mount();fireEvent.change(input(),{target:{value:"a".repeat(1999)+"🛒x"}});expect((input() as HTMLTextAreaElement).value).toBe("a".repeat(1999)+"🛒");});
it("can submit new options while an older request is pending and ignore its late reply",async()=>{
 const old=deferred(),current=deferred();vi.mocked(api.readLayoutBrief).mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise);const view=mount();fireEvent.click(button());await waitFor(()=>expect(api.readLayoutBrief).toHaveBeenCalledTimes(1));await view.change({width:24});fireEvent.click(button());await waitFor(()=>expect(api.readLayoutBrief).toHaveBeenCalledTimes(2));
 await act(async()=>{current.resolve({...result,options:{width:30},rationale:"Current brief"});await current.promise;});await screen.findByText("Current brief");await act(async()=>{old.resolve(result);await old.promise;});await waitFor(()=>expect(view.client.isMutating()).toBe(0));expect(view.value().width).toBe(30);expect(view.applied).toHaveBeenCalledTimes(1);
});

it.each([
 ["en", "Additional design brief", "Apply to the options"],
 ["ko", "추가 설계 요구사항", "설정에 반영"],
 ["zh", "补充设计要求", "应用到设置"],
 ["ja", "追加の設計要件", "設定に反映"],
 ["es", "Requisitos de diseño adicionales", "Aplicar a los ajustes"],
 ["fr", "Consignes de conception supplémentaires", "Appliquer aux réglages"],
] as const)("reads a brief with accessible translated controls in %s", async (locale,label,action) => {
 useLocale.setState({locale});vi.mocked(api.readLayoutBrief).mockResolvedValue(result);mount();
 fireEvent.change(screen.getByLabelText(label),{target:{value:"a".repeat(1999)+"🛒x"}});
 fireEvent.click(screen.getByRole("button",{name:action}));await screen.findByText(result.rationale);
 expect(vi.mocked(api.readLayoutBrief).mock.calls[0]![1].brief).toBe("a".repeat(1999)+"🛒");
});
