# Bước 3 — Metadata cho Contract RAG

## 1. Metadata là gì?

Metadata là:

> Dữ liệu mô tả một document hoặc chunk.

Ví dụ chunk:

```text
Either party may terminate this Agreement...
```

Nếu chỉ lưu text, hệ thống không biết:

- nó thuộc contract nào;
- thuộc loại contract gì;
- section nào;
- chunk thứ mấy;
- source file nào;
- PDF gốc ở đâu.

Metadata giải quyết việc đó.

---

# 2. Tại sao Metadata quan trọng?

Vector search trả về:

```text
chunk A
chunk B
chunk C
```

Nhưng ứng dụng thực tế cần biết:

```text
chunk A thuộc contract nào?
có đúng contract user đang hỏi không?
thuộc Service Agreement hay License Agreement?
nằm ở section nào?
nguồn nào để citation?
```

Metadata giúp:

- filter;
- trace source;
- citation;
- debug;
- phân nhóm;
- giới hạn search scope;
- tăng precision.

---

# 3. Hai tầng metadata

Nên tách tư duy thành:

```text
DOCUMENT METADATA
        ↓
     Contract
        ↓
      Chunk
        ↓
CHUNK METADATA
```

---

# 4. Document metadata

Thông tin áp dụng cho toàn contract.

Ví dụ:

```json
{
  "contract_id": "contract_0042",
  "filename": "ABC_SERVICE_AGREEMENT.txt",
  "contract_type": "Service",
  "dataset_part": "Part_I",
  "source_txt": "...",
  "source_pdf": "...",
  "word_count": 5321
}
```

Những field này có thể copy xuống mỗi chunk.

---

# 5. Chunk metadata

Thông tin riêng cho từng chunk.

Ví dụ:

```json
{
  "chunk_id": "contract_0042_chunk_0013",
  "contract_id": "contract_0042",
  "chunk_index": 13,
  "section_number": "8.2",
  "section": "Termination for Cause",
  "token_count": 987
}
```

Kết hợp document + chunk metadata sẽ tạo một vector record đầy đủ.

---

# 6. Schema V1 nên đơn giản

Đề xuất:

```text
chunk_id
contract_id
chunk_index

dataset_part
contract_type

section
section_number

token_count

source_txt
source_pdf

text
```

Đây là đủ cho phiên bản đầu.

---

# 7. Ví dụ record hoàn chỉnh

```json
{
  "chunk_id": "contract_0042_chunk_0013",
  "contract_id": "contract_0042",
  "chunk_index": 13,

  "dataset_part": "Part_I",
  "contract_type": "Service",

  "section_number": "8.2",
  "section": "Termination for Cause",

  "token_count": 987,

  "source_txt": "ABC_SERVICE_AGREEMENT.txt",
  "source_pdf": "ABC_SERVICE_AGREEMENT.pdf",

  "text": "Either party may terminate this Agreement..."
}
```

---

# 8. `contract_id`

Là khóa liên kết chính.

Dùng để:

```text
contract
↕
chunk
↕
vector result
↕
source
↕
evaluation
```

Khi user hỏi một contract cụ thể, metadata filter có thể là:

```text
contract_id = "contract_0042"
```

---

# 9. `chunk_id`

ID duy nhất của mỗi chunk.

Ví dụ:

```text
contract_0042_chunk_0013
```

Giúp:

- debug;
- trace retrieval;
- ghi log;
- evaluation;
- lấy neighboring chunks.

---

# 10. `chunk_index`

Ví dụ:

```text
13
```

Nghĩa là chunk thứ 13 trong contract.

Sau này nếu chunk 13 được retrieve, bạn có thể lấy thêm:

```text
chunk 12
chunk 13
chunk 14
```

để mở rộng context.

---

# 11. `dataset_part`

Có thể lấy từ folder:

```text
Part_I
Part_II
Part_III
```

Không cần model đoán.

Ví dụ:

```json
{
  "dataset_part": "Part_I"
}
```

