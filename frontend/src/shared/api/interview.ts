// One shopper's journey through a run and a conversation with that shopper afterwards. Mirrors backend
// domain/interview.py — keep in sync.

import type { Persona } from "@/shared/types/domain";

import { BASE } from "./client";

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: { "Content-Type": "application/json" }, ...init });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    let detail = body;
    try { detail = (JSON.parse(body) as { detail?: string }).detail ?? body; } catch { /* plain text */ }
    throw new Error(detail || `${res.status} ${res.statusText}`);
  }
  return (res.status === 204 ? undefined : res.json()) as Promise<T>;
}

export type JourneyAction = "enter" | "move" | "browse" | "buy" | "pay" | "wander" | "exit";

export interface JourneyStep {
  index: number;
  time: string;
  elapsed_sec: number;
  action: JourneyAction;
  rack_id: string;
  rack: string;
  face: string;
  product_sku: string;
  product_name: string;
  price: number;
  quantity: number;
  origin: string;
  thought: string;
  duration: number;
  x: number;
  y: number;
}

export interface ShelfItem { sku: string; name: string; price: number; regular_price: number; promo: string }

export interface Journey {
  run_id: string;
  persona: Persona;
  day: number;
  arrival_time: string;
  leave_time: string;
  engine_type: string;
  currency: string;
  total_spent: number;
  units: number;
  steps: JourneyStep[];
  path: [number, number, number][];
  shelves: Record<string, ShelfItem[]>;
}

export interface InterviewMessage { role: "interviewer" | "shopper"; text: string; steps: number[]; created_at: string }
export interface Interview { run_id: string; persona_id: string; model: string; messages: InterviewMessage[] }

const base = (pid: string, runId: string, sid: string) => `/api/projects/${pid}/runs/${runId}/shoppers/${encodeURIComponent(sid)}`;

export const getJourney = (pid: string, runId: string, sid: string, signal?: AbortSignal) =>
  fetchJson<Journey>(`${base(pid, runId, sid)}/journey`, { signal });
export const getInterview = (pid: string, runId: string, sid: string, signal?: AbortSignal) =>
  fetchJson<Interview>(`${base(pid, runId, sid)}/interview`, { signal });
export const askShopper = (pid: string, runId: string, sid: string, question: string, model: string) =>
  fetchJson<Interview>(`${base(pid, runId, sid)}/interview`, { method: "POST", body: JSON.stringify({ question, model }) });
export const clearInterview = (pid: string, runId: string, sid: string) =>
  fetchJson<void>(`${base(pid, runId, sid)}/interview`, { method: "DELETE" });

export const interviewKeys = {
  journey: (pid: string, runId: string, sid: string) => ["projects", pid, "runs", runId, "shoppers", sid, "journey"] as const,
  interview: (pid: string, runId: string, sid: string) => ["projects", pid, "runs", runId, "shoppers", sid, "interview"] as const,
};
