import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";

const vietnamese = /[ăâđêôơưĂÂĐÊÔƠƯẠ-ỹ]/;
const noGpu = process.env.DEMO_NO_GPU === "1";
const sampleImage = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../samples/real-world/rw05_corn_common_rust.jpg");

for (const [slug, heading] of [
  ["bo-du-lieu", "Bộ dữ liệu PlantVillageVQA-Vie"],
  ["phuong-phap", "Phương pháp"],
  ["ket-qua", "Kết quả"],
] as const) {
  test(`${slug}: nội dung tiếng Việt, điều hướng và hình minh hoạ`, async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto(`/${slug}`);
    await expect(page.locator("html")).toHaveAttribute("lang", "vi");
    await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
    await expect(page.locator("nav a[aria-current=page]")).toHaveText(
      slug === "bo-du-lieu" ? "Bộ dữ liệu" : slug === "phuong-phap" ? "Phương pháp" : "Kết quả",
    );
    expect(await page.locator("main:visible").innerText()).toMatch(vietnamese);
    const images = page.locator("main:visible img:visible");
    expect(await images.count()).toBeGreaterThan(0);
    const alts = await images.evaluateAll((imgs) => imgs.map((i) => i.getAttribute("alt")));
    expect(alts.every((a) => a !== null)).toBeTruthy();
    await page.screenshot({ path: `../logs/screens/${slug}-desktop.png`, fullPage: true });
    expect(errors).toEqual([]);
  });
}

test("ket-qua: số liệu khớp báo cáo và bộ lọc hoạt động", async ({ page }) => {
  await page.goto("/ket-qua");
  const table = page.locator("table").first();
  await expect(table).toContainText("61,25 %");
  await expect(table).toContainText("57,76 %");
  await expect(table).toContainText("0,00 %");
  await page.getByLabel("Tập đánh giá").selectOption("validation");
  await expect(page.locator(".heatmap tbody tr").first()).toContainText("267");
  await page.getByLabel("Tập đánh giá").selectOption("test");
  await expect(page.locator(".heatmap tbody tr").first()).toContainText("697");
  await page.getByLabel("Phần đáp án").selectOption("sentence_acc");
  await expect(page.getByRole("img", { name: /Khớp chính xác \(Văn bản\)/ })).toBeVisible();
});

test("hoi-dap: bố cục 3 bước, chip điền câu hỏi đúng dạng, cảnh báo luôn hiện", async ({ page }) => {
  await page.goto("/hoi-dap");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Thắc mắc bệnh cây trồng");
  for (const step of ["Chọn ảnh lá cây", "Bạn muốn hỏi gì?", "Câu trả lời"])
    await expect(page.getByRole("heading", { level: 2, name: step })).toBeVisible();
  await expect(page.getByRole("note")).toContainText("cán bộ khuyến nông");
  const textarea = page.locator("textarea#cauhoi");
  await expect(textarea).toHaveAttribute("lang", "vi");
  // Ảnh mẫu cà chua có câu gốc dạng nhận dạng bệnh → chip dùng câu gốc
  await page.getByRole("button", { name: "Lá bị bệnh gì?" }).click();
  await expect(textarea).toHaveValue(/lá cà chua này/);
  // Dạng không có câu gốc cho ảnh này → câu mẫu theo văn phong bộ dữ liệu
  await page.getByRole("button", { name: "Ảnh có lá cây không?" }).click();
  await expect(textarea).toHaveValue("Trong hình ảnh này có lá cây không?");
  await page.getByRole("button", { name: "Có phải bệnh … không?" }).click();
  await expect(textarea).toHaveValue(/Lá cà chua này có bị nhiễm bệnh .* không\?/);
  // Đổi ảnh mẫu: nhãn ảnh đổi theo
  await page.getByRole("button", { name: /Lá cam · vàng lá gân xanh/ }).click();
  await expect(page.locator(".selected-image .tag")).toContainText("Lá cam");
  await expect(page.locator("main:visible")).toContainText(/Ảnh ngoài vườn|Hàng dưới/);
});

