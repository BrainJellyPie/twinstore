import { translate } from "./translate";
import type { MessageKey } from "./messages";

/** Keep the key until render so an existing validation error follows language changes. */
export class UserMessageError extends Error {
  constructor(readonly key: MessageKey, readonly values: Record<string, string | number> = {}) {
    super(translate("en", key, values));
    this.name = "UserMessageError";
  }
}
