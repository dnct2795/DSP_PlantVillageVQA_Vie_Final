import { useState } from "react";
import { num, pct, type ResultsData } from "./types";
import { Card, Figure, Flow, SectionTitle, Stat } from "./components";
import { MathFormula } from "./math";

/** Trang Phương pháp: mô hình, LoRA/NoRA, cấu hình thí nghiệm, thước đo. Nội dung theo báo cáo của nhóm. */
export default function PhuongPhap({ results }: { results: ResultsData }) {
  const [selected, setSelected] = useState("E3");
  const e1 = results.main[1];
  const variants = [
    ["E0", "Không adapter", "Mô hình nền giữ nguyên, không tinh chỉnh (zero-shot)."],
    ["E1", "LoRA", "Học hai ma trận hạng thấp A và B, mô hình nền đóng băng."],
    ["E2", "NoRA-init", "Chuẩn hoá cột của A một lần lúc khởi tạo, sau đó huấn luyện như LoRA."],
    ["E3", "NoRA", "Chuẩn hoá cột của A ở mọi lượt tính, kể cả lúc suy luận."],
  ];
  const current = variants.find((v) => v[0] === selected)!;
  return (
    <>
      <section className="hero hero-compact">
        <div className="container">
          <div className="hero-copy">
            <h1>Phương pháp</h1>
            <p>
              Một mô hình thị giác–ngôn ngữ nhỏ (Qwen3-VL-2B-Instruct) được tinh chỉnh tiết kiệm tham số
              bằng LoRA và hai biến thể NoRA, cùng ngân sách tham số, cùng dữ liệu và cùng cách đánh giá.
            </p>
          </div>
          <div className="hero-stats">
            <Stat value="2,1 tỷ" label="tham số mô hình nền" />
            <Stat value={num(e1.trainable_parameters)} label="tham số được học" />
            <Stat value={pct(Number(e1.trainable_percentage) / 100, 2)} label="phần tham số được học" />
          </div>
        </div>
      </section>

      <main className="page stack">
        <Card>
          <SectionTitle index="1">Mô hình nền Qwen3-VL-2B-Instruct</SectionTitle>
          <Flow
            items={["Ảnh → bộ mã hoá thị giác", "Gộp đặc trưng → vector", "Ghép với câu hỏi", "Bộ giải mã → câu trả lời"]}
          />
          <div className="grid-2 prose">
            <p>
              Qwen3-VL-2B-Instruct trích đặc trưng ảnh, chiếu vào không gian ẩn của phần ngôn ngữ, ghép với
              câu hỏi và chỉ dẫn hệ thống, rồi sinh câu trả lời từng token. Bộ mã hoá thị giác và toàn bộ
              trọng số gốc được <strong>đóng băng</strong>.
            </p>
            <p>
              Adapter chỉ gắn vào bốn phép chiếu <em>q / k / v / o</em> của các lớp chú ý trong bộ giải mã
              ngôn ngữ. Hình dưới minh hoạ kiến trúc, không phải bản đồ chú ý thật.
            </p>
          </div>
          <Figure
            id="architecture"
            alt="Kiến trúc Qwen3-VL với bộ mã hoá thị giác, token ảnh và bộ giải mã ngôn ngữ có adapter"
            caption="Kiến trúc mô hình nền và vị trí adapter, theo báo cáo của nhóm (nguồn hình: Qwen3-VL)."
          />
          <div className="grid-2">
            <div className="tile">
              <h4>Mã hoá ảnh và ghép chuỗi</h4>
              <p>
                Bộ mã hoá ViT xử lý các mảnh ảnh; bộ gộp nhóm 2 × 2 đặc trưng lân cận và chiếu về chiều ẩn
                của phần ngôn ngữ (1.024 → 2.048).
              </p>
              <MathFormula
                label="Mã hoá thị giác và gộp đặc trưng"
                tex={String.raw`\begin{aligned}\mathbf X_v&=\operatorname{ViT}(\mathcal P(I))\\\mathbf V&=\operatorname{Merger}_{2\times2}(\mathbf X_v)\end{aligned}`}
              />
              <MathFormula label="Ghép chuỗi đa phương thức" tex={String.raw`\mathbf H^{(0)}=\operatorname{Pack}(\mathbf T,\mathbf V)`} />
            </div>
            <div className="tile">
              <h4>Sinh câu trả lời tự hồi quy</h4>
              <p>Mỗi token của câu trả lời được dự đoán từ ảnh, câu hỏi và các token trước đó.</p>
              <MathFormula
                label="Xác suất câu trả lời"
                tex={String.raw`p(a\mid I,q)=\prod_{t=1}^{L_a}p(a_t\mid I,q,a_{<t})`}
              />
              <p className="small muted">Demo dùng giải mã tham lam, một chùm, tối đa 64 token mới.</p>
            </div>
          </div>
        </Card>

        <Card>
          <SectionTitle index="2" note="Cùng hạng r = 16, α = 16, cùng lớp đích; chỉ khác cách xử lý ma trận A.">
            LoRA và NoRA
          </SectionTitle>
          <div className="grid-2">
            <div className="tile">
              <h4>LoRA · Low-Rank Adaptation</h4>
              <p>
                Giữ nguyên trọng số gốc W₀. Học một hiệu chỉnh nhỏ bằng phép chiếu xuống A và chiếu lên B;
                hạng r quyết định độ rộng biểu diễn trung gian.
              </p>
              <MathFormula label="Cập nhật trọng số LoRA" tex={String.raw`\Delta W_{\mathrm{LoRA}}=\frac{\alpha}{r}BA`} />
              <Figure id="lora-diagram" alt="Sơ đồ LoRA: nhánh trọng số đóng băng và hai ma trận hạng thấp A, B" caption="Sơ đồ LoRA (Hu và cộng sự, trích trong báo cáo)." />
            </div>
            <div className="tile">
              <h4>NoRA · Normalized Low-Rank Adaptation</h4>
              <p>
                Giữ cấu trúc hạng thấp nhưng chuẩn hoá từng cột của A theo chiều hạng. NoRA liên tục tính
                lại ma trận chuẩn hoá ở mỗi lượt tính; NoRA-init chỉ chuẩn hoá một lần lúc khởi tạo.
              </p>
              <MathFormula label="Cập nhật trọng số NoRA" tex={String.raw`\Delta W_{\mathrm{NoRA}}=\frac{\alpha}{r}B\widetilde A`} />
              <MathFormula
                label="Chuẩn hoá cột của ma trận chiếu xuống"
                tex={String.raw`\widetilde{\mathbf a}_j=\frac{\mathbf a_j}{\lVert\mathbf a_j\rVert_2+\epsilon}`}
              />
              <Figure id="nora-diagram" alt="Cơ chế chuẩn hoá cột của NoRA" caption="Sơ đồ NoRA (Kang và cộng sự, trích trong báo cáo)." />
            </div>
          </div>
        </Card>

        <Card>
          <SectionTitle index="3" note="Bốn cấu hình dùng chung mô hình nền, dữ liệu, hạt giống và cách sinh câu trả lời.">
            Bốn cấu hình thí nghiệm
          </SectionTitle>
          <div className="grid-3" role="group" aria-label="Chọn cấu hình">
            {variants.map(([id, name, desc]) => (
              <button
                key={id}
                type="button"
                className={`tile ${selected === id ? "is-active" : ""}`}
                aria-pressed={selected === id}
                onClick={() => setSelected(id)}
                style={{ textAlign: "left" }}
              >
                <span className="kicker">{id}</span>
                <h3>{name}</h3>
                <p className="small muted">{desc}</p>
              </button>
            ))}
          </div>
          <div className="tile" style={{ marginTop: 16 }}>
            <span className="kicker">{current[0]} · {current[1]}</span>
            <p>{current[2]}</p>
            <MathFormula
              label="Đầu ra một lớp chiếu khi suy luận"
              tex={
                selected === "E0"
                  ? String.raw`\mathbf h=W_0\mathbf x`
                  : selected === "E3"
                    ? String.raw`\mathbf h=W_0\mathbf x+\frac{\alpha}{r}B\widetilde A\mathbf x`
                    : String.raw`\mathbf h=W_0\mathbf x+\frac{\alpha}{r}BA\mathbf x`
              }
            />
          </div>
          <div className="stats-inline">
            <Stat value={num(e1.trainable_parameters)} label="tham số adapter được học (E1–E3)" />
            <Stat value="r = α = 16" label="cấu hình hạng thấp chung" />
            <Stat value="3 epoch" label="AdamW, lr 2e-4, batch hiệu dụng 16" />
          </div>
          <details className="more">
            <summary>Chi tiết huấn luyện và sinh câu trả lời</summary>
            <dl className="kv">
              <dt>Lớp đích</dt>
              <dd>q / k / v / o của các lớp chú ý trong bộ giải mã ngôn ngữ; bộ mã hoá thị giác đóng băng</dd>
              <dt>Huấn luyện</dt>
              <dd>3 epoch · lr 0,0002 · batch 2 × tích luỹ 8 · bf16 · hạt giống 42 · chỉ tính loss trên phần trả lời</dd>
              <dt>Dropout adapter</dt>
              <dd>0,05 khi huấn luyện, tắt khi đánh giá</dd>
              <dt>Chọn checkpoint</dt>
              <dd>Loss validation thấp nhất; tập test giữ kín</dd>
              <dt>Sinh câu trả lời</dt>
              <dd>Tham lam · một chùm · tối đa 64 token mới · cùng chỉ dẫn hệ thống tiếng Việt</dd>
              <dt>Phần cứng đo báo cáo</dt>
              <dd>{results.provenance.benchmark_gpu}; demo này chạy fp16 trên MacBook (MPS), chỉ để minh hoạ</dd>
            </dl>
          </details>
        </Card>

        <Card>
          <SectionTitle
            index="4"
            note="Mọi điểm chất lượng lưu trên thang 0–1 và hiển thị theo phần trăm. Dự đoán và đáp án đều được chuẩn hoá: NFC, chữ thường, bỏ khoảng trắng thừa và dấu câu cuối."
          >
            Thước đo đánh giá
          </SectionTitle>
          <div className="grid-2">
            <article className="tile">
              <h4>Khớp chính xác (EM) · Độ chính xác</h4>
              <p>
                Một dòng đúng khi dự đoán và đáp án sau chuẩn hoá giống hệt nhau. Tính riêng cho phần
                Có/Không và phần văn bản, rồi lấy trung bình theo số dòng.
              </p>
              <MathFormula label="Khớp chính xác" tex={String.raw`\operatorname{EM}(S)=\frac{1}{|S|}\sum_{i\in S}\mathbf{1}\!\left[\hat y_i=y_i\right]`} />
              <MathFormula label="Độ chính xác chung" tex={String.raw`a_{\mathrm{all}}=\frac{N_Y a_Y+N_F a_F}{N_Y+N_F}`} />
              <p className="small muted">
                Câu trả lời đúng ý nhưng khác câu chữ vẫn bị tính sai. Đây là giới hạn của thước đo, không
                phải lỗi của mô hình.
              </p>
            </article>
            <article className="tile">
              <h4>BLEU-4 · Độ chính xác n-gram</h4>
              <p>
                So các n-gram bậc 1–4 trên toàn bộ phần văn bản, có phạt câu quá ngắn. Câu trả lời rất
                ngắn dễ bị 0 điểm vì thiếu n-gram bậc cao.
              </p>
              <MathFormula label="BLEU-4" tex={String.raw`\operatorname{BLEU}_4=\operatorname{BP}\exp\!\left(\frac14\sum_{n=1}^{4}\log\widetilde p_n\right)`} />
              <MathFormula label="Phạt độ dài" tex={String.raw`\operatorname{BP}=\exp\!\left(\min\!\left(0,1-\frac{r}{c}\right)\right)`} />
            </article>
            <article className="tile">
              <h4>METEOR · Khớp token có phạt phân mảnh</h4>
              <p>
                Ghép token một–một giữa dự đoán và đáp án, rồi phạt khi thứ tự bị xé lẻ. Chỉ khớp token
                đúng chữ, không dùng từ đồng nghĩa hay gốc từ.
              </p>
              <MathFormula label="METEOR" tex={String.raw`\operatorname{METEOR}=F_{\mathrm{mean}}(1-\operatorname{Pen}),\quad F_{\mathrm{mean}}=\frac{10PR}{R+9P}`} />
              <MathFormula label="Phạt phân mảnh" tex={String.raw`\operatorname{Pen}=\frac12\left(\frac{\mathrm{chunks}}{m}\right)^3`} />
            </article>
            <article className="tile">
              <h4>ROUGE-1 / ROUGE-L · Trùng từ và trùng chuỗi</h4>
              <p>
                ROUGE-1 đếm token chung (F1). ROUGE-L dùng dãy con chung dài nhất để thưởng các token chung
                đúng thứ tự.
              </p>
              <MathFormula label="ROUGE-1" tex={String.raw`\operatorname{ROUGE}_1=\frac{2M_1}{|\hat y|+|y|}`} />
              <MathFormula label="ROUGE-L" tex={String.raw`\operatorname{ROUGE}_L=\frac{2\operatorname{LCS}(\hat y,y)}{|\hat y|+|y|}`} />
            </article>
          </div>
          <p className="small muted">
            Chỉ EM dùng cả hai phần đáp án; BLEU-4, METEOR, ROUGE chỉ tính trên phần văn bản. Thí nghiệm phụ
            thuộc thị giác lặp lại đúng 4.829 dòng test với ảnh trắng, không ảnh và ảnh tráo, giữ nguyên câu
            hỏi và đáp án.
          </p>
        </Card>
      </main>
    </>
  );
}
