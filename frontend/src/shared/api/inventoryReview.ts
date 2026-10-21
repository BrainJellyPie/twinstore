import { BASE } from "./client";
import { apiErrorMessage } from "./errors";

export type InventoryQuantity = "opening_units" | "received_units" | "sold_units" | "returned_units" | "other_in_units" | "other_out_units" | "closing_units";
export type InventoryMoney = "net_sales_minor" | "cogs_minor" | "opening_cost_minor" | "closing_cost_minor";
export type InventoryFlag = "stock_mismatch" | "negative_expected_stock" | "empty_stock_value" | "net_returns" | "zero_supply" | "zero_inventory_cost" | "negative_cogs";
export interface InventoryPeriod { start_date: string; end_date: string; currency: string }
export interface InventoryUpload extends InventoryPeriod { file: File }
export interface InventoryResult {
  inputs: { sku: string } & Record<InventoryQuantity, string> & Record<InventoryMoney, number>;
  expected_closing_units: number; difference_units: number; net_sold_units: number; reconciled: boolean;
  gross_profit_minor: number; average_inventory_cost_minor: number; net_sell_through: number | null;
  inventory_turns: number | null; gmroi: number | null; flags: InventoryFlag[];
}
export interface InventoryReport {
  method: "period-inventory-review-v1"; period: InventoryPeriod; period_days: number; source_sha256: string;
  rows: InventoryResult[];
  totals: { sku_count: number; reconciled_skus: number; net_sales_minor: number; cogs_minor: number;
    gross_profit_minor: number; average_inventory_cost_minor: number; inventory_turns: number | null;
    gmroi: number | null; ratios_withheld: boolean };
  notes: string[];
}
export async function inventoryTemplate(pid: string): Promise<Blob> {
  const response = await fetch(`${BASE}/api/projects/${pid}/inventory-review/template.csv`);
  if (!response.ok) throw new Error(apiErrorMessage(await response.text(), "Inventory template failed"));
  return response.blob();
}
async function requestInventory(pid: string, req: InventoryUpload, csv: boolean): Promise<Response> {
  const body = new FormData(); body.append("file", req.file); body.append("start_date", req.start_date);
  body.append("end_date", req.end_date); body.append("currency", req.currency);
  const response = await fetch(`${BASE}/api/projects/${pid}/inventory-review/${csv ? "export.csv" : "preview"}`, { method: "POST", body });
  if (!response.ok) throw new Error(apiErrorMessage(await response.text(), "Inventory review failed"));
  return response;
}
export async function previewInventory(pid: string, req: InventoryUpload): Promise<InventoryReport> {
  return (await requestInventory(pid, req, false)).json() as Promise<InventoryReport>;
}
export async function exportInventory(pid: string, req: InventoryUpload): Promise<Blob> {
  return (await requestInventory(pid, req, true)).blob();
}
