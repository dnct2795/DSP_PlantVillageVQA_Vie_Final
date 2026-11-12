/**
 * Nhãn tiếng Việt cho ảnh mẫu. Nguồn: câu hỏi/đáp án gốc của chính ảnh đó trong bộ dữ liệu
 * (generated/samples.json) và manifest ảnh ngoài vườn (samples/real-world/manifest.json).
 * Ảnh không nêu rõ loài cây trong đáp án thì để nhãn trung tính, không đoán.
 */
export type SampleMeta = {
  label: string; // nhãn ngắn hiện trên ảnh
  plant?: string; // tên cây dùng để điền vào câu hỏi mẫu
  disease?: string; // tên bệnh dùng cho chip "Có phải bệnh … không?"
  origin: "PlantVillage" | "Ngoài vườn";
};

export const SAMPLE_META: Record<string, SampleMeta> = {
  "image_046993.JPG": {
    label: "Lá cà chua · xoăn vàng lá",
    plant: "cà chua",
    disease: "xoăn vàng lá cà chua",
    origin: "PlantVillage",
  },
  "image_044461.JPG": {
    label: "Lá cam · vàng lá gân xanh",
    plant: "cam",
    disease: "vàng lá gân xanh",
    origin: "PlantVillage",
  },
  "image_046583.JPG": { label: "Lá táo", plant: "táo", origin: "PlantVillage" },
  "image_049476.JPG": {
    label: "Lá ớt chuông",
    plant: "ớt chuông",
    disease: "đốm vi khuẩn",
    origin: "PlantVillage",
  },
  "image_045864.JPG": { label: "Lá khỏe mạnh", origin: "PlantVillage" },
  "image_044441.JPG": { label: "Lá có dấu hiệu bệnh", origin: "PlantVillage" },
  "image_047791.JPG": { label: "Lá khỏe mạnh (ví dụ 2)", origin: "PlantVillage" },
  "image_047771.JPG": {
    label: "Lá cây có múi · vàng lá gân xanh",
    plant: "cam",
    disease: "vàng lá gân xanh",
    origin: "PlantVillage",
  },
  "image_044957.jpg": { label: "Ảnh không có lá (kiểm tra)", origin: "PlantVillage" },
  "rw01_tomato_early_blight.jpg": {
    label: "Cà chua ngoài vườn · đốm vòng",
    plant: "cà chua",
    disease: "đốm vòng",
    origin: "Ngoài vườn",
  },
  "rw02_tomato_late_blight.jpg": {
    label: "Cà chua ngoài vườn · mốc sương",
    plant: "cà chua",
    disease: "mốc sương",
    origin: "Ngoài vườn",
  },
  "rw03_apple_scab.jpg": {
    label: "Táo ngoài vườn · ghẻ táo",
    plant: "táo",
    disease: "ghẻ táo",
    origin: "Ngoài vườn",
  },
  "rw04_grape_black_rot.jpg": {
    label: "Nho ngoài vườn · thối đen",
    plant: "nho",
    disease: "thối đen",
    origin: "Ngoài vườn",
  },
  "rw05_corn_common_rust.jpg": {
    label: "Ngô ngoài ruộng · gỉ sắt",
    plant: "ngô",
    disease: "gỉ sắt thường",
    origin: "Ngoài vườn",
  },
};

export const metaOf = (imageId: string): SampleMeta =>
  SAMPLE_META[imageId] ?? {
    label: imageId.replace(/\.[^.]+$/, ""),
    origin: imageId.startsWith("rw") ? "Ngoài vườn" : "PlantVillage",
  };
