import { Suspense, lazy, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { api, type ResultsData, type Runtime, type SampleImage } from "./types";
import { LeafIcon } from "./components";
import HoiDap from "./hoidap";
import "./styles.css";

const BoDuLieu = lazy(() => import("./bodulieu"));
const PhuongPhap = lazy(() => import("./phuongphap"));
const KetQua = lazy(() => import("./ketqua"));

export const PAGES = [
  ["hoi-dap", "Hỏi đáp"],
  ["bo-du-lieu", "Bộ dữ liệu"],
  ["phuong-phap", "Phương pháp"],
  ["ket-qua", "Kết quả"],
] as const;
export type Page = (typeof PAGES)[number][0];

const pageFromPath = (): Page => {
  const slug = location.pathname.replace(/^\/+|\/+$/g, "");
  return (PAGES.find(([p]) => p === slug)?.[0] ?? "hoi-dap") as Page;
};

function App() {
  const [route, setRoute] = useState<Page>(pageFromPath);
  const [data, setData] = useState<{ results: ResultsData; samples: SampleImage[] } | null>(null);
  const [error, setError] = useState("");
  const [runtime, setRuntime] = useState<Runtime | null>(null);
  const [target, setTarget] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  const main = useRef<HTMLElement>(null);

  useEffect(() => {
    let alive = true;
    Promise.all([api<ResultsData>("/api/results"), api<SampleImage[]>("/api/samples")])
      .then(([results, samples]) => {
        if (alive) {
          setData({ results, samples });
          setError("");
        }
      })
      .catch((e) => alive && setError((e as Error).message));
    return () => {
      alive = false;
    };
  }, [retry]);

  useEffect(() => {
    let alive = true;
    const poll = () =>
      api<Runtime>("/api/runtime")
        .then((r) => alive && setRuntime(r))
        .catch(() => alive && setRuntime(null));
    poll();
    const t = setInterval(poll, 3000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  useEffect(() => {
    const back = () => setRoute(pageFromPath());
    addEventListener("popstate", back);
    return () => removeEventListener("popstate", back);
  }, []);

  const navigate = (page: Page, sample?: string) => {
    if (sample) setTarget(sample);
    history.pushState({}, "", `/${page}`);
    setRoute(page);
    window.scrollTo({ top: 0 });
    setTimeout(() => main.current?.focus(), 0);
  };
  const trySample = (row: string) =>
    navigate("hoi-dap", data?.samples.some((s) => s.questions.some((q) => q.row_id === row)) ? row : undefined);

  return (
    <>
      <a className="skip-link" href="#noi-dung">
        Bỏ qua phần đầu, tới nội dung
      </a>
      <header className="site-header">
        <div className="container">
          <a
            href="/hoi-dap"
            className="brand"
            onClick={(e) => {
              e.preventDefault();
              navigate("hoi-dap");
            }}
          >
            <LeafIcon />
            <span>
              <span className="brand-name">Hỏi Lá</span>
              <span className="brand-tagline">Hỏi đáp bệnh lá cây bằng tiếng Việt</span>
            </span>
          </a>
          <nav className="primary-nav" aria-label="Điều hướng chính">
            {PAGES.map(([path, label]) => (
              <a
                key={path}
                href={`/${path}`}
                aria-current={route === path ? "page" : undefined}
                onClick={(e) => {
                  e.preventDefault();
                  navigate(path);
                }}
              >
                {label}
              </a>
            ))}
          </nav>
        </div>
      </header>

      <div id="noi-dung" tabIndex={-1} ref={main as React.RefObject<HTMLDivElement>}>
        {error && (
          <main className="page">
            <div className="card" role="alert">
              <p>Không tải được nội dung: {error}</p>
              <button className="btn-secondary" onClick={() => setRetry((x) => x + 1)}>
                Thử tải lại
              </button>
            </div>
          </main>
        )}
        {!data && !error && (
          <p className="loading" role="status">
            Đang tải nội dung…
          </p>
        )}
        {data && (
          <>
            <div hidden={route !== "hoi-dap"}>
              <HoiDap
                samples={data.samples}
                results={data.results}
                runtime={runtime}
                target={target}
                active={route === "hoi-dap"}
              />
            </div>
            {route !== "hoi-dap" && (
              <Suspense
                fallback={
                  <p className="loading" role="status">
                    Đang tải trang…
                  </p>
                }
              >
                {route === "bo-du-lieu" && (
                  <BoDuLieu results={data.results} samples={data.samples} onTry={trySample} />
                )}
                {route === "phuong-phap" && <PhuongPhap results={data.results} />}
                {route === "ket-qua" && <KetQua data={data.results} onTry={trySample} />}
              </Suspense>
            )}
          </>
        )}
      </div>

      <footer className="site-footer">
        <div className="container">
          <span>DSP391 · Nhóm 1 · Qwen3-VL-2B tinh chỉnh LoRA/NoRA trên PlantVillageVQA-Vie</span>
          <span>
            <a
              href="/phuong-phap"
              onClick={(e) => {
                e.preventDefault();
                navigate("phuong-phap");
              }}
            >
              Xem phần nghiên cứu
            </a>
            {" · "}
            <a
              href="https://github.com/dnct2795/DSP_PlantVillageVQA_Vie_Final"
              target="_blank"
              rel="noreferrer"
            >
              Mã nguồn và dữ liệu
            </a>
          </span>
          <span>Bản demo nghiên cứu · câu trả lời có thể sai.</span>
        </div>
      </footer>
    </>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