---

# 12. `contract_type`

Có thể lấy từ folder category:

```text
Service
License_Agreements
Franchise
Supply
Transportation
...
```

Ví dụ:

```json
{
  "contract_type": "Service"
}
```

Metadata này sau này rất hữu ích cho query:

```text
Find termination clauses in Service agreements
```

Ta có thể filter:

```text
contract_type = Service
```

rồi mới vector search.

---

# 13. `section`

Ví dụ text:

```text
8. TERMINATION

Either party may terminate...
```

Metadata:

```json
{
  "section": "Termination",
  "section_number": "8"
}
```

Subsection:

```text
8.2 Termination for Cause
```

Metadata:

```json
{
  "section": "Termination for Cause",
  "section_number": "8.2"
}
```

---

# 14. Nếu detect section không được thì sao?

Để:

```json
{
  "section": null,
  "section_number": null
}
```

Điều này tốt hơn việc gọi LLM đoán bừa.

V1 không cần section detection hoàn hảo 100%.

---

# 15. Metadata lấy từ đâu?

Thứ tự ưu tiên:

```text
1. Folder / file path
2. Text structure rõ ràng
3. Deterministic parser
4. External trusted metadata
5. Model inference — để sau
```

Nguyên tắc:

> Cái gì có thể lấy chắc chắn thì không nên cho LLM đoán.

---

# 16. RAG metadata và Ground Truth phải tách biệt

Đây là phần cực kỳ quan trọng với CUAD.

Bạn có:

```text
master_clauses.csv
CUAD_v1.json
```

chứa annotation/answer.

Nếu bạn dùng trực tiếp ground truth để gắn:

```json
{
  "clause_type": "Termination"
}
```

cho chunk rồi retrieval filter theo `clause_type`, bạn đang vô tình cho hệ thống biết đáp án.

Ví dụ user hỏi:

```text
Find termination clause
```

Nếu retriever làm:

```text
WHERE clause_type = "Termination"
```

thì bài toán gần như đã được giải sẵn bởi annotation.

Evaluation sẽ không còn công bằng.

---

# 17. Cần tách hai thế giới

## RAG-visible data

Ví dụ `chunks.jsonl`:

```json
{
  "chunk_id": "c001_chunk_017",
  "contract_id": "c001",
  "contract_type": "Service",
  "section": "Termination",
  "chunk_index": 17,
  "token_count": 954,
  "text": "Either party may terminate..."
}
```

Đây là thứ retrieval được nhìn.

## Ground truth

Ví dụ `annotations.jsonl`:

```json
{
  "contract_id": "c001",
  "clause_type": "Termination",
  "expected_answer": "Either party may terminate..."
}
```

Đây là thứ dùng để chấm hệ thống.

---

# 18. Có một ngoại lệ cần hiểu

`section = "Termination"` lấy trực tiếp từ heading trong document khác với:

```text
clause_type = "Termination"
```

được lấy từ annotation CUAD.

Heading là thông tin tồn tại tự nhiên trong document.

Annotation là nhãn do con người cung cấp.

Hai thứ không hoàn toàn giống nhau.

Bạn có thể dùng heading làm metadata nếu parser đọc được từ raw contract.

Nhưng tránh lấy ground truth labels để "giúp" retrieval khi đang benchmark.

---

# 19. Metadata filter hoạt động thế nào?

Giả sử Vector DB có:

```text
15,000 chunks
```

User chọn contract:

```text
ABC Service Agreement
```

Query:

```text
What are the termination conditions?
```

Thay vì search toàn bộ:

```text
15,000 chunks
```

ta filter:

```text
contract_id = abc_service
```

có thể còn:

```text
30 chunks
```

rồi mới vector search.

Flow:

```text
Query
 ↓
Metadata Filter
 ↓
Vector Search
 ↓
Top-K
```

---

# 20. Ví dụ filter theo contract type

User hỏi:

```text
Find clauses related to renewal in Service Agreements.
```

Ta có thể:

