````markdown
# REASONING.md

## MedStock Pharmacy — Design Reasoning

### 1. Problem Understanding

The core problem is pharmacy inventory management at the batch level.

A medicine can exist in multiple batches, and each batch can have a different:

- Quantity
- Expiry date
- Batch number
- Status

The system therefore cannot safely track inventory only at the medicine level.

The design stores inventory as individual batches linked to a medicine.

---

## 2. Why Batch-Level Inventory?

Consider:

```text
Paracetamol
├── Batch A → 100 units → expires 2026-10-01
├── Batch B → 100 units → expires 2026-12-01
└── Batch C → 100 units → expires 2027-02-01
````

A single total such as:

```text
Paracetamol = 300 units
```

does not tell the pharmacy which units should be dispensed first.

Therefore the database stores every batch separately.

---

## 3. FEFO Decision

The pharmacy requires:

> First Expire, First Out.

The dispensing algorithm:

1. Finds batches belonging to the requested medicine.
2. Keeps only active batches.
3. Excludes expired batches.
4. Excludes batches with zero quantity.
5. Sorts the remaining batches by expiry date.
6. Dispenses from the earliest-expiring batch first.
7. Continues to the next batch when required.

Conceptually:

```text
Active batches
      ↓
Quantity > 0
      ↓
Expiry date > today
      ↓
ORDER BY expiry_date ASC
      ↓
Dispense
```

This prevents later-expiring inventory from being consumed while an earlier-expiring batch remains available.

---

## 4. Preventing Expired Sales

Expired medicine must never be considered sellable.

The sellable-stock rule is:

```text
status = active
AND quantity > 0
AND expiry_date > today
```

This rule is applied when calculating stock and when dispensing.

There is also a `/clock` endpoint that quarantines expired active batches.

Using both approaches provides two layers of protection:

1. Expired batches are excluded immediately from selling logic.
2. The daily automation changes their status to `quarantined`.

---

## 5. Why Use a Clock Endpoint?

A real pharmacy system would normally run a scheduled daily job.

For an assessment environment, waiting for an actual scheduled job makes the behavior difficult to demonstrate and test.

Therefore:

```text
POST /clock
```

simulates the daily job.

It allows the evaluator to trigger automation deterministically.

The endpoint performs:

```text
Expired batch detection
        ↓
Quarantine expired batches
        ↓
Generate expiry alerts
        ↓
Check reorder thresholds
        ↓
Create notification outbox messages
```

---

## 6. Expiry Alerts

A batch that is close to expiry should receive an alert before it becomes unusable.

The implementation uses a 7-day warning window.

For example:

```text
Today:       2026-09-01
Expiry:      2026-09-05
```

The batch is still sellable but should generate an expiry warning.

This allows pharmacy staff to take action before the stock becomes expired.

---

## 7. Reorder Threshold

Each medicine has a configurable:

```text
reorder_threshold
```

The threshold is compared against sellable stock rather than raw database quantity.

This distinction is important.

For example:

```text
Total stored quantity = 50

Expired quantity = 40

Sellable quantity = 10

Reorder threshold = 20
```

The system should consider the medicine below its reorder threshold because only 10 units are actually sellable.

Therefore:

```text
sellable_stock < reorder_threshold
```

triggers the reorder notification.

---

## 8. Outbox Pattern

The system does not directly depend on an external notification provider.

Instead, it creates an outbox message:

```text
Inventory System
      ↓
Outbox Message
      ↓
