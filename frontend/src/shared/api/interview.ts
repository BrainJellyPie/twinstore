// One shopper's journey through a run and a conversation with that shopper afterwards. Mirrors backend
// domain/interview.py — keep in sync.

import type { Persona } from "@/shared/types/domain";

import { BASE } from "./client";
import { apiErrorMessage } from "./errors";

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: { "Content-Type": "application/json" }, ...init });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(apiErrorMessage(body, `${res.status} ${res.statusText}`));
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
  sees_products?: boolean;
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
export interface Interview {
  run_id: string;
  persona_id: string;
  model: string;
  messages: InterviewMessage[];
  /** Model-written next questions, written after `suggested_after` messages (-1: none yet). */
  suggestions?: string[];
  suggested_after?: number;
}

const base = (pid: string, runId: string, sid: string) => `/api/projects/${pid}/runs/${runId}/shoppers/${encodeURIComponent(sid)}`;

export const getJourney = (pid: string, runId: string, sid: string, signal?: AbortSignal) =>
  fetchJson<Journey>(`${base(pid, runId, sid)}/journey`, { signal });
export const getInterview = (pid: string, runId: string, sid: string, signal?: AbortSignal) =>
  fetchJson<Interview>(`${base(pid, runId, sid)}/interview`, { signal });
export const askShopper = (pid: string, runId: string, sid: string, question: string, model: string) =>
  fetchJson<Interview>(`${base(pid, runId, sid)}/interview`, { method: "POST", body: JSON.stringify({ question, model }) });
export const suggestQuestions = (pid: string, runId: string, sid: string, model: string, signal?: AbortSignal) =>
  fetchJson<Interview>(`${base(pid, runId, sid)}/interview/suggestions`, { method: "POST", body: JSON.stringify({ model }), signal });
export const clearInterview = (pid: string, runId: string, sid: string) =>
  fetchJson<void>(`${base(pid, runId, sid)}/interview`, { method: "DELETE" });

export const shelfFaceUrl = (pid: string, runId: string, rackId: string, face: string) =>
  `${BASE}/api/projects/${pid}/runs/${runId}/racks/${encodeURIComponent(rackId)}/faces/${face}.png`;

export type GroupSegment = "all" | "empty_handed" | "buyers" | "impulse" | "top_spenders";

export interface GroupAnswer {
  persona_id: string;
  identity: string;
  age_group: string;
  gender: string;
  spent: number;
  units: number;
  answer: string;
  steps: number[];
  theme: number;
  error: string;
}

export interface Theme { label: string; count: number; share: number }

export interface GroupInterview {
  group_id: string;
  run_id: string;
  question: string;
  segment: GroupSegment;
  model: string;
  created_at: string;
  answers: GroupAnswer[];
  themes: Theme[];
  errors: number;
}

export const askGroup = (pid: string, runId: string, body: { question: string; segment: GroupSegment; size: number; model: string; persona_ids?: string[] }) =>
  fetchJson<GroupInterview>(`/api/projects/${pid}/runs/${runId}/group-interviews`, { method: "POST", body: JSON.stringify(body) });
export const listGroups = (pid: string, runId: string, signal?: AbortSignal) =>
  fetchJson<GroupInterview[]>(`/api/projects/${pid}/runs/${runId}/group-interviews`, { signal });
export const deleteGroup = (pid: string, runId: string, gid: string) =>
  fetchJson<void>(`/api/projects/${pid}/runs/${runId}/group-interviews/${gid}`, { method: "DELETE" });

export const interviewKeys = {
  groups: (pid: string, runId: string) => ["projects", pid, "runs", runId, "group-interviews"] as const,
  journey: (pid: string, runId: string, sid: string) => ["projects", pid, "runs", runId, "shoppers", sid, "journey"] as const,
  interview: (pid: string, runId: string, sid: string) => ["projects", pid, "runs", runId, "shoppers", sid, "interview"] as const,
  suggestions: (pid: string, runId: string, sid: string, after: number, model: string) =>
    ["projects", pid, "runs", runId, "shoppers", sid, "interview", "suggestions", after, model] as const,
};
