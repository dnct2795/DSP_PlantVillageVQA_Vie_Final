import React, { useRef } from "react";
import { asset } from "./types";

/* ---------- Icon SVG nét (stroke), không dùng emoji ---------- */
type IconProps = { size?: number; stroke?: string; className?: string };
const svgProps = (size: number, stroke: string, className?: string) => ({
  width: size,
  height: size,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke,
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
  className,
});
export const LeafIcon = ({ size = 36, stroke = "#F2C14E", className }: IconProps) => (
  <svg {...svgProps(size, stroke, className)}>
    <path d="M5 19c0-8 6-14 15-14 0 9-6 15-14 15" />
    <path d="M5 19 13 11" />
  </svg>
);
export const UploadIcon = ({ size = 32, stroke = "#1E4A2C", className }: IconProps) => (
  <svg {...svgProps(size, stroke, className)}>
    <path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
    <path d="M12 4v12" />
    <path d="m7 9 5-5 5 5" />
  </svg>
);
export const CheckIcon = ({ size = 18, stroke = "#F2C14E", className }: IconProps) => (
  <svg {...svgProps(size, stroke, className)} strokeWidth={2}>
    <path d="M20 6 9 17l-5-5" />
  </svg>
);
export const InfoIcon = ({ size = 24, stroke = "#8A5A12", className }: IconProps) => (
  <svg {...svgProps(size, stroke, className)} strokeWidth={2}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 8v5" />
    <path d="M12 16h.01" />
  </svg>
);
export const ArrowIcon = ({ size = 20, stroke = "currentColor", className }: IconProps) => (
  <svg {...svgProps(size, stroke, className)} strokeWidth={2}>
    <path d="M5 12h14" />
    <path d="m13 6 6 6-6 6" />
  </svg>
);
export const ClockIcon = ({ size = 16, stroke = "currentColor", className }: IconProps) => (
  <svg {...svgProps(size, stroke, className)}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  </svg>
);
export const CloseIcon = ({ size = 18, stroke = "currentColor", className }: IconProps) => (
  <svg {...svgProps(size, stroke, className)} strokeWidth={2}>
    <path d="M6 6l12 12" />
    <path d="M18 6 6 18" />
  </svg>
);
export const SpinnerIcon = ({ size = 18, stroke = "currentColor", className }: IconProps) => (
  <svg {...svgProps(size, stroke, `spinner ${className ?? ""}`)} strokeWidth={2}>
    <path d="M12 3a9 9 0 1 0 9 9" />
  </svg>
);

/* ---------- Khối bố cục ---------- */
export function Card({
  children,
  className = "",
  as: Tag = "section",
  ...rest
}: React.HTMLAttributes<HTMLElement> & { as?: "section" | "article" | "div" }) {
  return (
    <Tag className={`card ${className}`} {...rest}>
      {children}
    </Tag>
  );
}

export function StepTitle({
  step,
  children,
  id,
  right,
}: {
  step: string | number;
  children: React.ReactNode;
  id?: string;
  right?: React.ReactNode;
}) {
  return (
    <div className="step-row">
      <h2 id={id} className="step-title">
        <span className="step-badge" aria-hidden="true">
          {step}
        </span>
        {children}
      </h2>
      {right}
    </div>
  );
}

export function SectionTitle({
  index,
  children,
  note,
  id,
  level = 2,
}: {
  index?: string;
  children: React.ReactNode;
  note?: React.ReactNode;
  id?: string;
  level?: 2 | 3;
}) {
  const H = level === 3 ? "h3" : "h2";
  return (
    <header className="section-title">
      <H id={id}>
        {index && (
          <span className="section-index" aria-hidden="true">
            {index}
          </span>
        )}
        {children}
      </H>
      {note && <p className="section-note">{note}</p>}
    </header>
  );
}

export function Warning({ children }: { children: React.ReactNode }) {
  return (
    <aside className="warning" role="note">
      <InfoIcon />
      <p>{children}</p>
    </aside>
  );
}

export function Notice({
  children,
  tone = "info",
  role,
}: {
  children: React.ReactNode;
  tone?: "info" | "error";
  role?: "alert" | "status";
}) {
  return (
    <p className={`notice notice-${tone}`} role={role}>
      {children}
    </p>
  );
}

export function Stat({ value, label }: { value: React.ReactNode; label: string }) {
  return (
    <div className="stat">
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

/* ---------- Bảng ---------- */
export function Table({
  headers,
  rows,
  caption,
  className = "",
}: {
  headers: React.ReactNode[];
  rows: React.ReactNode[][];
  caption?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className="table-scroll">
      <table className={`table ${className}`}>
        {caption && <caption>{caption}</caption>}
        <thead>
          <tr>
            {headers.map((h, i) => (
              <th key={i} scope="col">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {row.map((v, j) =>
                j === 0 ? (
                  <th key={j} scope="row">
                    {v}
                  </th>
                ) : (
                  <td key={j}>{v}</td>
                ),
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ---------- Hình minh hoạ có phóng to ---------- */
export function Figure({
  id,
  alt,
  caption,
  className = "",
}: {
  id: string;
  alt: string;
  caption: React.ReactNode;
  className?: string;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  return (
    <figure className={`figure ${className}`}>
      <button
        type="button"
        className="figure-button"
        aria-label={`Phóng to: ${alt}`}
        onClick={() => dialog.current?.showModal()}
      >
        <img src={asset(id)} alt={alt} loading="lazy" />
      </button>
      <figcaption>
        {caption} <span className="muted">Bấm vào hình để phóng to.</span>
      </figcaption>
      <dialog
        ref={dialog}
        className="image-dialog"
        aria-label={alt}
        onClick={(e) => {
          if (e.target === dialog.current) dialog.current.close();
        }}
      >
        <button type="button" className="dialog-close" onClick={() => dialog.current?.close()}>
          <CloseIcon /> Đóng
        </button>
        <img src={asset(id)} alt={alt} />
        <p className="muted">{caption}</p>
      </dialog>
    </figure>
  );
}

/** Dòng chảy các bước (thay mũi tên emoji bằng SVG). */
export function Flow({ items }: { items: string[] }) {
  return (
    <ol className="flow">
      {items.map((item, i) => (
        <li key={item}>
          <span className="flow-index" aria-hidden="true">
            {i + 1}
          </span>
          <span>{item}</span>
          {i < items.length - 1 && <ArrowIcon size={18} className="flow-arrow" />}
        </li>
      ))}
    </ol>
  );
}
