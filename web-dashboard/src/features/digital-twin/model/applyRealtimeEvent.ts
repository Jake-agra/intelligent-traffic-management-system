import type { RealtimeEventEnvelope } from "../../../api/types";
import { isDigitalTwinRealtimeEvent } from "./normalizeDigitalTwinState";

export interface RealtimeRefreshDecision {
  shouldRefresh: boolean;
  reason: string;
}

export function shouldRefreshDigitalTwin(
  event: RealtimeEventEnvelope | null,
  intersectionId: string,
  seenEventIds: Set<string>
): RealtimeRefreshDecision {
  if (!event) {
    return { shouldRefresh: false, reason: "no-event" };
  }
  if (seenEventIds.has(event.event_id)) {
    return { shouldRefresh: false, reason: "duplicate" };
  }
  seenEventIds.add(event.event_id);
  if (event.intersection_id !== intersectionId) {
    return { shouldRefresh: false, reason: "other-intersection" };
  }
  if (!isDigitalTwinRealtimeEvent(event)) {
    return { shouldRefresh: false, reason: "unsupported-event" };
  }
  return { shouldRefresh: true, reason: event.event };
}
