import type { CustomerResult, TimelineEvent } from "@/shared/types/domain";
import type { SkuSales } from "./playback";
import { parseTimeToSeconds } from "./playback";

export interface ScheduledEvent {
  time: number;
  customerId: string;
  action: string;
  event: TimelineEvent;
  arrivalSec: number;
}

export interface RackMetric {
  rackId: string;
  revenue: number;
  visitors: number;
  // Carried across snapshot/loadSnapshot to restore the unique-visitor set.
  // The UI consumes only visitors (size).
  visitorIds: string[];
}

export interface MetricsSnapshot {
  entered: number;
  exited: number;
  inStore: number;
  revenue: number;
  impulseRevenue: number;
  paidCount: number;
  skuSales: SkuSales[];
  rackMetrics: RackMetric[];
}

export function buildEventQueue(customers: CustomerResult[]): ScheduledEvent[] {
  const queue: ScheduledEvent[] = [];

  for (const c of customers) {
    const arrivalSec = parseTimeToSeconds(c.arrival_time);
    for (const ev of c.timeline) {
      queue.push({
        time: arrivalSec + ev.elapsed_sec,
        customerId: c.persona_id,
        action: ev.action,
        event: ev,
        arrivalSec,
      });
    }
  }

  queue.sort((a, b) => a.time - b.time || a.action.localeCompare(b.action));
  return queue;
}

export function buildDayCheckpoints(
  customers: CustomerResult[],
  availableDays: number[],
): Map<number, MetricsSnapshot> {
  const checkpoints = new Map<number, MetricsSnapshot>();
  const acc = new MetricsAccumulator();

  checkpoints.set(availableDays[0] ?? 1, acc.snapshot());

  for (let i = 0; i < availableDays.length; i++) {
    const day = availableDays[i]!;
    const dayCustomers = customers.filter((c) => c.day === day);
    const queue = buildEventQueue(dayCustomers);
    for (const ev of queue) acc.processEvent(ev);
    if (i < availableDays.length - 1) {
      checkpoints.set(availableDays[i + 1]!, acc.snapshot());
    }
  }

  return checkpoints;
}

export class MetricsAccumulator {
  entered = 0;
  exited = 0;
  inStore = 0;
  revenue = 0;
  impulseRevenue = 0;
  paidCount = 0;
  private skuMap = new Map<string, SkuSales>();
  private carts = new Map<
    string,
    { sku: string; name: string; price: number; quantity: number; impulse: boolean; rackId: string }[]
  >();
  private arrived = new Set<string>();
  private rackRevenue = new Map<string, number>();
  private rackVisitors = new Map<string, Set<string>>();

  processEvent(ev: ScheduledEvent): void {
    if (!this.arrived.has(ev.customerId) && ev.event.elapsed_sec >= 0) {
      this.arrived.add(ev.customerId);
      this.entered++;
      this.inStore++;
    }

    if (ev.action === "buy" && ev.event.product_sku && ev.event.price > 0) {
      const cart = this.carts.get(ev.customerId) ?? [];
      cart.push({
        sku: ev.event.product_sku,
        name: ev.event.product_name,
        price: ev.event.price,
        quantity: ev.event.quantity ?? 1,
        impulse: ev.event.origin === "impulse",
        rackId: ev.event.target_rack,
      });
      this.carts.set(ev.customerId, cart);
    }

    if (ev.action === "pay") {
      const cart = this.carts.get(ev.customerId) ?? [];
      for (const item of cart) {
        const line = item.price * item.quantity;
        this.revenue += line;
        if (item.impulse) this.impulseRevenue += line;
        const existing = this.skuMap.get(item.sku);
        if (existing) {
          existing.quantity += item.quantity;
          existing.revenue += line;
        } else {
          this.skuMap.set(item.sku, {
            sku: item.sku,
            name: item.name,
            quantity: item.quantity,
            revenue: line,
            rackId: item.rackId,
          });
        }
        if (item.rackId) {
          this.rackRevenue.set(item.rackId, (this.rackRevenue.get(item.rackId) ?? 0) + line);
          const visitors = this.rackVisitors.get(item.rackId);
          if (visitors) visitors.add(ev.customerId);
          else this.rackVisitors.set(item.rackId, new Set([ev.customerId]));
        }
      }
      this.paidCount++;
      this.carts.set(ev.customerId, []);
    }

    if (ev.action === "exit") {
      this.inStore = Math.max(0, this.inStore - 1);
      this.exited++;
    }
  }

  snapshot(): MetricsSnapshot {
    const allRackIds = new Set([...this.rackRevenue.keys(), ...this.rackVisitors.keys()]);
    return {
      entered: this.entered,
      exited: this.exited,
      inStore: this.inStore,
      revenue: this.revenue,
      impulseRevenue: this.impulseRevenue,
      paidCount: this.paidCount,
      skuSales: [...this.skuMap.values()].sort((a, b) => b.revenue - a.revenue),
      rackMetrics: [...allRackIds].map((rackId) => {
        const visitors = this.rackVisitors.get(rackId);
        return {
          rackId,
          revenue: this.rackRevenue.get(rackId) ?? 0,
          visitors: visitors?.size ?? 0,
          visitorIds: visitors ? [...visitors] : [],
        };
      }).sort((a, b) => b.revenue - a.revenue),
    };
  }

  loadSnapshot(snap: MetricsSnapshot): void {
    this.entered = snap.entered;
    this.exited = snap.exited;
    this.inStore = snap.inStore;
    this.revenue = snap.revenue;
    this.impulseRevenue = snap.impulseRevenue;
    this.paidCount = snap.paidCount;
    this.skuMap.clear();
    for (const s of snap.skuSales) this.skuMap.set(s.sku, { ...s });
    this.rackRevenue.clear();
    this.rackVisitors.clear();
    for (const r of snap.rackMetrics) {
      this.rackRevenue.set(r.rackId, r.revenue);
      this.rackVisitors.set(r.rackId, new Set(r.visitorIds));
    }
    this.carts.clear();
    this.arrived.clear();
  }

  reset(): void {
    this.entered = 0;
    this.exited = 0;
    this.inStore = 0;
    this.revenue = 0;
    this.impulseRevenue = 0;
    this.paidCount = 0;
    this.skuMap.clear();
    this.carts.clear();
    this.arrived.clear();
    this.rackRevenue.clear();
    this.rackVisitors.clear();
  }
}
