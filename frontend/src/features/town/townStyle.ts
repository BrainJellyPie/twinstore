// Colors and label keys shared by the neighborhood map and its legend.

import type { VenueCategory } from "@/shared/api/client";
import type { MessageKey } from "@/shared/i18n/messages";

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

export const BUILDING_LABELS: Record<string, MessageKey> = {
  apartment: "areaBuildingApartment", house: "areaBuildingHouse", studio: "areaBuildingStudio", dormitory: "areaBuildingDormitory",
  office: "areaBuildingOffice", school: "areaBuildingSchool", university: "areaBuildingUniversity", station: "areaBuildingStation",
  hospital: "areaBuildingHospital", hotel: "areaBuildingHotel", park: "areaBuildingPark", mixed_use: "areaBuildingMixedUse",
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

export const VENUE_LABELS: Record<VenueCategory, MessageKey> = {
  convenience: "areaVenueConvenience", cafe: "areaVenueCafe", bakery: "areaVenueBakery", pharmacy: "areaVenuePharmacy",
  restaurant: "areaVenueRestaurant", fast_food: "areaVenueFastFood", supermarket: "areaVenueSupermarket", bar: "areaVenueBar",
  gym: "areaVenueGym", bookstore: "areaVenueBookstore", academy: "areaVenueAcademy", laundry: "areaVenueLaundry",
  bank: "areaVenueBank", pc_room: "areaVenuePcRoom",
};

export const ROAD_WIDTH: Record<string, number> = { arterial: 16, street: 9, alley: 4.5, footpath: 2.5 };

export const SEGMENT_LABELS: Record<string, MessageKey> = {
  resident: "areaSegmentResident", worker: "areaSegmentWorker", student: "areaSegmentStudent", commuter: "areaSegmentCommuter",
  visitor: "areaSegmentVisitor", linked: "areaSegmentLinked",
};

export const ARCHETYPE_LABELS: Record<string, MessageKey> = {
  residential: "areaArchetypeResidential", university: "areaArchetypeUniversity", business_district: "areaArchetypeBusiness",
  suburban: "areaArchetypeSuburban", station_area: "areaArchetypeStation", tourist: "areaArchetypeTourist", mixed: "areaArchetypeMixed",
};

/** The translated label of a key in one of the maps above, or the raw value when the map does not know it. */
export function labelOf(map: Record<string, MessageKey>, value: string, t: (key: MessageKey) => string): string {
  return Object.prototype.hasOwnProperty.call(map, value) ? t(map[value]!) : value;
}
