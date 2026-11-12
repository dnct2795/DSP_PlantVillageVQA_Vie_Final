import { defineConfig } from "@playwright/test";
// Chạy với server demo thật đang mở ở 127.0.0.1:8000 (bash scripts/run_demo.sh).
// DEMO_URL đổi địa chỉ; DEMO_NO_GPU=1 bỏ qua các test cần model.
export default defineConfig({
  testDir: "./tests",
  timeout: 120000,
  fullyParallel: false,
  workers: 1,
  use: {
    baseURL: process.env.DEMO_URL ?? "http://127.0.0.1:8000",
    channel: "chrome",
    viewport: { width: 1440, height: 1000 },
  },
  reporter: "list",
  outputDir: "../logs/playwright-results",
});
