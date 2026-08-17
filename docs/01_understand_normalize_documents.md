# Bước 1 — Understand & Normalize Documents

## 1. Mục tiêu của bước này

Trước khi nghĩ đến Embedding, Vector DB, Gemini hay RAG, việc đầu tiên là biến dữ liệu thô thành một tập document mà bạn **hiểu rõ và kiểm soát được**.

Với bộ dữ liệu contract hiện tại:

```text
data/raw/
├── CUAD_v1.json
├── CUAD_v1_README.txt
├── master_clauses.csv
├── full_contract_pdf/      # 510 PDF
├── full_contract_txt/      # 510 TXT
└── label_group_xlsx/       # 28 XLSX
```

Mục tiêu của bước 1 là đi từ:

```text
raw files
   ↓
inspect
   ↓
clean / normalize
   ↓
contracts.jsonl
```

Chưa có AI ở đây.

---

# 2. Vì sao không nên nhảy thẳng vào Embedding?

Nếu chưa hiểu dữ liệu mà đã embed, bạn có thể đưa vào Vector DB:

- file rỗng;
- file parse lỗi;
- header/footer lặp lại;
- page number;
- duplicate document;
- ký tự rác từ PDF → TXT;
- tài liệu rất ngắn nhưng hợp lệ;
- tài liệu không thực sự là “contract dài” mà là exhibit, amendment, filing agreement;
- metadata sai hoặc mất nguồn gốc tài liệu.

Khi đó Vector DB vẫn chạy bình thường, nhưng retrieval sẽ kém mà bạn không biết nguyên nhân.

RAG tốt bắt đầu từ data tốt.

---

# 3. Vai trò của từng loại dữ liệu

## `full_contract_txt/`

Đây nên là nguồn text chính ở phiên bản đầu.

Lý do:

- đã có text;
- dễ đọc;
- dễ normalize;
- dễ chunk;
- không cần parse PDF lại từ đầu.

Pipeline ban đầu:

```text
TXT
 ↓
Normalize
 ↓
Chunk
 ↓
Embedding
```

## `full_contract_pdf/`

PDF nên được giữ làm:

- tài liệu gốc;
- source để người dùng mở lại;
- kiểm tra layout;
- đối chiếu khi TXT bị lỗi;
- về sau có thể dùng để lấy page number/citation chính xác.

Không cần embed PDF trực tiếp ở bản đầu nếu TXT đã dùng được.

## `master_clauses.csv`

Đây là dữ liệu annotation/ground truth rất giá trị.

Ở giai đoạn đầu, **không nên dùng nó như đáp án để giúp retriever tìm clause**, nếu mục tiêu của bạn là đánh giá retrieval công bằng.

Nên dùng về sau cho:

- evaluation;
- golden dataset;
- so sánh predicted clause với expected clause.

## `CUAD_v1.json`

Có thể dùng về sau để:

- tạo evaluation queries;
- kiểm tra answer span;
- benchmark retrieval;
- benchmark question answering.

## `label_group_xlsx/`

Chưa cần dùng ở MVP.

Nó phù hợp hơn cho:

- phân tích annotation;
- xem clause theo nhóm;
- debugging;
- nghiên cứu taxonomy clause.

---

# 4. Đầu tiên phải inspect dữ liệu

Bạn cần biết bộ 510 contract của mình trông như thế nào.

Các thống kê cơ bản nên có:

```text
Total documents
Min words
Max words
Average words
Median words
P90
P95
Empty files
Top 10 shortest
Top 10 longest
```

Kết quả bạn đã quan sát:

```text
Min     ≈ 109 từ
Max     ≈ 47,733 từ
Average ≈ 7,861 từ
Median  ≈ 5,006 từ
P90     ≈ 18,610 từ
P95     ≈ 25,203 từ
```

Điều này cho thấy dữ liệu bị lệch phải:

- phần lớn contract ở mức ngắn/trung bình;
- một nhóm nhỏ dài hơn đáng kể;
- không cần thiết kế toàn bộ hệ thống chỉ để xử lý nhóm cực dài.

