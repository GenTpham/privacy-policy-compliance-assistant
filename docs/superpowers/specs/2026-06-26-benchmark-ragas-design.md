# RAG Benchmark Design Spec

## Mục tiêu
Đánh giá và so sánh hiệu năng của hệ thống RAG hiện tại (Optimized RAG) so với một hệ thống RAG cơ bản (Naive RAG) thường thấy trong doanh nghiệp. Việc đánh giá sử dụng tập dữ liệu chuẩn `BeIR/fiqa` (Financial QA) kết hợp với framework **Ragas** để có các chỉ số đo lường khách quan.

## Kiến trúc và Các bước triển khai

### Bước 1: Chuẩn bị Dữ liệu & Đưa vào Vector DB (Ingestion)
Tạo 2 môi trường lưu trữ độc lập trên Qdrant để so sánh:
1. **`fiqa_naive_rag` (Baseline):** 
   - Chunking: Phương pháp cơ bản (ví dụ cắt cứng theo kích thước ký tự/từ).
   - Embedding: Sử dụng mô hình phổ thông hoặc hệ thống mặc định không tối ưu.
2. **`fiqa_optimized_rag` (Hệ thống hiện tại):**
   - Lấy corpus từ FiQA và chạy qua toàn bộ pipeline Ingestion đã được tinh chỉnh của dự án (semantic chunking, xử lý metadata, embedding qua model Nemotron của hệ thống).

*Lưu ý: Để tối ưu chi phí và thời gian chạy thử, sẽ lấy một subset nhỏ của corpus FiQA chứa đáp án cho khoảng 100-200 câu hỏi test.*

### Bước 2: Truy xuất & Sinh câu trả lời (Inference Loop)
Chạy kịch bản giả lập người dùng đặt câu hỏi trên tập 100 câu test cho cả 2 hệ thống:
1. **Retrieval:** Lấy Top K chunks cho mỗi câu hỏi từ cả `fiqa_naive_rag` và `fiqa_optimized_rag`.
2. **Generation:** Sử dụng mô hình **OSS LLM đã được config sẵn trong hệ thống** để sinh câu trả lời (Answer) dựa trên câu hỏi và các chunks tìm được. (Tuyệt đối không hardcode Gemma 4 hoặc model ngoài cấu hình).
3. **Format Dữ Liệu:** Đóng gói kết quả đầu ra thành 2 danh sách dạng dictionary theo định dạng bắt buộc của Ragas:
   - `question`: Câu hỏi đầu vào.
   - `contexts`: Các chunks văn bản đã lấy (List of strings).
   - `answer`: Câu trả lời từ LLM OSS.
   - `ground_truth`: Câu trả lời đúng từ dataset FiQA.

### Bước 3: Đánh giá bằng Ragas & Báo cáo
Sử dụng framework **Ragas** để tự động chấm điểm chất lượng của pipeline:
1. **Judge LLM:** Cấu hình Ragas sử dụng chung mô hình OSS LLM của hệ thống bằng cách viết một LLM Wrapper (nếu cần thiết để tương thích).
2. **Các chỉ số (Metrics) sẽ đo lường:**
   - *Context Precision:* Đo lường độ chính xác và thứ hạng của chunk tìm được.
   - *Context Recall:* Đo lường độ đầy đủ thông tin của chunk so với ground truth.
   - *Faithfulness:* Đánh giá khả năng bám sát context của câu trả lời, không bịa đặt (hallucination).
   - *Answer Correctness:* Tính chính xác của câu trả lời sinh ra so với ground truth.
3. **Xuất báo cáo:** Chạy hàm `evaluate()` và lưu kết quả ra file `benchmark_report.csv` hoặc định dạng Markdown, làm nổi bật sự khác biệt về điểm số giữa Naive RAG và Optimized RAG.

## Yêu cầu kỹ thuật
- Không sử dụng LangChain cho luồng chính (Raw implementation) trừ khi phải dùng nội bộ bên trong Ragas.
- Tự động hóa thành script dễ chạy lại (e.g. `scripts/run_benchmark.py`).