```text
contract_type = Service
```

rồi semantic search:

```text
renewal clauses
```

Flow:

```text
All chunks
   ↓
Filter Service
   ↓
Vector similarity
   ↓
Top-K
```

---

# 21. Metadata không thay thế Embedding

Metadata trả lời:

```text
Search ở đâu?
```

Embedding trả lời:

```text
Trong scope đó, đoạn nào giống nghĩa query nhất?
```

Hai thứ bổ trợ nhau.

Ví dụ:

```text
metadata filter:
contract_id = c001
```

sau đó:

```text
vector search:
termination conditions
```

---

# 22. Metadata không nên quá nhiều ngay từ đầu

Chưa cần:

```text
party_a
party_b
jurisdiction
effective_date
expiration_date
risk_level
clause_type
obligation_type
monetary_value
renewal_type
```

Nếu chưa có use case cụ thể.

Metadata nên xuất phát từ query thực tế.

Ví dụ nếu app cần:

```text
search trong một contract cụ thể
```

thì `contract_id` quan trọng.

Nếu cần:

```text
search theo loại contract
```

thì `contract_type` quan trọng.

---

# 23. Metadata tốt phải có 3 tính chất

## Có nguồn rõ ràng

Bạn biết field đến từ đâu.

## Ổn định

Không thay đổi mỗi lần chạy.

## Có ích cho retrieval hoặc traceability

Nếu field không dùng cho:

- filter;
- citation;
- debug;
- display;
- evaluation;

thì chưa chắc cần lưu.

---

# 24. Source metadata

Nên giữ:

```text
source_txt
source_pdf
```

Ví dụ:

```json
{
  "source_txt": "data/raw/full_contract_txt/abc.txt",
  "source_pdf": "data/raw/full_contract_pdf/Part_I/Service/abc.pdf"
}
```

Sau này retrieval trả chunk, frontend có thể:

```text
Answer
+
Source contract
+
Open PDF
```

---

# 25. Page number thì sao?

Nếu TXT không có mapping chính xác với PDF page, đừng bịa:

```json
{
  "page": 17
}
```

Chỉ thêm page khi có pipeline xác định được page thật.

Citation sai page tệ hơn việc không có page.

---

# 26. Ví dụ document rất ngắn

Joint Filing Agreement:

```json
{
  "chunk_id": "contract_0183_chunk_0000",
  "contract_id": "contract_0183",
  "chunk_index": 0,

  "dataset_part": "Part_III",
  "contract_type": "Joint Venture / Filing",

  "section_number": null,
  "section": "Joint Filing Agreement",

  "token_count": 160,

  "source_txt": "...txt",
  "source_pdf": "...pdf",

  "text": "Exhibit 99.1 JOINT FILING AGREEMENT..."
}
```

Một document có một chunk vẫn có metadata đầy đủ như document dài.

---

# 27. Có nên dùng filename làm `contract_type`?

Không nếu đã có folder category tốt hơn.

Ví dụ path:

```text
Part_I/Service/ABC.txt
```

thì lấy:

```text
contract_type = Service
```

từ folder.

Filename thường không ổn định hoặc khó parse hơn.

---

# 28. Có nên dùng Gemini để extract metadata?

Ở V1: chưa nên.

Chưa cần Gemini cho:

```text
contract_type
dataset_part
source
chunk_index
token_count
section_number
```

Nếu về sau cần field khó:

```text
party names
effective date
jurisdiction
renewal mechanism
```

thì có thể cân nhắc parser/LLM extraction riêng.

Nhưng đó là phase khác.

---

# 29. Metadata được lưu ở đâu?

Trong `chunks.jsonl`:

```json
{
  "chunk_id": "...",
  "contract_id": "...",
  "metadata": {
    "contract_type": "Service",
    "dataset_part": "Part_I",
    "section": "Termination"
  },
  "text": "..."
}
```

Hoặc flat schema:

