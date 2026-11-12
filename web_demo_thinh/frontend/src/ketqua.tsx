import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { asset, num, pct, runLabel, runShort, type ResultsData, type Row } from "./types";
import { qtypeVi } from "./questions";
import { Card, SectionTitle, Stat, Table } from "./components";

/** Màu cố định theo mô hình (E0..E3), không xoay vòng; đã kiểm tra bằng validator của skill dataviz. */
export const MODEL_COLORS: Record<string, string> = {
  E0: "#C2693A",
  E1: "#2A78D6",
  E2: "#EDA100",
  E3: "#1F8A4C",
};
const ACC_METRICS = [
  ["overall_acc", "Chung"],
  ["yesno_acc", "Có/Không"],
  ["sentence_acc", "Văn bản"],
] as const;
const TEXT_METRICS = [
  ["bleu4", "BLEU-4"],
  ["meteor", "METEOR"],
  ["rouge1", "ROUGE-1"],
  ["rouge_l", "ROUGE-L"],
] as const;
const CONDITIONS = [
  ["normal", "Ảnh gốc"],
  ["blank", "Ảnh trắng"],
  ["no_image", "Không ảnh"],
  ["shuffled", "Ảnh tráo"],
] as const;

function Chart({
  data,
  series,
  byRow = false,
  label,
}: {
  data: Record<string, unknown>[];
  series: { key: string; label: string; color?: string }[];
  byRow?: boolean;
  label: string;
}) {
  return (
    <div className="chart" role="img" aria-label={`${label}. Giá trị chính xác ở bảng kèm theo.`}>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data} margin={{ top: 12, right: 8, left: -12, bottom: 0 }} barGap={2} barCategoryGap="28%">
          <CartesianGrid vertical={false} stroke="#E1E7DA" />
          <XAxis dataKey="name" tick={{ fill: "#4F5F52", fontSize: 13 }} tickLine={false} axisLine={{ stroke: "#C9D5C1" }} />
          <YAxis
            domain={[0, 100]}
            tickFormatter={(v) => `${v} %`}
            tick={{ fill: "#4F5F52", fontSize: 12 }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip
            contentStyle={{ background: "#fff", border: "1px solid #C9D5C1", borderRadius: 10, fontSize: 14 }}
            formatter={(v) => pct(Number(v) / 100)}
            cursor={{ fill: "#EEF2E8" }}
          />
          {series.length > 1 && <Legend wrapperStyle={{ fontSize: 13 }} />}
          {series.map((s) => (
            <Bar key={s.key} dataKey={s.key} name={s.label} fill={s.color ?? "#1E4A2C"} maxBarSize={48} radius={[4, 4, 0, 0]} isAnimationActive={false}>
              {byRow && data.map((d, j) => <Cell key={j} fill={MODEL_COLORS[String(d.short)] ?? "#1E4A2C"} />)}
            </Bar>
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

const Swatch = ({ run }: { run: unknown }) => (
  <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
    <span aria-hidden="true" style={{ width: 12, height: 12, borderRadius: 3, background: MODEL_COLORS[runShort(run)] }} />
    {runLabel(run)}
  </span>
);

export default function KetQua({ data, onTry }: { data: ResultsData; onTry: (row: string) => void }) {
  const [metric, setMetric] = useState<(typeof ACC_METRICS)[number][0]>("overall_acc");
  const [split, setSplit] = useState<"test" | "validation">("test");
  const main = data.main;
  const e1 = main[1];
  const e3 = main[3];
  const delta = (Number(e3.overall_acc) - Number(e1.overall_acc)) * 100;
  const qtypes = [...new Set(data.question_types.map((r) => String(r.question_type)))];
  const qrow = (q: string, run: unknown): Row | undefined =>
    data.question_types.find((r) => r.question_type === q && r.run === run && r.split === split);
  const abl = (run: unknown, c: string) => data.ablation.find((a) => a.run === run && a.condition === c);
  const bestRow = (rows: Row[], key: string) => rows.reduce((b, r) => (Number(r[key]) > Number(b[key]) ? r : b), rows[0]);

  return (
    <>
      <section className="hero hero-compact">
        <div className="container">
          <div className="hero-copy">
            <h1>Kết quả</h1>
            <p>
              Bốn cấu hình E0–E3 được đánh giá trên tập test giữ kín gồm {num(e3.test_count)} dòng hỏi–đáp tiếng
              Việt ({num(e3.test_yesno_count)} Có/Không, {num(e3.test_freetext_count)} văn bản). Số liệu lấy từ
              báo cáo của nhóm, đo trên {data.provenance.benchmark_gpu}.
            </p>
          </div>
          <div className="hero-stats">
            <Stat value={pct(e3.overall_acc)} label="NoRA (E3) khớp chính xác chung" />
            <Stat value={`+${num(delta, 2)} điểm %`} label="NoRA so với LoRA" />
            <Stat value={pct(e3.sentence_acc)} label="NoRA khớp chính xác phần văn bản" />
          </div>
        </div>
      </section>

      <main className="page stack">
        <Card>
          <SectionTitle index="1" note="Khớp chính xác là so chuỗi sau chuẩn hoá, không phải đánh giá ngữ nghĩa của chuyên gia.">
            Độ chính xác khớp chính xác (EM)
          </SectionTitle>
          <div className="chart-controls">
            <label className="field-label">
              Phần đáp án
              <select className="select" value={metric} onChange={(e) => setMetric(e.target.value as typeof metric)}>
                {ACC_METRICS.map(([k, l]) => (
                  <option key={k} value={k}>
                    {l}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <Chart
            label={`Khớp chính xác (${ACC_METRICS.find((m) => m[0] === metric)![1]}) của bốn mô hình`}
            data={main.map((r) => ({ name: runLabel(r.run), short: runShort(r.run), score: Number(r[metric]) * 100 }))}
            series={[{ key: "score", label: ACC_METRICS.find((m) => m[0] === metric)![1] }]}
            byRow
          />
          <Table
            headers={["Mô hình", "EM chung", "EM Có/Không", "EM văn bản"]}
            rows={main.map((r) => [<Swatch run={r.run} />, ...ACC_METRICS.map(([k]) => pct(r[k]))])}
            caption={`Tập test. Mô hình tốt nhất ở EM chung: ${runLabel(bestRow(main, "overall_acc").run)}.`}
          />
          <p className="small muted">
            E0 đạt 0 % không có nghĩa mọi câu trả lời đều vô nghĩa: mô hình nền thường trả lời dài, khác
            hẳn khuôn đáp án ngắn của bộ dữ liệu nên không bao giờ khớp từng chữ.
          </p>
        </Card>

        <Card>
          <SectionTitle index="2" note="Chỉ tính trên phần đáp án văn bản (2.809 dòng). Hiển thị theo phần trăm.">
            Thước đo sinh văn bản
          </SectionTitle>
          <Chart
            label="BLEU-4, METEOR, ROUGE-1, ROUGE-L của bốn mô hình"
            data={TEXT_METRICS.map(([k, l]) => ({
              name: l,
              ...Object.fromEntries(main.map((r) => [runShort(r.run), Number(r[k]) * 100])),
            }))}
            series={main.map((r) => ({ key: runShort(r.run), label: runLabel(r.run), color: MODEL_COLORS[runShort(r.run)] }))}
          />
          <Table
            headers={["Mô hình", ...TEXT_METRICS.map(([, l]) => l)]}
            rows={main.map((r) => [<Swatch run={r.run} />, ...TEXT_METRICS.map(([k]) => pct(r[k]))])}
            caption="METEOR ở đây chỉ khớp token đúng chữ, không dùng từ đồng nghĩa hay gốc từ."
          />
        </Card>

        <Card>
          <SectionTitle index="3">Kết quả theo dạng câu hỏi</SectionTitle>
          <label className="field-label">
            Tập đánh giá
            <select className="select" value={split} onChange={(e) => setSplit(e.target.value as typeof split)}>
              <option value="test">Test · {num(e3.test_count)} dòng</option>
              <option value="validation">Validation · {num(e3.validation_count)} dòng</option>
            </select>
          </label>
          <div className="table-scroll">
            <table className="table heatmap">
              <caption>Khớp chính xác chung theo dạng câu hỏi. Màu nền đậm dần theo giá trị; số luôn được ghi rõ.</caption>
              <thead>
                <tr>
                  <th scope="col">Dạng câu hỏi</th>
                  <th scope="col">Số dòng</th>
                  {main.map((r) => (
                    <th key={String(r.run)} scope="col">
                      {runLabel(r.run)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {qtypes.map((q) => (
                  <tr key={q}>
                    <th scope="row">
                      {qtypeVi(q)}
                      <br />
                      <span className="small muted">{q}</span>
                    </th>
                    <td>{num(qrow(q, main[0].run)?.count)}</td>
                    {main.map((r) => {
                      const v = qrow(q, r.run)?.accuracy;
                      return (
                        <td key={String(r.run)} style={{ backgroundColor: `rgba(30, 74, 44, ${Number(v ?? 0) * 0.22})` }}>
                          {pct(v)}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="small muted">
            Các dạng trả lời Có/Không (đánh giá sức khỏe, kiểm chứng, xác nhận đặc điểm, kiểm tra có lá) đạt rất
            cao; các dạng trả lời văn bản dài (mô tả, suy luận) thấp hơn nhiều vì khớp từng chữ khó hơn.
          </p>
        </Card>

        <Card>
          <SectionTitle
            index="4"
            note="Giữ nguyên câu hỏi và đáp án, chỉ đổi ảnh đưa vào: ảnh trắng, không ảnh, hoặc ảnh tráo của dòng khác. Cùng 4.829 dòng test."
          >
            Mô hình có thật sự “nhìn” ảnh không?
          </SectionTitle>
          <Chart
            label="Khớp chính xác chung theo điều kiện ảnh của bốn mô hình"
            data={CONDITIONS.map(([c, name]) => ({
              name,
              ...Object.fromEntries(main.map((r) => [runShort(r.run), Number(abl(r.run, c)?.accuracy_overall) * 100])),
            }))}
            series={main.map((r) => ({ key: runShort(r.run), label: runLabel(r.run), color: MODEL_COLORS[runShort(r.run)] }))}
          />
          <Table
            headers={["Mô hình", ...CONDITIONS.map(([, n]) => n), "Giảm khi tráo ảnh"]}
            rows={main.map((r) => [
              <Swatch run={r.run} />,
              ...CONDITIONS.map(([c]) => pct(abl(r.run, c)?.accuracy_overall)),
              `${num(abl(r.run, "shuffled")?.drop_accuracy_overall_pp, 2)} điểm %`,
            ])}
            caption="Khớp chính xác chung và mức giảm (ảnh gốc trừ ảnh tráo), tính bằng điểm phần trăm."
          />
          <p className="small muted">
            Điểm giảm mạnh khi bỏ hoặc tráo ảnh cho thấy mô hình có dựa vào ảnh, nhưng chưa chứng minh nó
            nhìn đúng triệu chứng. Phần còn lại (khoảng 30 %) có thể đoán được từ riêng câu hỏi, vì bộ dữ
            liệu sinh từ mẫu câu.
          </p>
        </Card>

        <Card>
          <SectionTitle index="5" note={`Đo trên ${data.provenance.benchmark_gpu} khi làm báo cáo, không phải trên máy chạy demo này.`}>
            Chi phí tính toán
          </SectionTitle>
          <Table
            headers={["Mô hình", "Tham số được học", "Loss validation tốt nhất", "Thời gian huấn luyện", "Suy luận trung vị / P95"]}
            rows={main.map((r) => [
              <Swatch run={r.run} />,
              num(r.trainable_parameters),
              r.best_val_loss === null ? "Không áp dụng" : num(r.best_val_loss, 4),
              r.training_wall_seconds === null ? "Không huấn luyện" : `${num(Number(r.training_wall_seconds) / 60, 1)} phút`,
              `${num(Number(r.latency_median) * 1000, 0)} / ${num(Number(r.latency_p95) * 1000, 0)} ms`,
            ])}
            caption="Ba cấu hình E1–E3 học cùng 6.422.528 tham số (0,30 % mô hình). NoRA liên tục chậm hơn một chút vì chuẩn hoá ở mỗi lượt tính."
          />
        </Card>

        <Card>
          <SectionTitle index="6" note="Hai trường hợp chọn lọc từ báo cáo, không phải ước lượng tỷ lệ lỗi.">
            Ví dụ phân tích lỗi
          </SectionTitle>
          <div className="qual-grid">
            {data.qualitative.map((c) => (
              <article key={c.row_id} className="tile">
                <div className="qual-images">
                  <figure>
                    <img src={asset(c.image_id)} alt="Ảnh gốc của dòng dữ liệu" loading="lazy" />
                    <figcaption>Ảnh gốc</figcaption>
                  </figure>
                  {c.condition === "shuffled" && (
                    <figure>
                      <img src={asset(c.input_image_id)} alt="Ảnh tráo thực tế đưa vào mô hình" loading="lazy" />
                      <figcaption>Ảnh thật đưa vào (tráo)</figcaption>
                    </figure>
                  )}
                </div>
                <span className="kicker">{(c as unknown as { category_vi?: string }).category_vi ?? c.category}</span>
                <p lang="vi">
                  <strong>{c.question}</strong>
                </p>
                <dl className="kv">
                  <dt>Đáp án</dt>
                  <dd lang="vi">{c.reference}</dd>
                  {c.predictions.map((p, i) => (
                    <>
                      <dt key={`t${i}`}>E{i + 1}</dt>
                      <dd key={`d${i}`} lang="vi">
                        {p}
                      </dd>
                    </>
                  ))}
                </dl>
                <p className="small muted">{c.note}</p>
                <button type="button" className="btn-link" onClick={() => onTry(c.row_id)}>
                  Thử hỏi với ảnh này
                </button>
              </article>
            ))}
          </div>
        </Card>

        <details className="more">
          <summary>Nguồn số liệu và cách đọc</summary>
          <p className="small">
            Số liệu lấy từ các bảng CSV trích xuất của báo cáo (bản chụp <code>{data.version.slice(0, 12)}</code>),
            cùng nguồn với <code>results/new/2026-10-31_01/comparison.csv</code> trong repo mô hình. Mỗi cấu hình
            chạy một lần, hạt giống 42, không có khoảng tin cậy. Giá trị trống là “không áp dụng”, không phải 0.
            Chênh lệch E3 − E1 là 3,50 điểm % tính từ số chưa làm tròn; một vài chỗ trong báo cáo ghi 3,49.
          </p>
          <ul className="small">
            {Object.keys(data.provenance.sources)
              .filter((p) => p.endsWith(".csv"))
              .map((p) => (
                <li key={p}>
                  <code>{p}</code>
                </li>
              ))}
          </ul>
        </details>
      </main>
    </>
  );
}