Notification Service
```

The outbox stores:

* Event type
* Recipient
* Subject
* Message
* Status
* Creation time

Initially the message has:

```text
status = pending
```

When delivered through:

```text
POST /outbox/{message_id}/deliver
```

the status changes to:

```text
delivered
```

This provides a simple integration boundary and makes the notification behavior easy to inspect during assessment.

---

## 9. Messy Data Import

Real-world inventory files are often inconsistent.

The importer therefore accepts common variations.

### Quantity

These can represent the same quantity:

```text
10
10 units
```

The importer extracts the numeric quantity.

### Dates

The importer accepts:

```text
2026-12-31
31/12/2026
```

The first uses ISO format and the second uses day/month/year format.

### Invalid Records

Records are rejected when required information is missing or invalid.

Examples:

```text
Missing SKU
Missing batch number
Invalid quantity
Invalid expiry date
Unknown SKU
```

Rejected records are not inserted.

---

## 10. Duplicate Import Rows

Duplicate records should not create duplicate inventory.

The importer identifies duplicate rows using the medicine and batch identity.

The database also has a unique constraint:

```text
medicine_id + batch_no
```

This provides database-level protection in addition to importer-level deduplication.

The import result reports:

```json
{
  "imported": 5,
  "deduped": 2,
  "rejected": 1
}
```

This gives the pharmacy operator visibility into what happened during the import.

---

## 11. Database Choice

SQLite was selected because:

* It requires no separate database server.
* It is easy to run locally.
* It works well for an assessment project.
* SQLAlchemy keeps the database layer structured.
* The schema can later be migrated to PostgreSQL or another relational database.

The application uses SQLAlchemy ORM rather than writing raw SQL throughout the application.

---

## 12. API Design

FastAPI was selected because it provides:

* REST API support.
* Automatic OpenAPI documentation.
* Request validation through Pydantic.
* Easy dependency injection.
* Straightforward authentication integration.
* Good testing support.

The API is separated conceptually into:

```text
/auth
/medicines
/batches
/clock
/alerts
/outbox
/import
```

This keeps the domain responsibilities understandable.

---

## 13. Pagination

Medicine listing supports pagination because an inventory database can contain many medicines.

The endpoint accepts:

```text
page
page_size
```

and returns:

```json
{
  "items": [],
  "page": 1,
  "page_size": 10,
  "total": 100,
  "total_pages": 10
}
```

This prevents the frontend from having to load every medicine record at once.

---

## 14. Search and Sorting

Medicine search supports matching against:

* Medicine name
* SKU

Sorting supports fields such as:

* Name
* SKU
* Reorder threshold
* ID

The API also accepts ascending or descending order.

This gives pharmacy staff practical ways to locate inventory quickly.

---

## 15. Authentication

JWT authentication is used for protected operations.

The flow is:

```text
Register
   ↓
Password hashed
   ↓
Login
   ↓
JWT token issued
   ↓
Token sent with API requests
   ↓
Current user identified
```

Passwords are never stored directly.

The database stores a password hash instead.

---

## 16. Frontend Approach

The frontend uses plain:

* HTML
* CSS
* JavaScript

A framework was intentionally avoided because the assessment focuses on a working full-stack product rather than frontend framework complexity.

The JavaScript communicates with the FastAPI REST API.

The frontend provides a usable interface for:

* Authentication
* Medicine management
* Batch management
* Stock lookup
* Dispensing
* Alerts
* Automation
* Importing data
* Viewing notification messages

---

## 17. Data Integrity

Several safeguards are used.

### Medicine SKU

Medicine SKU is unique.

### Medicine + Batch

The combination of:

```text
medicine_id
batch_no
```

is unique.

### Quantities

Batch quantities must be positive when creating a batch.

### Dispensing

The system checks available sellable stock before performing a dispense operation.

This avoids partially completing a request that cannot be fulfilled.

---

## 18. Important Trade-offs

### SQLite vs PostgreSQL

SQLite is simpler for the assessment and local execution.

For a larger production pharmacy deployment, PostgreSQL would be more appropriate.

### Vanilla JavaScript vs React

Vanilla JavaScript keeps setup small and avoids unnecessary build tooling.

A larger production frontend could use React, Vue, or another framework.

### `/clock` vs Real Scheduler

A real scheduler would be appropriate in production.

The `/clock` endpoint makes the same logic deterministic and easy to grade.

### Outbox vs Direct Notification

The outbox adds an extra step, but it makes the integration boundary visible and allows pending notifications to be inspected and retried.

---

## 19. Future Improvements

The landing page identifies three possible next features:

1. Barcode scanning.
2. Supplier and purchase-order management.
3. Sales analytics and inventory forecasting.

Additional production improvements could include:

* Role-based permissions.
* Audit logs.
* PostgreSQL.
* Background workers.
* Real notification providers.
* Automated database backups.
* Barcode hardware integration.
* Pharmacy-specific compliance controls.

---

## 20. Summary

The architecture prioritizes the core pharmacy workflow:

```text
Medicine
   ↓
Multiple batches
   ↓
Expiry-aware sellable stock
   ↓
FEFO dispensing
   ↓
Expiry automation
   ↓
Reorder detection
   ↓
Notification outbox
```

The main design principle is that **inventory availability must be based on sellable, in-date batch stock rather than simply the total quantity stored in the database**.

```
```
