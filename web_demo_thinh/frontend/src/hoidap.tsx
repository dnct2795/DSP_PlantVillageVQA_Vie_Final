import { useEffect, useRef, useState } from "react";
import {
  api,
  APIError,
  BEST_MODEL,
  MODELS,
  modelOf,
  num,
  seconds,
  type Job,
  type ModelId,
  type ModelOutput,
  type ResultsData,
  type Runtime,
  type SampleImage,
} from "./types";
import { CHIPS, qtypeVi } from "./questions";
import { metaOf } from "./samples_meta";
import {
  ArrowIcon,
  Card,
  CheckIcon,
  ClockIcon,
  CloseIcon,
  InfoIcon,
  Notice,
  SpinnerIcon,
  Stat,
  StepTitle,
  UploadIcon,
  Warning,
} from "./components";

const TERMINAL = ["succeeded", "partial", "failed", "cancelled"];
const MAX_UPLOAD = 10 * 1024 * 1024;
const STATUS_VI: Record<string, string> = {
  queued: "Đang xếp hàng",
  running: "Đang chạy",
  succeeded: "Xong",
  partial: "Xong một phần",
  failed: "Lỗi",
  cancelled: "Đã huỷ",
  pending: "Chờ đến lượt",
  loading: "Đang nạp mô hình",
  generating: "Đang trả lời…",
};
const COMPARE_ORDER: ModelId[] = ["lora", "nora_init", "baseline"];
const ALL_MODELS: ModelId[] = ["baseline", "lora", "nora_init", "nora"];

type Upload = { file: File; url: string; name: string };

