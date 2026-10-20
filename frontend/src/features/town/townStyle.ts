// Colors and labels shared by the neighborhood map and its legend.

import type { VenueCategory } from "@/shared/api/client";

export const BUILDING_COLORS: Record<string, string> = {
  apartment: "#93c5fd",
  house: "#fcd34d",
  studio: "#c4b5fd",
  dormitory: "#67e8f9",
  office: "#94a3b8",
  school: "#86efac",
  university: "#4ade80",
  station: "#f472b6",
  hospital: "#fca5a5",
  hotel: "#fdba74",
  park: "#bbf7d0",
  mixed_use: "#a5b4fc",
};

export const BUILDING_LABELS: Record<string, string> = {
  apartment: "Apartments", house: "Houses", studio: "Studios", dormitory: "Dorms", office: "Offices",
  school: "Schools", university: "University", station: "Station", hospital: "Hospital", hotel: "Hotel",
  park: "Park", mixed_use: "Mixed use",
};

export const VENUE_COLORS: Record<VenueCategory, string> = {
  convenience: "#dc2626",
  cafe: "#92400e",
  bakery: "#d97706",
  pharmacy: "#059669",
  restaurant: "#ea580c",
  fast_food: "#f97316",
  supermarket: "#7c3aed",
  bar: "#9333ea",
  gym: "#0891b2",
  bookstore: "#2563eb",
  academy: "#4f46e5",
  laundry: "#0ea5e9",
  bank: "#475569",
  pc_room: "#db2777",
};

export const VENUE_LABELS: Record<VenueCategory, string> = {
  convenience: "Convenience store", cafe: "Café", bakery: "Bakery", pharmacy: "Pharmacy", restaurant: "Restaurant",
  fast_food: "Fast food", supermarket: "Supermarket", bar: "Bar", gym: "Gym", bookstore: "Bookstore",
  academy: "Academy (hagwon)", laundry: "Laundromat", bank: "Bank", pc_room: "PC room",
};

export const ROAD_WIDTH: Record<string, number> = { arterial: 16, street: 9, alley: 4.5, footpath: 2.5 };

export const SEGMENT_LABELS: Record<string, string> = {
  resident: "Residents", worker: "Office workers", student: "Students", commuter: "Commuters",
  visitor: "Visitors", linked: "From nearby venues",
};

export const ARCHETYPE_LABELS: Record<string, string> = {
  residential: "Residential", university: "University district", business_district: "Business district",
  suburban: "Suburban", station_area: "Station area", tourist: "Tourist area", mixed: "Mixed",
};