test("hoi-dap: giao diện điện thoại không tràn ngang", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/hoi-dap");
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  expect(overflow).toBeFalsy();
  await expect(page.getByRole("heading", { level: 2, name: "Chọn ảnh lá cây" })).toBeVisible();
  await page.screenshot({ path: "../logs/screens/hoi-dap-mobile.png", fullPage: true });
});

test("hoi-dap: trợ năng cơ bản (axe, WCAG A/AA)", async ({ page }) => {
  await page.goto("/hoi-dap");
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  const serious = results.violations.filter((v) => ["serious", "critical"].includes(v.impact ?? ""));
  expect(serious.map((v) => `${v.id}: ${v.nodes.length}`)).toEqual([]);
});

test.describe("chạy model thật trên máy", () => {
  test.skip(noGpu, "DEMO_NO_GPU=1: bỏ qua test cần model");

  test("hỏi với ảnh mẫu: so sánh 4 mô hình, có đáp án bộ dữ liệu", async ({ page }) => {
    await page.goto("/hoi-dap");
    await expect(page.getByRole("button", { name: "Hỏi ngay" })).toBeEnabled({ timeout: 300000 });
    await page.getByRole("button", { name: "Lá bị bệnh gì?" }).click();
    await page.getByRole("button", { name: "So sánh 4 mô hình" }).click();
    await page.getByRole("button", { name: "Hỏi ngay" }).click();
    await expect(page.locator(".question-snapshot")).toContainText("Xong", { timeout: 180000 });
    await expect(page.locator(".answer-main")).toContainText("NoRA (E3)");
    await expect(page.locator(".answer-main .answer-text")).toHaveText(vietnamese);
    expect(await page.locator(".compare-row").count()).toBe(3);
    await expect(page.locator(".answer-main")).toContainText(/đáp án/i);
    await expect(page.locator(".answer-main")).toContainText("giây");
    await page.screenshot({ path: "../logs/screens/hoi-dap-ket-qua.png", fullPage: true });
  });

  test("tải ảnh lên: chỉ E3, không có đáp án, không chấm điểm", async ({ page }) => {
    await page.goto("/hoi-dap");
    await expect(page.getByRole("button", { name: "Hỏi ngay" })).toBeEnabled({ timeout: 300000 });
    await page.locator('input[type=file]').setInputFiles(sampleImage);
    await expect(page.locator(".selected-image .tag")).toContainText("Ảnh của bạn");
    await page.getByRole("button", { name: "Lá bị bệnh gì?" }).click();
    await expect(page.locator("textarea#cauhoi")).toHaveValue("Cây này đang mắc bệnh hoặc rối loạn gì?");
    await page.getByRole("button", { name: "Chỉ NoRA · E3 (nhanh hơn)" }).click();
    await page.getByRole("button", { name: "Hỏi ngay" }).click();
    await expect(page.locator(".question-snapshot")).toContainText("Xong", { timeout: 180000 });
    await expect(page.locator(".answer-main .answer-text")).toHaveText(vietnamese);
    expect(await page.locator(".compare-row").count()).toBe(0);
    await expect(page.locator("main:visible")).toContainText("không có đáp án mẫu");
    await expect(page.locator(".answer-main")).not.toContainText("Đáp án trong bộ dữ liệu");
  });

  test("tải tệp không phải ảnh bị từ chối ngay trên trình duyệt", async ({ page }) => {
    await page.goto("/hoi-dap");
    await expect(page.getByRole("button", { name: "Hỏi ngay" })).toBeEnabled({ timeout: 300000 });
    await page.locator('input[type=file]').setInputFiles({
      name: "ghi-chu.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("khong phai anh"),
    });
    await expect(page.getByRole("alert")).toContainText("Chỉ nhận ảnh JPG hoặc PNG");
  });
});