export default function HoiDap({
  samples,
  results,
  runtime,
  target,
  active,
}: {
  samples: SampleImage[];
  results: ResultsData;
  runtime: Runtime | null;
  target: string | null;
  active: boolean;
}) {
  const initial = samples.find((s) => s.image_id === "image_046993.JPG") ?? samples[0];
  const [imageId, setImageId] = useState(initial.image_id);
  const [upload, setUpload] = useState<Upload | null>(null);
  const [questionId, setQuestionId] = useState<string | null>(initial.questions[0]?.row_id ?? null);
  const [question, setQuestion] = useState(initial.questions[0]?.question ?? "");
  const [chip, setChip] = useState<string | null>(initial.questions[0]?.question_type ?? null);
  const [mode, setMode] = useState<"all" | "best">("all");
  const [job, setJob] = useState<Job | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [pollError, setPollError] = useState("");
  const [revision, setRevision] = useState(0);
  const [jobRevision, setJobRevision] = useState(0);
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const requestRef = useRef(false);

  const sample = samples.find((s) => s.image_id === imageId) ?? initial;
  const meta = metaOf(sample.image_id);
  const busy = pending || !!(job && !TERMINAL.includes(job.status));
  const stale = !!job && revision !== jobRevision;
  const uploadsEnabled = runtime?.uploads_enabled ?? false;
  const modelIds: ModelId[] = mode === "all" ? ALL_MODELS : [BEST_MODEL];

  const plantvillage = samples.filter((s) => s.group === "plantvillage");
  const realWorld = samples.filter((s) => s.group === "real-world");
  const datasetCount = Number(results.main[0]?.dataset_count ?? 0);
  const imageCount = Number(results.main[0]?.dataset_unique_images ?? 0);
  const qtypeCount = new Set(results.question_types.map((r) => r.question_type)).size;

  const bump = () => setRevision((r) => r + 1);

  const chooseSample = (s: SampleImage, row?: string) => {
    if (upload) {
      URL.revokeObjectURL(upload.url);
      setUpload(null);
    }
    const q = s.questions.find((x) => x.row_id === row) ?? s.questions[0];
    setImageId(s.image_id);
    setQuestionId(q?.row_id ?? null);
    setQuestion(q?.question ?? "");
    setChip(q?.question_type ?? null);
    bump();
  };

  useEffect(() => {
    if (!target) return;
    const s = samples.find((x) => x.questions.some((q) => q.row_id === target));
    if (s) chooseSample(s, target);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target]);

  useEffect(
    () => () => {
      if (upload) URL.revokeObjectURL(upload.url);
    },
    [upload],
  );

  /* Thăm dò trạng thái lượt hỏi */
  useEffect(() => {
    if (!job || TERMINAL.includes(job.status)) return;
    let alive = true;
    const timer = setInterval(
      () =>
        api<Job>(`/api/inferences/${job.job_id}`)
          .then((j) => {
            if (alive) {
              setJob(j);
              setPollError("");
            }
          })
          .catch((e) => {
            if (!alive) return;
            setPollError((e as Error).message);
            if (e instanceof APIError && e.status === 404)
              setJob((prev) =>
                prev
                  ? { ...prev, status: "failed", error: { code: "JOB_NOT_FOUND", message: e.message } }
                  : null,
              );
          }),
      1000,
    );
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [job?.job_id, job?.status]);

  /* Chip câu hỏi: ưu tiên câu gốc của ảnh đang chọn, nếu không có thì điền câu mẫu theo dạng */
  const pickChip = (type: string) => {
    const own = !upload ? sample.questions.find((q) => q.question_type === type) : undefined;
    const def = CHIPS.find((c) => c.type === type)!;
    if (own) {
      setQuestionId(own.row_id);
      setQuestion(own.question);
    } else {
      setQuestionId(null);
      setQuestion(def.template(upload ? undefined : meta.plant, upload ? undefined : meta.disease));
    }
    setChip(type);
    bump();
  };

  const acceptFile = (file: File | undefined) => {
    setError("");
    if (!file) return;
    if (!["image/jpeg", "image/png"].includes(file.type)) {
      setError("Chỉ nhận ảnh JPG hoặc PNG.");
      return;
    }
    if (file.size > MAX_UPLOAD) {
      setError(`Ảnh vượt quá 10 MB (ảnh của bạn ${num(file.size / 1024 / 1024, 1)} MB).`);
      return;
    }
    if (upload) URL.revokeObjectURL(upload.url);
    setUpload({ file, url: URL.createObjectURL(file), name: file.name });
    setQuestionId(null);
    if (chip) {
      const def = CHIPS.find((c) => c.type === chip);
      if (def) setQuestion(def.template());
    }
    bump();
  };

  const clearUpload = () => {
    if (upload) URL.revokeObjectURL(upload.url);
    setUpload(null);
    chooseSample(sample);
  };

  const run = async () => {
    if (requestRef.current || busy) return;
    requestRef.current = true;
    setPending(true);
    setError("");
    setPollError("");
    const captured = revision;
    try {
      let image_id = imageId;
      if (upload) {
        const form = new FormData();
        form.append("file", upload.file, upload.name);
        const up = await api<{ image_id: string }>("/api/uploads", { method: "POST", body: form });
        image_id = up.image_id;
      }
      const useCanonical = !upload && !!questionId;
      const created = await api<{ job_id: string }>("/api/inferences", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          image_id,
          question_id: useCanonical ? questionId : null,
          ...(useCanonical ? {} : { question: question.trim() }),
          model_ids: modelIds,
        }),
      });
      setJobRevision(captured);
      setJob({
        job_id: created.job_id,
        status: "queued",
        image_id,
        image_source: upload ? "upload" : "sample",
        question_id: useCanonical ? questionId : null,
        question: question.trim(),
        outputs: MODELS.filter((m) => modelIds.includes(m.id)).map((m) => ({
          model_id: m.id,
          status: "pending",
        })),
      });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPending(false);
      requestRef.current = false;
    }
  };

  const cancel = async () => {
    if (!job) return;
    try {
      setJob(await api<Job>(`/api/inferences/${job.job_id}`, { method: "DELETE" }));
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const best = job?.outputs.find((o) => o.model_id === BEST_MODEL) ?? job?.outputs[job.outputs.length - 1];
  const others = job
    ? COMPARE_ORDER.map((id) => job.outputs.find((o) => o.model_id === id)).filter(
        (o): o is ModelOutput => !!o && o.model_id !== best?.model_id,
      )
    : [];
  const activeChip = CHIPS.find((c) => c.type === chip);
  const jobTruth = job?.image_source === "sample" ? samples.find((s) => s.image_id === job.image_id)?.truth : undefined;

  return (
    <>
      <section className="hero">
        <div className="container">
          <div className="hero-copy">
            <h1>
              Thắc mắc bệnh cây trồng,
              <br />
              hãy hỏi ngay.
            </h1>
            <p>
              Chọn ảnh lá có sẵn hoặc tải ảnh của bạn lên, chọn câu hỏi gợi ý hoặc tự gõ, rồi xem bốn
              phiên bản mô hình trả lời và so với đáp án đúng.
            </p>
          </div>
          <div className="hero-stats" aria-label="Số liệu bộ dữ liệu">
            <Stat value={num(datasetCount)} label="cặp hỏi–đáp" />
            <Stat value={num(imageCount)} label="ảnh lá cây" />
            <Stat value={num(qtypeCount)} label="dạng câu hỏi" />
          </div>
        </div>
      </section>

      <main className="page two-col">
        {/* ----- Bước 1 ----- */}
        <Card className="col-left" aria-labelledby="buoc1">
          <StepTitle step={1} id="buoc1">
            Chọn ảnh lá cây
          </StepTitle>
          <div className="selected-image">
            <img
              src={upload ? upload.url : sample.asset_url}
              alt={upload ? `Ảnh bạn tải lên: ${upload.name}` : `Ảnh mẫu: ${meta.label}`}
            />
            <span className="tag">
              {upload ? `Ảnh của bạn · ${upload.name}` : `Ảnh mẫu · ${meta.label}`}
            </span>
          </div>
          {!upload && sample.truth && (
            <p className="image-credit">
              Đáp án đúng để so sánh: <strong>{sample.truth.plant.charAt(0).toUpperCase() + sample.truth.plant.slice(1)} · {sample.truth.disease}</strong>
            </p>
          )}
          {!upload && sample.source && (
            <p className="image-credit">
              Ảnh ngoài vườn ·{" "}
              <a href={sample.source.url} target="_blank" rel="noreferrer">
                Wikimedia Commons
              </a>{" "}
              · {sample.source.author} ·{" "}
              <a href={sample.source.license_url} target="_blank" rel="noreferrer">
                {sample.source.license}
              </a>
            </p>
          )}

          <label
            className={`upload ${dragging ? "is-dragging" : ""} ${uploadsEnabled ? "" : "is-disabled"}`}
            onDragOver={(e) => {
              e.preventDefault();
              if (uploadsEnabled) setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragging(false);
              if (uploadsEnabled) acceptFile(e.dataTransfer.files?.[0]);
            }}
          >
            <UploadIcon />
            <span>
              <span className="upload-title">Tải ảnh của bạn lên</span>
              <span className="upload-hint">
                {uploadsEnabled
                  ? "JPG hoặc PNG, tối đa 10 MB · Chụp rõ một lá, đủ sáng"
                  : "Chỉ dùng được khi demo chạy mô hình trên máy"}
              </span>
            </span>
            <input
              ref={fileInput}
              type="file"
              accept="image/jpeg,image/png"
              disabled={!uploadsEnabled || busy}
              onChange={(e) => {
                acceptFile(e.target.files?.[0]);
                e.target.value = "";
              }}
            />
          </label>
          {upload && (
            <div className="upload-actions">
              <button type="button" className="btn-secondary" onClick={clearUpload} disabled={busy}>
                <CloseIcon size={16} /> Bỏ ảnh đã tải, quay về ảnh mẫu
              </button>
            </div>
          )}

          <h3 className="gallery-title">Hoặc chọn ảnh có sẵn</h3>
          <div className="thumb-grid" role="group" aria-label="Ảnh mẫu PlantVillage">
            {plantvillage.map((s) => (
              <Thumb key={s.image_id} s={s} selected={!upload && s.image_id === imageId} onPick={chooseSample} />
            ))}
          </div>
          <h3 className="gallery-title">Ảnh chụp ngoài vườn (nguồn mở)</h3>
          <div className="thumb-grid" role="group" aria-label="Ảnh ngoài vườn">
            {realWorld.map((s) => (
              <Thumb key={s.image_id} s={s} selected={!upload && s.image_id === imageId} onPick={chooseSample} />
            ))}
          </div>
          <p className="image-credit">
            Hàng trên: ảnh gốc PlantVillage trong bộ dữ liệu. Hàng dưới: ảnh chụp ngoài vườn từ Wikimedia
            Commons / Bugwood.org, giấy phép CC, không nằm trong bộ dữ liệu huấn luyện.
          </p>
        </Card>

        <div className="col-right">
          {/* ----- Bước 2 ----- */}
          <Card aria-labelledby="buoc2">
            <StepTitle step={2} id="buoc2">
              Bạn muốn hỏi gì?
            </StepTitle>
            <div className="chips" role="group" aria-label="Câu hỏi gợi ý theo 9 dạng của bộ dữ liệu">
              {CHIPS.map((c) => (
                <button
                  key={c.type}
                  type="button"
                  className="chip"
                  aria-pressed={chip === c.type}
                  title={qtypeVi(c.type)}
                  onClick={() => pickChip(c.type)}
                  disabled={busy}
                >
                  {c.chip}
                </button>
              ))}
            </div>
            {activeChip && (
              <p className="chip-hint">
                Dạng câu hỏi: <strong>{qtypeVi(activeChip.type)}</strong> · {activeChip.hint}.
                {questionId && !upload
                  ? " Đây là câu hỏi gốc của ảnh này trong bộ dữ liệu, có đáp án để so sánh."
                  : " Câu hỏi tự soạn theo văn phong bộ dữ liệu, không có đáp án để so sánh."}
              </p>
            )}
            <label className="field-label" htmlFor="cauhoi">
              Câu hỏi
            </label>
            <div className="ask-row">
              <textarea
                id="cauhoi"
                lang="vi"
                rows={2}
                maxLength={500}
                value={question}
                placeholder="Gõ câu hỏi bằng tiếng Việt, hoặc bấm một gợi ý ở trên"
                disabled={busy}
                onChange={(e) => {
                  setQuestion(e.target.value);
                  setQuestionId(null);
                  bump();
                }}
              />
              <button
                type="button"
                className="btn-primary"
                disabled={busy || !runtime?.inference_ready || !question.trim()}
                onClick={run}
              >
                {pending ? "Đang gửi…" : busy ? "Đang trả lời…" : "Hỏi ngay"}
                {!busy && <ArrowIcon />}
              </button>
            </div>
            <p className="field-hint">
              {question.length}/500 ký tự · Mô hình chỉ học 9 dạng câu hỏi ở trên; câu hỏi lạ có thể
              được trả lời kém.
            </p>
            <div className="segmented" role="group" aria-label="Số mô hình sẽ chạy">
              <button type="button" aria-pressed={mode === "all"} onClick={() => setMode("all")} disabled={busy}>
                So sánh 4 mô hình
              </button>
              <button type="button" aria-pressed={mode === "best"} onClick={() => setMode("best")} disabled={busy}>
                Chỉ NoRA · E3 (nhanh hơn)
              </button>
            </div>
            {error && (
              <Notice tone="error" role="alert">
                {error}
              </Notice>
            )}
            {!runtime?.inference_ready && runtime && (
              <Notice tone="info" role="status">
                {runtime.state === "warming_up"
                  ? "Mô hình đang được nạp lên máy. Nút “Hỏi ngay” sẽ bật khi sẵn sàng."
                  : runtime.message}
              </Notice>
            )}
          </Card>

          {/* ----- Bước 3 ----- */}
          <Card aria-labelledby="buoc3" aria-live="polite">
            <StepTitle step={3} id="buoc3">
              Câu trả lời
            </StepTitle>

            {!job && (
              <div className="placeholder">
                Chọn ảnh và câu hỏi rồi bấm <strong>Hỏi ngay</strong>
                {mode === "all" ? ". Bốn mô hình sẽ trả lời lần lượt." : "."}
              </div>
            )}

            {job && (
              <>
                {pollError && (
                  <Notice tone="error" role="alert">
                    {pollError} Sẽ tự thử lại, không gửi lượt hỏi mới.
                  </Notice>
                )}
                {stale && (
                  <Notice tone="info">
                    Kết quả này thuộc về ảnh/câu hỏi trước. Bấm “Hỏi ngay” để hỏi với lựa chọn hiện tại.
                  </Notice>
                )}
                <p className="question-snapshot" lang="vi">
                  <span className="muted small">Câu đã hỏi · {STATUS_VI[job.status] ?? job.status}</span>
                  <br />
                  {job.question}
                </p>
                {job.error && (
                  <Notice tone="error" role="alert">
                    {job.error.message}
                  </Notice>
                )}

                {best && <MainAnswer out={best} job={job} truth={jobTruth} />}

                {others.length > 0 && (
                  <>
                    <h3 className="compare-title">So sánh với các mô hình khác</h3>
                    <div className="compare-list">
                      {others.map((o) => (
                        <CompareRow key={o.model_id} out={o} job={job} />
                      ))}
                    </div>
                  </>
                )}

                {job.image_source === "upload" && (
                  <p className="field-hint">
                    Ảnh bạn tải lên không có đáp án mẫu nên không chấm điểm. Ảnh chỉ được giữ trong lúc
                    chạy rồi xoá, không lưu lại.
                  </p>
                )}
                {jobTruth && (
                  <p className="field-hint">
                    Ảnh ngoài vườn không nằm trong bộ dữ liệu nên không chấm điểm tự động; đáp án đúng lấy theo nhãn
                    của nguồn ảnh (loài cây + bệnh).
                  </p>
                )}
                <div className="actions-row">
                  {!TERMINAL.includes(job.status) && (
                    <button type="button" className="btn-secondary" onClick={cancel} disabled={job.cancel_requested}>
                      {job.cancel_requested ? "Đang huỷ…" : "Huỷ lượt hỏi"}
                    </button>
                  )}
                  {TERMINAL.includes(job.status) && (
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={() => {
                        setJob(null);
                        setError("");
                        setPollError("");
                      }}
                    >
                      Xoá kết quả
                    </button>
                  )}
                </div>
              </>
            )}
          </Card>

          <Warning>
            Đây là mô hình nghiên cứu, học từ ảnh lá chụp trên nền trơn. Với ảnh chụp ngoài ruộng, câu trả
            lời có thể sai. Hãy hỏi thêm cán bộ khuyến nông trước khi phun thuốc.
          </Warning>

        </div>
      </main>
      {active && null}
    </>
  );
}

function Thumb({
  s,
  selected,
  onPick,
}: {
  s: SampleImage;
  selected: boolean;
  onPick: (s: SampleImage) => void;
}) {
  const meta = metaOf(s.image_id);
  return (
    <button
      type="button"
      className="thumb"
      aria-pressed={selected}
      aria-label={`${meta.label}${selected ? " (đang chọn)" : ""}`}
      onClick={() => onPick(s)}
    >
      <img src={s.asset_url} alt="" loading="lazy" />
      <span className="thumb-caption" aria-hidden="true">
        {meta.label}
      </span>
    </button>
  );
}

function MainAnswer({ out, job, truth }: { out: ModelOutput; job: Job; truth?: { plant: string; disease: string } }) {
  const m = modelOf(out.model_id);
  return (
    <div className={`answer-main ${out.model_id === "baseline" ? "is-e0" : ""}`}>
      <div className="answer-meta">
        <span>
          {out.model_id === BEST_MODEL ? "Mô hình tốt nhất · " : ""}
          {m?.name} ({m?.short})
        </span>
        <span>
          {out.status === "succeeded" && out.generation_ms !== undefined && (
            <>
              <ClockIcon /> {seconds(out.generation_ms)}
            </>
          )}
          {["pending", "generating", "loading"].includes(out.status) && (
            <>
              <SpinnerIcon /> {STATUS_VI[out.status]}
            </>
          )}
          {out.status === "failed" && "Lỗi"}
          {out.status === "cancelled" && "Đã huỷ"}
        </span>
      </div>
      {out.answer ? (
        <p className="answer-text" lang="vi">
          {out.answer}
        </p>
      ) : (
        <p className="answer-text muted" style={{ color: "var(--on-green-muted)" }}>
          {out.error?.message ?? (job.status === "queued" ? "Đang chờ đến lượt…" : "Đang trả lời…")}
        </p>
      )}
      {out.answer && !job.reference && truth && (
        <div className="answer-reference">
          <InfoIcon size={18} stroke="#F2C14E" />
          <span>
            Đáp án đúng (theo nguồn ảnh): <strong lang="vi">{truth.plant.charAt(0).toUpperCase() + truth.plant.slice(1)} · {truth.disease}</strong>
          </span>
        </div>
      )}
      {out.answer && job.reference && (
        <div className="answer-reference">
          {out.normalized_exact_match ? <CheckIcon /> : <InfoIcon size={18} stroke="#CFE0C8" />}
          <span>
            {out.normalized_exact_match
              ? "Trùng đáp án trong bộ dữ liệu."
              : "Đáp án trong bộ dữ liệu: "}
            {!out.normalized_exact_match && (
              <em lang="vi">“{job.reference}”</em>
            )}
            {!out.normalized_exact_match && (
              <span className="small"> (so khớp từng chữ; cùng ý nhưng khác câu chữ không tính là trùng)</span>
            )}
          </span>
        </div>
      )}
    </div>
  );
}

function CompareRow({ out, job }: { out: ModelOutput; job: Job }) {
  const m = modelOf(out.model_id);
  return (
    <div className={`compare-row ${out.model_id === "baseline" ? "is-e0" : ""}`}>
      <span className="compare-model">
        {m?.label}
        {out.status === "succeeded" && out.generation_ms !== undefined && (
          <span className="small">
            <ClockIcon size={14} /> {seconds(out.generation_ms)}
          </span>
        )}
        {out.answer && job.reference && out.normalized_exact_match && (
          <span className="match-badge">
            <CheckIcon size={14} stroke="#1E4A2C" /> trùng đáp án
          </span>
        )}
      </span>
      <span className="compare-answer" lang="vi">
        {out.answer ??
          (out.error ? (
            <span className="status">{out.error.message}</span>
          ) : (
            <span className="status">
              {["generating", "loading"].includes(out.status) && <SpinnerIcon size={14} />}{" "}
              {STATUS_VI[out.status] ?? out.status}
            </span>
          ))}
      </span>
    </div>
  );
}
