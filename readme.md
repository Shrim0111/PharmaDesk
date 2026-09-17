````markdown
# MedStock Pharmacy

A full-stack pharmacy inventory management system built with Python, FastAPI, SQLAlchemy, SQLite, and a vanilla HTML/CSS/JavaScript frontend.

MedStock Pharmacy helps a neighborhood pharmacy track medicine batches, expiry dates, sellable stock, FEFO dispensing, expiry alerts, messy data imports, and automatic reorder notifications.

---

## 1. Problem Statement

A neighborhood pharmacy may have the same medicine in multiple batches with different expiry dates.

The system must:

- Track medicines and their batches.
- Track quantity for every batch.
- Never sell expired medicine.
- Always dispense the batch that expires soonest first.
- Show the currently sellable stock.
- Answer whether a medicine is available and in date.
- Warn staff about batches that are close to expiry.
- Automatically quarantine expired batches.
- Import messy batch data safely.
- Generate reorder notifications when sellable stock falls below a configured threshold.

---

## 2. Key Features

### Authentication

- User registration.
- User login.
- JWT-based authentication.
- Protected inventory endpoints.

### Medicine Management

- Create medicines.
- Search medicines.
- Paginate medicine results.
- Sort medicine results.
- View individual medicine details.
- Configure reorder thresholds.

### Batch Management

- Add medicine batches.
- Track batch number.
- Track quantity.
- Track expiry date.
- Track batch status.

### FEFO Dispensing

FEFO means:

> First Expire, First Out.

When medicine is dispensed, the system selects the earliest-expiring sellable batch first.

Expired batches are never included in sellable stock.

### Expiry Automation

`POST /clock` simulates a daily pharmacy clock job.

It:

1. Quarantines expired batches.
2. Creates alerts for batches expiring within 7 days.
3. Checks sellable stock against reorder thresholds.
4. Creates reorder notifications in the outbox.

### Messy Data Import

The batch importer handles:

- Missing values.
- Invalid values.
- Quantities such as `10 units`.
- ISO dates such as `2026-12-31`.
- Dates such as `31/12/2026`.
- Duplicate rows.
- Unknown SKUs.

The import response reports:

```json
{
  "imported": 5,
  "deduped": 2,
  "rejected": 1
}
````

### Notification Outbox

Reorder notifications are stored in an outbox before delivery.

This demonstrates a simple reliable integration pattern between the inventory system and a notification service.

---

# 3. Technology Stack

| Component         | Technology                |
| ----------------- | ------------------------- |
| Backend           | Python + FastAPI          |
| Database          | SQLite                    |
| ORM               | SQLAlchemy                |
| Validation        | Pydantic                  |
| Authentication    | JWT                       |
| Password Hashing  | Argon2 via pwdlib         |
| Frontend          | HTML + CSS + JavaScript   |
| Testing           | Pytest                    |
| API Documentation | FastAPI OpenAPI / Swagger |

---

# 4. Project Structure

```text
medstock-pharmacy/
│
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── security.py
│   ├── deps.py
│   │
│   └── static/
│       ├── index.html
│       ├── styles.css
│       └── app.js
│
├── tests/
│   ├── __init__.py
│   └── test_app.py
│
├── README.md
├── REASONING.md
├── AI_LOGS.md
├── requirements.txt
├── .gitignore
└── sample_import.csv
```

---

# 5. Database Schema

## Users

Stores application users.

Fields:

* `id`
* `email`
* `password_hash`
* `created_at`

---

## Medicines

Stores medicine-level information.

Fields:

* `id`
* `name`
* `sku`
* `reorder_threshold`
* `created_at`

Each medicine has one or more batches.

---

## Batches

Stores individual medicine batches.

Fields:

* `id`
* `medicine_id`
* `batch_no`
* `quantity`
* `expiry_date`
* `status`
* `created_at`

A unique constraint prevents the same batch number from being duplicated for the same medicine.

---

## Expiry Alerts

Stores expiry warnings.

Fields:

* `id`
* `batch_id`
* `message`
* `status`
* `created_at`

---

## Outbox Messages

Stores notifications waiting to be delivered.

Fields:

* `id`
* `event_type`
* `recipient`
* `subject`
* `message`
* `status`
* `created_at`

---

# 6. FEFO Logic

The system uses the following rule:

```text
Medicine
   |
   v
