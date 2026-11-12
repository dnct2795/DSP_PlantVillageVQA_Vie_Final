export type Row = Record<string, string | number | null>;
export type Question = {
  row_id: string;
  question: string;
  question_type: string;
  question_style?: string;
};
export type SampleImage = {
  image_id: string;
  asset_url: string;
  questions: Question[];
  group: "plantvillage" | "real-world";
  label?: string;
  truth?: { plant: string; disease: string };
  source?: {
    url: string;
    author: string;
    license: string;
    license_url: string;
    changes: string;
  };
};
export type Qualitative = {
  row_id: string;
  image_id: string;
  input_image_id: string;
  condition: string;
  category: string;
  question: string;
  reference: string;
  predictions: string[];
  note: string;
};
export type ResultsData = {
  version: string;
  source_updated_at: string;
  main: Row[];
  question_types: Row[];
  ablation: Row[];
  qualitative: Qualitative[];
  provenance: {
    sources: Record<string, string>;
    benchmark_gpu: string;
    rounding_note: string;
  };
};
export type Runtime = {
  inference_ready: boolean;
  gpu: string | null;
  device_name: string | null;
  state: string;
  message: string | null;
  queue_depth: number;
  execution_device: string;
  uploads_enabled: boolean;
  profile: { dtype: string; use_cache: boolean; max_new_tokens: number };
  provenance: Record<
    string,
    { report_verified?: boolean; adapter_enabled?: boolean }
  >;
};
export type ModelOutput = {
  model_id: string;
  status: string;
  answer?: string;
  generation_ms?: number;
  load_ms?: number;
  model_total_ms?: number;
  peak_allocated_bytes?: number | null;
  error?: { code: string; message: string };
  normalized_exact_match?: boolean;
};
export type Job = {
  job_id: string;
  status: string;
  image_id: string;
  image_source?: "sample" | "upload";
  question_id: string | null;
  question: string;
  outputs: ModelOutput[];
  reference?: string | null;
  expected_answer?: string;
  total_ms?: number;
  queued_ms?: number;
  error?: { code: string; message: string };
  cancel_requested?: boolean;
};

/** Thứ tự chạy của backend là E0 → E1 → E2 → E3. */
export const MODELS = [
  { id: "baseline", short: "E0", name: "Không adapter", label: "Chưa tinh chỉnh · E0" },
  { id: "lora", short: "E1", name: "LoRA", label: "LoRA · E1" },
  { id: "nora_init", short: "E2", name: "NoRA-init", label: "NoRA-init · E2" },
  { id: "nora", short: "E3", name: "NoRA", label: "NoRA · E3" },
] as const;
export type ModelId = (typeof MODELS)[number]["id"];
export const BEST_MODEL: ModelId = "nora";

export const modelOf = (id: string) => MODELS.find((m) => m.id === id);
export const runShort = (run: unknown) => String(run).slice(0, 2);
export const runLabel = (run: unknown) => {
  const e = runShort(run);
  const m = MODELS.find((x) => x.short === e);
  return m ? `${m.short} · ${m.name}` : String(run);
};

/** Định dạng số kiểu Việt Nam: 24.195 và 61,25 %. */
export const num = (value: unknown, digits = 0) =>
  value === null || value === undefined || value === ""
    ? "—"
    : Number(value).toLocaleString("vi-VN", {
        maximumFractionDigits: digits,
        minimumFractionDigits: digits,
      });
export const pct = (value: unknown, digits = 2) =>
  value === null || value === undefined || value === ""
    ? "—"
    : `${num(Number(value) * 100, digits)} %`;
export const seconds = (ms: unknown) =>
  ms === null || ms === undefined ? "—" : `${num(Number(ms) / 1000, 1)} giây`;

export const asset = (id: string) => `/api/assets/${encodeURIComponent(id)}`;

export class APIError extends Error {
  constructor(
    message: string,
    public status: number,
    public code?: string,
  ) {
    super(message);
  }
}
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, init);
  let value: { error?: { message?: string; code?: string } } & T;
  try {
    value = await r.json();
  } catch {
    throw new APIError("Không đọc được phản hồi từ máy chủ.", r.status);
  }
  if (!r.ok)
    throw new APIError(
      value.error?.message ?? "Yêu cầu không thực hiện được.",
      r.status,
      value.error?.code,
    );
  return value;
}
