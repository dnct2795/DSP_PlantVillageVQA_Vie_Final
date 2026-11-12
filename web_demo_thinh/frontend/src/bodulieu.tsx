import { num, type ResultsData, type SampleImage } from "./types";
import { CHIPS, qtypeVi } from "./questions";
import { metaOf } from "./samples_meta";
import { Card, Figure, Flow, SectionTitle, Stat, Table } from "./components";

/**
 * Trang Bộ dữ liệu. Số liệu lấy từ PROGRESS.md / quality_report của repo dữ liệu và
 * generated/results.json (xuất từ CSV báo cáo). Không bịa số; chỗ chưa có ghi "chưa có".
 */
export default function BoDuLieu({
  results,
  samples,
  onTry,
}: {
  results: ResultsData;
  samples: SampleImage[];
  onTry: (row: string) => void;
}) {
  const main = results.main[0];
  const qtypeRows = results.question_types.filter(
    (r) => r.run === "E0_baseline" && r.split === "test",
  );
  const gallery = samples
    .filter((s) => s.group === "plantvillage")
    .flatMap((s) => s.questions.map((q) => ({ s, q })))
    .slice(0, 9);
  return (
    <>
      <section className="hero hero-compact">
        <div className="container">
          <div className="hero-copy">
            <h1>Bộ dữ liệu PlantVillageVQA-Vie</h1>
            <p>
              Bộ hỏi–đáp hình ảnh về lá cây bằng tiếng Việt, dựng từ PlantVillageVQA bằng một quy
              trình tự động ba bước: lấy mẫu đại diện, dịch theo cặp có ngữ cảnh, và chấm – sửa độc lập.
            </p>
          </div>
          <div className="hero-stats">
            <Stat value={num(main.dataset_count)} label="cặp hỏi–đáp" />
            <Stat value={num(main.dataset_unique_images)} label="ảnh lá cây" />
            <Stat value="7.519" label="cặp dịch duy nhất" />
            <Stat value="9" label="dạng câu hỏi" />
          </div>
        </div>
      </section>

      <main className="page stack">
        <Card>
          <SectionTitle
            index="1"
            note="Nguồn: Hugging Face SyedNazmusSakib/PlantVillageVQA, revision a025a438 (ghim cố định)."
          >
            Nguồn gốc và quy trình xây dựng
          </SectionTitle>
          <div className="prose">
            <p>
              PlantVillageVQA là bộ hỏi–đáp tiếng Anh sinh từ mẫu câu trên ảnh lá PlantVillage: ảnh một
              lá đơn, chụp trong phòng trên nền trơn. Bản gốc có <strong>193.609</strong> dòng hỏi–đáp, chỉ
              có hai phần chia <em>train</em> và <em>test</em>, và 9 dạng câu hỏi. Nhóm lấy một tập con đại
              diện rồi dịch sang tiếng Việt, giữ nguyên ánh xạ ảnh – câu hỏi – đáp án – phần chia.
            </p>
          </div>
          <Flow
            items={[
              "Lấy mẫu phân tầng 12,5 %",
              "Gom cặp, dịch có glossary",
              "Chuẩn hoá thuật ngữ, kiểm tra luật",
              "Chấm độc lập, sửa một lần",
              "Xuất CSV/JSON + bản đối chiếu",
            ]}
          />
          <Figure
            id="data-pipeline"
            alt="Sơ đồ quy trình xây dựng dữ liệu PlantVillageVQA-Vie"
            caption="Sơ đồ quy trình xây dựng dữ liệu trong báo cáo của nhóm (nhãn tiếng Anh theo báo cáo)."
          />
        </Card>

        <Card>
          <SectionTitle index="2" note="Đơn vị lấy mẫu là dòng hỏi–đáp; không thay mẫu.">
            Bước 1 · Lấy mẫu đại diện
          </SectionTitle>
          <div className="prose">
            <p>
              Lấy ngẫu nhiên phân tầng theo <em>phần chia × dạng câu hỏi</em> (18 tầng), tỷ lệ 12,5 %, hạt
              giống 42, phân bổ theo phần dư lớn nhất, mỗi tầng ít nhất một dòng. Kết quả: 24.201 dòng,
              18.751 ảnh, 7.522 cặp (dạng câu hỏi, câu hỏi, đáp án) duy nhất và 1.088 câu hỏi tiếng Anh
              khác nhau.
            </p>
          </div>
          <Table
            headers={["Giai đoạn", "Train", "Test", "Tổng dòng"]}
            rows={[
              ["Bản gốc tiếng Anh", "154.977", "38.632", "193.609"],
              ["Tập con tiếng Anh (12,5 %)", "19.371", "4.830", "24.201"],
              ["Bản tiếng Việt cuối", "19.366", "4.829", "24.195"],
            ]}
            caption="Số dòng hỏi–đáp theo giai đoạn. 6 dòng bị loại ở bước 3 vì bản dịch không đạt sau khi sửa."
          />
        </Card>

        <Card>
          <SectionTitle index="3" note="Mỗi cặp chỉ dịch một lần rồi áp cho mọi dòng dùng cặp đó.">
            Bước 2 · Dịch theo cặp, có ngữ cảnh
          </SectionTitle>
          <div className="prose">
            <ul>
              <li>
                <strong>Gom cặp:</strong> các dòng có cùng (dạng câu hỏi, câu hỏi, đáp án) tiếng Anh dùng
                chung một bản dịch; các cặp cùng câu hỏi được dịch trong cùng một lô để có đúng một{" "}
                <em>câu hỏi tiếng Việt</em> chung.
              </li>
              <li>
                <strong>Glossary cố định</strong> tên cây, tên bệnh, thuật ngữ; tên khoa học giữ nguyên. Viết
                tắt tiếng Anh (HLB, TYLCV, ToMV) luôn thành tên tiếng Việt đầy đủ.
              </li>
              <li>
                <strong>Câu hỏi Có/Không:</strong> giữ nguyên mệnh đề và cực tính, dạng “… có … không?”; đáp
                án chỉ là “Có” hoặc “Không”, nhãn sao chép từ nguồn, không qua dịch.
              </li>
              <li>
                <strong>Kiểm tra bằng luật</strong> (không dùng model): JSON hợp lệ, Có/Không khớp nhãn, tên
                cây/bệnh khớp glossary, không còn tiếng Anh chưa dịch, cùng câu hỏi gốc → cùng câu hỏi
                Việt. Kết quả: 7.508 cặp qua, 14 cặp trượt (96 dòng) chuyển sang bước sửa.
              </li>
            </ul>
            <p className="small muted">Mô hình dịch: Claude Sonnet, chạy qua gói Claude Pro, không dùng API trả phí.</p>
          </div>
        </Card>

        <Card>
          <SectionTitle index="4" note="Người chấm và người dịch là hai mô hình khác nhau.">
            Bước 3 · Chấm độc lập và sửa có chọn lọc
          </SectionTitle>
          <div className="prose">
            <p>
              Codex (gpt-6-luna) chấm từng cặp Anh–Việt theo kiểu MQM: sai nghĩa, đảo cực tính, thiếu, thừa,
              thuật ngữ, độ trôi chảy; mỗi lỗi ở mức nhỏ, lớn hoặc nghiêm trọng. Trước khi chấm toàn bộ,
              bộ kiểm tra 50 cặp cố ý sai: bắt được <strong>40/40</strong> lỗi cài vào, báo nhầm{" "}
              <strong>0/10</strong> cặp đúng. Cặp có lỗi lớn/nghiêm trọng hoặc trượt luật được Claude dịch
              lại đúng một lần kèm nhận xét, rồi chấm lại.
            </p>
          </div>
          <Table
            headers={["Trạng thái", "Cặp duy nhất", "Dòng hỏi–đáp"]}
            rows={[
              ["PASS (qua ngay lần đầu)", "7.489", "23.972"],
              ["PASS_AFTER_REPAIR (qua sau một lần sửa)", "30", "223"],
              ["UNRESOLVED (không đạt, giữ lại để truy vết)", "3", "6"],
              [<strong>Được dùng (PASS + PASS_AFTER_REPAIR)</strong>, <strong>7.519</strong>, <strong>24.195</strong>],
            ]}
            caption="Chỉ PASS và PASS_AFTER_REPAIR được coi là “đã kiểm định tự động, mức silver-standard”. Không có người kiểm định."
          />
        </Card>

        <Card>
          <SectionTitle index="5" note="Số dòng theo tập test dùng để huấn luyện/đánh giá mô hình (4.829 dòng).">
            Chín dạng câu hỏi
          </SectionTitle>
          <Table
            headers={["Dạng câu hỏi", "Tên gốc", "Ví dụ câu hỏi trong bộ dữ liệu", "Dòng test"]}
            rows={CHIPS.map((c) => {
              const row = qtypeRows.find((r) => r.question_type === c.type);
              return [
                qtypeVi(c.type),
                <span className="small muted">{c.type}</span>,
                <span lang="vi">{c.template("cà chua", "mốc sương")}</span>,
                <span className="num">{row ? num(row.count) : "chưa có"}</span>,
              ];
            })}
            caption="Ví dụ là câu hỏi thật xuất hiện nhiều trong bộ dữ liệu tiếng Việt (tên cây/bệnh điền minh hoạ)."
          />
          <p className="small muted">
            Phần đáp án: câu hỏi Có/Không chiếm khoảng 42 % số dòng; phần còn lại là câu trả lời ngắn dạng
            văn bản (tên cây, tên bệnh, mô tả một câu).
          </p>
        </Card>

        <Card>
          <SectionTitle index="6" note="Chia theo ảnh để ảnh không xuất hiện ở hai tập.">
            Phần chia dùng cho huấn luyện
          </SectionTitle>
          <div className="prose">
            <p>
              Giữ nguyên tập <em>test</em> của nguồn; tách khoảng 10 % ảnh của <em>train</em> làm{" "}
              <em>validation</em>, đảm bảo không trùng ảnh giữa các tập.
            </p>
          </div>
          <Table
            headers={["Tập", "Dòng hỏi–đáp", "Ảnh"]}
            rows={[
              ["Train", num(main.train_count), num(main.train_unique_images)],
              ["Validation", num(main.validation_count), num(main.validation_unique_images)],
              ["Test", num(main.test_count), num(main.test_unique_images)],
              [<strong>Tổng</strong>, <strong>{num(main.dataset_count)}</strong>, <strong>{num(main.dataset_unique_images)}</strong>],
            ]}
            caption={`Test gồm ${num(main.test_yesno_count)} dòng Có/Không và ${num(main.test_freetext_count)} dòng văn bản. Bốn biến thể test cho thí nghiệm phụ thuộc thị giác: ảnh gốc, ảnh trắng, không ảnh, ảnh tráo.`}
          />
        </Card>

        <Card>
          <SectionTitle index="7" note="Câu hỏi và đáp án tiếng Việt gốc trong bộ dữ liệu, không phải câu trả lời của mô hình.">
            Ví dụ từ bộ dữ liệu
          </SectionTitle>
          <div className="sample-cards">
            {gallery.map(({ s, q }) => (
              <article key={q.row_id} className="sample-card">
                <img src={s.asset_url} alt={`Ảnh mẫu: ${metaOf(s.image_id).label}`} loading="lazy" />
                <div className="body">
                  <span className="qtype">{qtypeVi(q.question_type)}</span>
                  <p className="q" lang="vi">
                    {q.question}
                  </p>
                  <p className="a">Đáp án được giấu trên trang này; bấm “Thử hỏi” để xem và so với mô hình.</p>
                  <button type="button" className="btn-link" onClick={() => onTry(q.row_id)}>
                    Thử hỏi với ảnh này
                  </button>
                </div>
              </article>
            ))}
          </div>
        </Card>

        <Card>
          <SectionTitle index="8">Giới hạn cần biết</SectionTitle>
          <div className="prose">
            <ul>
              <li>
                Dữ liệu gốc sinh từ mẫu câu: 1.088 câu hỏi và vài trăm mẫu đáp án lặp lại trên nhiều ảnh,
                nên mô hình học “cách nói” của bộ dữ liệu hơn là ngôn ngữ tự nhiên đa dạng.
              </li>
              <li>
                Lấy mẫu theo dòng nên một ảnh có thể xuất hiện ở cả train và test với câu hỏi khác nhau;
                nhóm đã chia lại theo ảnh cho phần huấn luyện.
              </li>
              <li>
                Bản dịch chỉ được kiểm định tự động (luật + một mô hình chấm), chưa có người đối chiếu;
                còn khoảng 300 cặp có lỗi nhỏ được chấp nhận.
              </li>
              <li>Ảnh chụp trong phòng, nền trơn; ảnh ngoài ruộng khác phân phối nên kết quả kém hơn.</li>
            </ul>
          </div>
          <div className="page-links">
            <a className="btn-secondary" href="https://github.com/dnct2795/DSP_PlantVillageVQA_Vie_Final" target="_blank" rel="noreferrer">
              Mã nguồn quy trình và báo cáo chất lượng
            </a>
            <a className="btn-secondary" href="https://www.kaggle.com/datasets/ngnguyncngthnh/plantvillagevqa-vietnamese" target="_blank" rel="noreferrer">
              Bộ dữ liệu trên Kaggle
            </a>
          </div>
        </Card>
      </main>
    </>
  );
}