Find active batches
   |
   v
Remove expired batches
   |
   v
Sort by earliest expiry date
   |
   v
Dispense from earliest-expiring batch
   |
   v
Continue until requested quantity is fulfilled
```

Example:

```text
Paracetamol

Batch A -> 100 units -> expires 2026-10-01
Batch B -> 100 units -> expires 2026-12-01
Batch C -> 100 units -> expires 2027-02-01
```

If the pharmacy dispenses 120 units:

```text
Batch A -> 100 units
Batch B -> 20 units
Batch C -> 0 units
```

The system does not dispense from Batch B until Batch A has been exhausted.

---

# 7. Sellable Stock

A batch is considered sellable only when:

```text
status = active
AND
quantity > 0
AND
expiry_date > today
```

Therefore expired inventory is excluded from the sellable stock calculation.

---

# 8. API Documentation

When the application is running, FastAPI automatically provides:

```text
GET /docs
```

Swagger UI can be used to test the APIs interactively.

FastAPI also provides:

```text
GET /openapi.json
```

for the OpenAPI specification.

---

# 9. API Endpoints

## Health

### `GET /health`

Checks whether the application is running.

Example response:

```json
{
  "status": "ok"
}
```

---

# Authentication

## Register

### `POST /auth/register`

Creates a new user.

Request:

```json
{
  "email": "pharmacist@example.com",
  "password": "password123"
}
```

---

## Login

### `POST /auth/login`

Logs the user in and returns a JWT access token.

The endpoint accepts form data:

```text
username=pharmacist@example.com
password=password123
```

Response:

```json
{
  "access_token": "JWT_TOKEN",
  "token_type": "bearer"
}
```

Use the returned token in protected API requests:

```text
Authorization: Bearer JWT_TOKEN
```

---

## Current User

### `GET /auth/me`

Returns information about the currently authenticated user.

Requires authentication.

---

# Medicines

## Create Medicine

### `POST /medicines`

Requires authentication.

Request:

```json
{
  "name": "Paracetamol",
  "sku": "PARA-500",
  "reorder_threshold": 20
}
```

---

## List Medicines

### `GET /medicines`

Supports:

* Search.
* Pagination.
* Sorting.

Example:

```text
GET /medicines?search=para&page=1&page_size=10&sort_by=name&sort_order=asc
```

Parameters:

| Parameter    | Description                                 |
| ------------ | ------------------------------------------- |
| `search`     | Searches medicine name and SKU              |
| `page`       | Page number                                 |
| `page_size`  | Number of results per page                  |
| `sort_by`    | `name`, `sku`, `reorder_threshold`, or `id` |
| `sort_order` | `asc` or `desc`                             |

Example response:

```json
{
  "items": [],
  "page": 1,
  "page_size": 10,
  "total": 0,
  "total_pages": 0
}
```

---

## Get Medicine

### `GET /medicines/{medicine_id}`

Returns one medicine.

---

# Batches

## Create Batch

### `POST /batches`

Requires authentication.

Request:

```json
{
  "medicine_id": 1,
  "batch_no": "PCM001",
  "quantity": 100,
  "expiry_date": "2026-12-31"
}
```

---

## List Batches

### `GET /batches`

Returns batches and supports medicine filtering.

---

# Stock

## Get Sellable Stock

### `GET /medicines/{medicine_id}/stock`

Returns the medicine's currently sellable batches and total sellable quantity.

Expired batches are excluded.

This endpoint can be used to answer:

```text
Do we have paracetamol in date?
```

---

# Dispensing

## Dispense Medicine

### `POST /medicines/{medicine_id}/dispense`

Requires authentication.

Request:

```json
{
  "quantity": 30
}
```

The system automatically applies FEFO.

If the requested quantity cannot be fulfilled using sellable stock, the operation fails without partially dispensing the requested amount.

---

# Daily Automation

## Run Pharmacy Clock

### `POST /clock`

Simulates the daily scheduled pharmacy job.

The job:

1. Quarantines expired batches.
2. Creates expiry alerts for batches expiring within 7 days.
3. Checks reorder thresholds.
4. Creates reorder notifications in the outbox.

This endpoint is intentionally exposed so the automation can be graded without waiting for a real scheduled task.

---

# Alerts

## Get Alerts

### `GET /alerts`

Returns expiry alerts generated by the system.

---

# Notification Outbox

## Get Outbox

### `GET /outbox`

Returns notification messages generated by the reorder automation.

---

## Deliver Outbox Message

### `POST /outbox/{message_id}/deliver`

Marks an outbox notification as delivered.

This represents the handoff to an external Notification Service.

---

# Import

## Get Import Template

### `GET /import/template`

Returns the expected CSV structure.

Required columns:

```text
sku,batch_no,quantity,expiry_date
```

---

## Import Batches

### `POST /import/batches`

Uploads a CSV containing batch information.

Example:

```csv
sku,batch_no,quantity,expiry_date
PARA-500,PARA001,100,31/12/2026
PARA-500,PARA002,10 units,2027-01-15
```

The importer normalizes the data and reports:

```json
{
  "imported": 2,
  "deduped": 0,
  "rejected": 0
}
```

Invalid records are rejected rather than inserted into the database.

---

# 10. Running the Application

## Step 1: Create a virtual environment

Windows:

```bash
python -m venv .venv
```

Activate it:

```bash
.venv\Scripts\activate
```

---

## Step 2: Install dependencies

```bash
pip install -r requirements.txt
```

---

## Step 3: Start the server

From the project root:

```bash
uvicorn app.main:app --reload
```

The application will be available at:

```text
http://127.0.0.1:8000
```

---

# 11. Using the Frontend

Open:

```text
http://127.0.0.1:8000
```

The frontend provides:

* Login and registration.
* Medicine search.
* Pagination.
* Sorting.
* Medicine creation.
* Batch creation.
* Sellable stock display.
* Dispensing.
* Expiry alerts.
* Clock automation.
* Import tools.
* Notification outbox.

---

# 12. Running Tests

From the project root:

```bash
pytest
```

The tests cover important application behavior including:

* Health endpoint.
* Registration.
* Login.
* Medicine creation.
* Batch creation.
* Sellable stock.
* FEFO dispensing.

---

# 13. Assessment Scenarios

## Scenario 1: FEFO

Create two batches:

```text
Batch A -> expires sooner
Batch B -> expires later
```

Dispense medicine.

The system should use Batch A first.

---

## Scenario 2: Expired Stock

Create a batch with an expiry date in the past.

The batch must not be counted as sellable stock.

Running:

```text
POST /clock
```

should quarantine the expired batch.

---

## Scenario 3: Expiring Soon

Create a batch that expires within 7 days.

Run:

```text
POST /clock
```

The system should generate an expiry alert.

---

## Scenario 4: Reorder Notification

Set:

```text
reorder_threshold = 20
```

If sellable stock falls below 20, running:

```text
POST /clock
```

creates a reorder notification in:

```text
GET /outbox
```

---

## Scenario 5: Messy Import

Upload a CSV containing:

```text
10 units
31/12/2026
2026-12-31
blank quantity
duplicate rows
unknown SKU
```

The importer should normalize valid records, deduplicate duplicates, and reject invalid records.

---

# 14. Landing Page

The landing page explains:

### What it is

A pharmacy inventory system focused on medicine batch and expiry management.

### Target audience

Neighborhood pharmacies and pharmacy staff managing medicines with multiple batches and expiry dates.

### How it helps

It reduces expiry-related inventory mistakes by tracking batch-level stock, enforcing FEFO dispensing, identifying expiring medicines, and generating reorder notifications.

### Next Features

Three possible future features are:

1. Barcode scanning for faster medicine and batch lookup.
2. Supplier management and purchase-order generation.
3. Sales analytics and inventory forecasting.

---

# 15. Security Notes

This project is designed as an assessment/demo application.

Before production deployment:

* Move the JWT secret into an environment variable.
* Use HTTPS.
* Add stronger email validation.
* Add rate limiting.
* Add refresh tokens if required.
* Use a production database.
* Add audit logging.
* Configure proper CORS origins.
* Use secure production password policies.
* Add role-based access control.

---

# 16. License

This project is created for educational and assessment purposes.

```
```
