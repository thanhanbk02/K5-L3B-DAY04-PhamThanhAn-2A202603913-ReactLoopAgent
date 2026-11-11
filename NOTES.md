# Ghi chú phân tích · Day 04

Họ và tên: Phạm Thành An
MSSV: 2A202603913

Cấu hình eval: agent `ollama / qwen2.5:7b`, judge `ollama / qwen2.5:14b`, snapshot, `max_steps = 8`, dataset core (22 case).

## 1. Case được chọn

- ID case: **E4** (cùng lỗi xuất hiện ở **H5**).
  - E4: "Xem incident GitHub xr3myzj7ms51: những component được ghi nhận nào bị ảnh hưởng? Actions có liên quan không?"
- Câu trả lời của agent (E4), nguyên văn trong `eval_before.json`:
  `"brtc\n{\"name\": \"get_incident_details\", \"arguments\": {\"provider\": \"github\", \"incident_id\": \"xr3myzj7ms51\"}}\n</tool_call>"`
- Điểm ở lần chạy 1: **E4 = 40** (factuality 20, completeness 0, evidence 5, boundaries 15); **H5 = 50** (bị trần 50 vì "Chưa gọi tool cần thiết: get_status").

## 2. Bằng chứng trong trace

Trace E4 trong `eval_before.json`: chỉ có một lần gọi model, không có event `tool` nào, nhưng run vẫn `completed`.

```text
E4 trace:
  {"event": "model", "step": 1, "finish": "stop", "tool_calls": 0}
  {"event": "final", "step": 1}
answer: "brtc\n{\"name\": \"get_incident_details\", \"arguments\": {...}}\n</tool_call>"
grade.mechanical: tool_calls = 0, tool_steps = 0
grade.reason: "Agent không cung cấp thông tin chi tiết về incident ...; chỉ có tool call nhưng không thu được kết quả."

H5 trace (cùng kiểu lỗi):
  {"event": "model", "step": 1, "finish": "stop", "tool_calls": 0}
  {"event": "final", "step": 1}
answer: "ronics\n{\"name\": \"get_status\", \"arguments\": {\"component\": \"github-actions\", \"provider\": \"github\"}}\n</tool_call>"
grade.mechanical.violations: ["Chưa gọi tool cần thiết: get_status"]
```

Nguyên nhân có thể:

- **Model:** `qwen2.5:7b` muốn gọi tool nhưng sinh tool call dạng văn bản, kèm token rác ở đầu (`brtc`, `ronics`). Parser tool call của Ollama không nhận ra định dạng này, nên response có `calls = []`, `finish = "stop"` và toàn bộ JSON nằm trong `content`.
- **Loop (nguyên nhân chính, sửa được trong `agent.py`):** agent coi mọi response "không có tool call + `finish == "stop"`" là câu trả lời cuối, không kiểm tra nội dung. Vì vậy tool không bao giờ được thực thi và người dùng nhận một chuỗi JSON vô nghĩa với trạng thái `completed`.
- Lỗi không ổn định: lần chạy thử ở CP2 cũng gặp một lần (`">×</tools> {"name": "get_status", ...}</tool_call>"`). Chạy lại riêng E4/H5 thì model gọi tool bình thường. Đây là lỗi ngẫu nhiên của model nhỏ, nên loop cần chặn nó thay vì trông vào việc model không mắc lỗi.

## 3. Thay đổi đã thực hiện

- Sửa gì, ở đâu (`agent.py`):
  - Thêm hàm `_validate_answer(answer, source_urls)`. Hàm này chạy **trước khi** chấp nhận final answer (nhánh không có tool call và `finish == "stop"` trong `run_agent`).
  - **Phát hiện tool call bị in ra dạng văn bản** bằng regex `MALFORMED_TOOL_CALL`: tìm `<tool_call>`/`</tool_call>` hoặc mẫu `{"name": "...", "arguments": ...}`. Khi khớp, agent ghi event `validation_malformed_tool_call` vào trace (kèm `answer_preview`), thêm một message phản hồi yêu cầu model gọi lại tool qua function calling, rồi tiếp tục loop.
  - **Kiểm tra nguồn** (contract `tests/test_validation.py`): lưu `url` từ mỗi `get_incident_details` thành công. Nếu answer không chứa URL nào trong số đó, agent ghi `validation_missing_source` và yêu cầu model viết lại kèm URL. Nếu không có incident nào đọc thành công thì không bắt buộc URL.
  - Cả hai kiểm tra chỉ dùng số step còn lại. Hết `max_steps` mà answer vẫn chưa đạt thì trả `max_steps`, không báo `completed`.
  - Thêm `tests/test_improvement.py`, dùng đúng output hỏng thật của E4: agent phải retry, thực thi tool, rồi mới `completed`. Hết budget thì trả `max_steps`. Câu trả lời bình thường không bị chặn nhầm.
- Vì sao chọn thay đổi này:
  - Lỗi nằm ở loop (tin `finish == "stop"` mà không kiểm tra nội dung), nên sửa ở loop có tác dụng với mọi câu hỏi, không phụ thuộc vào việc model tuân theo prompt.
  - Bằng chứng rõ ràng và đo được: trace có `tool_calls = 0` và answer là JSON. Regex đã kiểm tra trên toàn bộ 22 answer của `eval_before.json`: khớp đúng E4 và H5, không khớp nhầm case nào khác.
  - Gửi phản hồi cho model (thay vì tự parse JSON trong text rồi chạy tool) giữ đúng contract: assistant message được append nguyên vẹn và mọi tool result đều gắn `tool_call_id` thật do provider sinh ra.
  - Giới hạn: regex chỉ bắt các dạng rò rỉ đã quan sát. Nó không sửa các lỗi khác như trả lời bằng tiếng Trung, không theo liên kết (H1/H6) hay không kiểm tra tiền đề (H2/H3).

## 4. So sánh hai lần chạy

| Chỉ số | `eval_before.json` | `eval_after.json` |
|---|---|---|
| Điểm tổng |  |  |
| Điểm case đã chọn |  |  |
| Số model calls |  |  |
| Token, chi phí nếu có |  |  |

- Lỗi đã giải quyết:
- Lỗi còn lại hoặc mới xuất hiện:

## 5. Giới hạn

Nêu giới hạn của điểm judge, của snapshot và của việc chỉ chạy một lần mỗi phiên bản.