---

# 5. Hiểu Median, P90, P95

## Median

```text
Median = 5,006 words
```

Có nghĩa:

> Khoảng 50% document có số từ nhỏ hơn hoặc bằng khoảng 5,006.

Median hữu ích hơn average khi distribution có một số file rất dài.

## P90

```text
P90 = 18,610 words
```

Có nghĩa:

> Khoảng 90% document có độ dài không vượt quá 18,610 từ.

Chỉ khoảng 10% dài hơn.

## P95

```text
P95 = 25,203 words
```

Có nghĩa:

> Khoảng 95% document có độ dài không vượt quá 25,203 từ.

Chỉ khoảng 5% dài hơn.

Với 510 documents:

```text
5% × 510 ≈ 25 documents
```

Tức chỉ có khoảng 25 document nằm ở phần cực dài.

---

# 6. Đừng loại document chỉ vì nó ngắn

Ví dụ bạn gặp document chỉ khoảng 109 từ:

```text
Exhibit 99.1
JOINT FILING AGREEMENT
...
```

Đây không nhất thiết là lỗi.

Nó có thể là:

- Joint Filing Agreement;
- Amendment;
- Exhibit;
- Schedule;
- một thỏa thuận rất ngắn.

Vì vậy không nên đặt rule kiểu:

```text
if words < 500:
    delete_document()
```

Đó là rule nguy hiểm.

Cách đúng là:

```text
document rất ngắn
      ↓
inspect vài mẫu
      ↓
xác định hợp lệ hay parse lỗi
```

---

# 7. Data cleaning cần cẩn thận

Contract có nhiều số và ký hiệu mang ý nghĩa pháp lý.

Ví dụ:

```text
Section 13D
Rule 13d-1(k)
30 days
January 22, 2020
Section 8.2
```

Do đó không được clean kiểu:

```text
xóa mọi số
xóa mọi dòng ngắn
xóa mọi ký tự đặc biệt
```

Bạn chỉ nên normalize những thứ tương đối an toàn:

- whitespace thừa;
- nhiều dòng trống liên tiếp;
- ký tự control;
- encoding lỗi;
- page number nếu đã xác nhận chắc chắn;
- header/footer lặp lại nếu xác nhận được.

Nguyên tắc:

> Clean đủ để retrieval tốt hơn, nhưng không làm mất ý nghĩa pháp lý.

---

# 8. Document normalization là gì?

Normalization nghĩa là biến mỗi raw file thành một record có schema thống nhất.

Ví dụ:

```json
{
  "contract_id": "contract_0001",
  "filename": "ABC_SERVICE_AGREEMENT.txt",
  "contract_type": "Service",
  "dataset_part": "Part_I",
  "source_txt": "data/raw/full_contract_txt/...",
  "source_pdf": "data/raw/full_contract_pdf/...",
  "text": "THIS SERVICE AGREEMENT...",
  "word_count": 7861
}
```

Mỗi document dù ngắn hay dài đều về cùng một format.

---

# 9. Tại sao cần `contracts.jsonl`?

JSONL = mỗi dòng là một JSON object.

Ví dụ:

```json
{"contract_id":"c001","contract_type":"Service","text":"..."}
{"contract_id":"c002","contract_type":"License","text":"..."}
{"contract_id":"c003","contract_type":"Franchise","text":"..."}
```

Ưu điểm:

- dễ stream;
- dễ đọc từng record;
- không cần load toàn bộ dataset vào memory;
- dễ debug;
- dễ dùng cho bước chunking;
- dễ version control hơn các format phức tạp.

---

# 10. Schema tối thiểu cho `contracts.jsonl`

Bạn có thể bắt đầu bằng:

```text
contract_id
filename
contract_type
dataset_part
source_txt
source_pdf
text
word_count
char_count
```

Ví dụ:

```json
{
  "contract_id": "contract_0042",
  "filename": "example_agreement.txt",
  "contract_type": "Service",
  "dataset_part": "Part_I",
  "source_txt": "full_contract_txt/example_agreement.txt",
  "source_pdf": "full_contract_pdf/Part_I/Service/example_agreement.pdf",
  "text": "THIS SERVICE AGREEMENT...",
  "word_count": 5321,
  "char_count": 34892
}
```