```json
{
  "chunk_id": "...",
  "contract_id": "...",
  "contract_type": "Service",
  "dataset_part": "Part_I",
  "section": "Termination",
  "text": "..."
}
```

Cả hai đều được.

Flat schema thường dễ debug hơn ở giai đoạn đầu.

---

# 30. Sau này Vector DB sẽ lưu gì?

Khái niệm:

```text
Vector record
├── id
├── embedding
├── text
└── metadata
```

Ví dụ:

```json
{
  "id": "contract_0042_chunk_0013",
  "embedding": [0.023, -0.182, 0.741],
  "text": "Either party may terminate...",
  "metadata": {
    "contract_id": "contract_0042",
    "contract_type": "Service",
    "section": "Termination for Cause",
    "chunk_index": 13
  }
}
```

Embedding sẽ được tạo ở bước 4.

---

# 31. Bước 3 hoàn thành khi nào?

Khi mỗi chunk trả lời được:

```text
Tôi là chunk nào?
Tôi thuộc contract nào?
Tôi đứng thứ mấy?
Tôi thuộc loại contract gì?
Tôi nằm ở section nào nếu biết?
Nguồn TXT ở đâu?
PDF gốc ở đâu?
Tôi dài bao nhiêu token?
```

---

# 32. Workflow bước 3

```text
contracts.jsonl
       ↓
chunk_contracts.py
       ↓
chunks
       ↓
inherit document metadata
       ↓
add chunk metadata
       ↓
chunks.jsonl
```

Thực tế bạn có thể để chunker tạo metadata ngay từ đầu, không nhất thiết phải có một script thứ hai.

---

# 33. Validation nên làm

Kiểm tra ngẫu nhiên khoảng 20 records:

```text
contract_id đúng?
chunk_id unique?
chunk_index liên tục?
contract_type đúng folder?
dataset_part đúng folder?
section đúng text?
token_count đúng?
source_txt tồn tại?
source_pdf tồn tại?
```

---

# 34. Checklist bước 3

- [ ] Chốt schema metadata V1
- [ ] Có `contract_id`
- [ ] Có `chunk_id`
- [ ] Có `chunk_index`
- [ ] Có `contract_type`
- [ ] Có `dataset_part`
- [ ] Có `section` nếu detect được
- [ ] Có `section_number` nếu detect được
- [ ] Có `token_count`
- [ ] Có `source_txt`
- [ ] Có `source_pdf`
- [ ] Không dùng CUAD ground truth để leak đáp án
- [ ] Kiểm tra source path
- [ ] Kiểm tra ID unique
- [ ] Manual inspect 20 records

---

# 35. Tư duy quan trọng nhất

Metadata không phải thứ trang trí.

Nó là cơ chế giúp retrieval:

```text
search đúng phạm vi
+
trace đúng nguồn
+
debug được kết quả
```

Một hệ thống RAG chỉ có embedding mà metadata nghèo sẽ rất khó mở rộng khi dataset lớn lên.

---

# 36. Input và Output của bước 3

## Input

```text
contracts.jsonl
chunks
folder structure
section structure
```

## Processing

```text
inherit document metadata
detect structural metadata
assign IDs
validate source
```

## Output

```text
chunks.jsonl
```

với schema sẵn sàng cho Embedding.

---

# 37. Trạng thái pipeline sau bước 3

Sau khi hoàn thành ba bước đầu, bạn có:

```text
RAW CONTRACTS
      ↓
1. Understand / Normalize
      ↓
contracts.jsonl
      ↓
2. Chunk
      ↓
3. Metadata
      ↓
chunks.jsonl
```

Lúc này bạn đã có một tập chunk:

- sạch;
- traceable;
- có cấu trúc;
- có metadata;
- sẵn sàng để biến thành vector.

Bước tiếp theo mới là:

```text
4. Embedding
```

Tại đó text:

```text
Either party may terminate this Agreement...
```

sẽ được chuyển thành vector:

```text
[0.023, -0.182, 0.741, ...]
```

để hệ thống bắt đầu semantic search.
