/**
 * 9 chip câu hỏi gợi ý ↔ 9 `question_type` của PlantVillageVQA.
 * Mỗi chip điền một câu đúng văn phong bộ dữ liệu (câu xuất hiện nhiều trong
 * outputs/final/PlantVillageVQA_vi.csv), vì model chỉ học 9 dạng này.
 * Nếu ảnh đang chọn có sẵn câu hỏi gốc cùng dạng thì giao diện ưu tiên câu gốc đó.
 */
export type Chip = {
  type: string;
  chip: string;
  hint: string;
  yesNo: boolean;
  template: (plant?: string, disease?: string) => string;
};

export const CHIPS: Chip[] = [
  {
    type: "General Health Assessment",
    chip: "Lá có khỏe không?",
    hint: "Đánh giá sức khỏe chung · trả lời Có/Không",
    yesNo: true,
    template: () =>
      "Lá này có biểu hiện các triệu chứng cho thấy bị nhiễm bệnh không?",
  },
  {
    type: "Plant Species Identification",
    chip: "Đây là cây gì?",
    hint: "Nhận dạng loài cây",
    yesNo: false,
    template: () => "Hãy xác định phân loại thực vật của mẫu cây này.",
  },
  {
    type: "Specific Disease Identification",
    chip: "Lá bị bệnh gì?",
    hint: "Gọi tên bệnh cụ thể",
    yesNo: false,
    template: (plant) =>
      plant
        ? `Loại tình trạng bệnh lý nào thể hiện rõ trên lá ${plant} này?`
        : "Cây này đang mắc bệnh hoặc rối loạn gì?",
  },
  {
    type: "Causal Reasoning",
    chip: "Vì sao lá bị như vậy?",
    hint: "Suy luận nguyên nhân",
    yesNo: false,
    template: (plant) =>
      plant
        ? `Những yếu tố nào là nguyên nhân gây ra sự suy yếu của lá ${plant} này?`
        : "Tác nhân gây bệnh hoặc yếu tố môi trường nào gây ra các triệu chứng này?",
  },
  {
    type: "Comprehensive Description",
    chip: "Mô tả những gì thấy trên lá",
    hint: "Mô tả tổng hợp",
    yesNo: false,
    template: () =>
      "Bạn có thể đưa ra đánh giá trực quan chi tiết về mẫu thực vật này không?",
  },
  {
    type: "Visual Attribute Grounding",
    chip: "Có vết đốm đặc trưng không?",
    hint: "Xác nhận một đặc điểm nhìn thấy · Có/Không · sửa mô tả vết bệnh nếu cần",
    yesNo: true,
    template: () =>
      "Có các đốm tròn với viền sẫm màu và vùng giữa nhạt màu không?",
  },
  {
    type: "Detailed Verification",
    chip: "Có phải bệnh … không?",
    hint: "Kiểm chứng một bệnh cụ thể · Có/Không · sửa tên cây/bệnh trong câu",
    yesNo: true,
    template: (plant, disease) =>
      plant
        ? `Lá ${plant} này có bị nhiễm bệnh ${disease ?? "đốm vi khuẩn"} không?`
        : `Lá này có bị bệnh ${disease ?? "đốm vi khuẩn"} không?`,
  },
  {
    type: "Counterfactual Reasoning",
    chip: "Nếu khỏe thì khác gì?",
    hint: "Suy luận phản thực tế",
    yesNo: false,
    template: () =>
      "Một cây khỏe mạnh sẽ có những đặc điểm nào mà cây này hiện không có?",
  },
  {
    type: "Existence & Sanity Check",
    chip: "Ảnh có lá cây không?",
    hint: "Kiểm tra ảnh có lá hay không · Có/Không",
    yesNo: true,
    template: () => "Trong hình ảnh này có lá cây không?",
  },
];

/** Tên tiếng Việt ngắn cho từng question_type (dùng ở trang Bộ dữ liệu / Kết quả). */
export const QTYPE_VI: Record<string, string> = {
  "General Health Assessment": "Đánh giá sức khỏe chung",
  "Plant Species Identification": "Nhận dạng loài cây",
  "Specific Disease Identification": "Nhận dạng bệnh cụ thể",
  "Causal Reasoning": "Suy luận nguyên nhân",
  "Comprehensive Description": "Mô tả tổng hợp",
  "Visual Attribute Grounding": "Xác nhận đặc điểm nhìn thấy",
  "Detailed Verification": "Kiểm chứng chi tiết",
  "Counterfactual Reasoning": "Suy luận phản thực tế",
  "Existence & Sanity Check": "Kiểm tra sự tồn tại của lá",
};
export const qtypeVi = (t: string) => QTYPE_VI[t] ?? t;