---

# 11. `contract_id` dùng để làm gì?

Không nên dựa hoàn toàn vào filename.

Tạo một ID nội bộ ổn định:

```text
contract_0001
contract_0002
contract_0003
```

Sau này mọi thứ liên kết bằng:

```text
contract_id
```

Ví dụ:

```text
contract
   ↓
chunks
   ↓
vector records
   ↓
retrieval result
   ↓
citation
```

Tất cả đều giữ `contract_id`.

---

# 12. Nguồn của metadata document

Một số metadata có thể lấy trực tiếp từ folder.

Ví dụ:

```text
Part_I/
└── Service/
    └── ABC_AGREEMENT.pdf
```

Ta có thể suy ra:

```json
{
  "dataset_part": "Part_I",
  "contract_type": "Service"
}
```

Không cần Gemini.

Không cần classifier.

Không cần embedding.

Luôn ưu tiên metadata có nguồn rõ ràng hơn metadata do model đoán.

---

# 13. Script nên có ở bước 1

Có thể tách thành:

```text
scripts/
├── inspect_contracts.py
└── normalize_contracts.py
```

## `inspect_contracts.py`

Nhiệm vụ:

```text
đếm file
đo word count
đo char count
phát hiện empty
thống kê min/max/average/median/P90/P95
in top shortest
in top longest
```

## `normalize_contracts.py`

Nhiệm vụ:

```text
read TXT
↓
normalize whitespace
↓
gắn contract_id
↓
gắn source
↓
gắn contract_type / part
↓
ghi contracts.jsonl
```

Không chunk.

Không embed.

Không gọi LLM.

---

# 14. Bước 1 hoàn thành khi nào?

Bước 1 hoàn thành khi bạn có:

```text
data/processed/contracts.jsonl
```

và có thể lấy bất kỳ dòng nào rồi giải thích được:

- text đến từ file nào;
- PDF gốc ở đâu;
- contract này thuộc loại nào;
- contract ID là gì;
- document dài bao nhiêu;
- dữ liệu đã được clean những gì.

Flow lúc này:

```text
RAW DATA
   ↓
Inspect
   ↓
Normalize
   ↓
contracts.jsonl
```

---

# 15. Những thứ chưa nên làm ở bước 1

Chưa cần:

```text
Embedding
Vector DB
LangChain
LangGraph
Reranker
Hybrid Search
LLM classification
Agent
```

Nếu một script normalize cần Gemini mới chạy được, nhiều khả năng đang over-engineer.

---

# 16. Checklist bước 1

- [ ] Đếm đủ số TXT
- [ ] Kiểm tra file rỗng
- [ ] Tính min/max/average/median/P90/P95
- [ ] Đọc 5–10 file ngắn nhất
- [ ] Đọc 5–10 file dài nhất
- [ ] Kiểm tra PDF tương ứng với một số TXT
- [ ] Xác định noise phổ biến
- [ ] Xác định schema document
- [ ] Tạo `contract_id`
- [ ] Tạo `contracts.jsonl`
- [ ] Kiểm tra ngẫu nhiên ít nhất 20 records

---

# 17. Tư duy cần nhớ

Bước 1 không phải "tiền xử lý cho có".

Đây là lúc bạn trả lời:

```text
Tôi đang có dữ liệu gì?
Nó có đáng tin không?
Một document là gì?
Nguồn của document ở đâu?
Có metadata tự nhiên nào?
Có noise gì?
```

Nếu bước này tốt, những bước RAG phía sau sẽ dễ hơn rất nhiều.

---

# 18. Input và Output của bước 1

## Input

```text
full_contract_txt/
full_contract_pdf/
folder structure
```

## Processing

```text
inspect
normalize
clean nhẹ
gắn ID
gắn source
```

## Output

```text
contracts.jsonl
```

Đây là document layer chuẩn để bước 2 — Chunking — sử dụng.
