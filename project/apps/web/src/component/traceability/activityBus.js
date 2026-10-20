/** Lets any page tell the global progress dock that a job is starting, before the API confirms it. */
export const ACTIVITY_EVENT = "c4-activity";

export function announceActivity(detail) {
  window.dispatchEvent(new CustomEvent(ACTIVITY_EVENT, { detail }));
}
