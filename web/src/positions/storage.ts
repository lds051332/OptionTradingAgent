export const POSITIONS_KEY = "option-desk:positions:v1";
export const POSITION_SETTINGS_KEY = "option-desk:position-settings:v1";
export const POSITION_DRAFT_KEY = "option-desk:position-draft:v1";

export class StorageError extends Error {
  constructor(message = "storage_error") {
    super(message);
    this.name = "StorageError";
  }
}

export function readStorageRaw(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    throw new StorageError();
  }
}

export function writeStorageRaw(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    throw new StorageError();
  }
}

export function removeStorageRaw(key: string): void {
  try {
    window.localStorage.removeItem(key);
  } catch {
    throw new StorageError();
  }
}

export function parseJsonOrThrow(raw: string): unknown {
  try {
    return JSON.parse(raw) as unknown;
  } catch {
    throw new StorageError();
  }
}
