

# MedStock Pharmacy — AI Development Log

This file records the AI-assisted development process used to build the MedStock Pharmacy full-stack assessment project.

---

## 1. Initial Project Request

User requested a complete full-stack pharmacy inventory application named **MedStock Pharmacy**.

The application needed to satisfy the following assessment requirements:

* Full-stack working product.
* Python frontend/backend.
* Python web framework and database.
* Sensible database schema.
* REST APIs.
* API/list endpoint documentation in README.
* Usable UI consuming the APIs.
* User registration and login.
* Search.
* Pagination.
* Sorting.
* One-page landing page containing:

  * What the product is.
  * Key features.
  * Target audience.
  * How it helps.
  * Three possible next features.

The project also needed:

* `README.md`
* `REASONING.md`
* `AI_LOGS.md`

The GitHub repository was expected to be public.

---

## 2. Pharmacy Inventory Problem

The core business problem was defined as follows:

A neighborhood pharmacy stores medicine in multiple batches. Every batch has an expiry date.

When medicine is dispensed, the application must:

1. Prefer the batch that expires soonest.
2. Never dispense expired stock.
3. Show only sellable/in-date stock.
4. Answer questions such as:

   * "Do we have paracetamol in date?"
5. Provide a heads-up when batches are approaching expiry.

This resulted in the implementation of **FEFO — First Expiry, First Out**.

---

## 3. Automation Requirement — Twist Level 1 / T2

The project needed a daily automation workflow.

The automation should:

* Identify batches expiring within 7 days.
* Flag those batches.
* Quarantine expired batches.
* Report the number of affected batches.

For deterministic assessment/testing, the application exposes:

`POST /clock`

The `/clock` endpoint triggers the daily inventory automation.

---

## 4. Messy Data Requirement — Twist Level 2 / T4

The application also needed to support messy imported inventory data.

The import data could contain:

* Null values.
* Quantities such as `"10 units"`.
* Dates in different formats.
* `dd/mm/yyyy` dates.
* ISO dates.
* Duplicate rows.

The import process needed to produce a result containing:

```text
{
  imported,
  deduped,
  rejected
}
```

The import process was designed to:

1. Parse valid values.
2. Normalize quantities.
3. Normalize supported date formats.
4. Detect duplicate rows.
5. Reject invalid rows.
6. Create valid batches.

A sample CSV file was included in the repository.

---

## 5. Notification Requirement — Twist Level 3 / T1

The application also needed an integration workflow.

When a medicine's in-date sellable stock falls below its configured reorder threshold, the application should create a reorder notification.

Instead of depending on an external email/SMS provider during assessment execution, an **outbox pattern** was implemented.

Notifications are stored in the database and exposed through:

`GET /outbox`

The notification can then be marked delivered through:

`POST /outbox/{message_id}/deliver`

This makes the integration deterministic and easy to demonstrate.

---

## 6. Technology Selection

The application was designed using:

* Python
* FastAPI
* SQLAlchemy
* SQLite
* Pydantic
* JWT authentication
* Argon2 password hashing
* Vanilla HTML
* CSS
* JavaScript
* Pytest

The dependency list was stored in:

`requirements.txt`

---

## 7. Project Structure

The project structure was designed as:

```text
medstock-pharmacy/
├── README.md
├── REASONING.md
├── AI_LOGS.md
├── requirements.txt
├── .gitignore
├── sample_import.csv
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── security.py
│   ├── deps.py
│   └── static/
│       ├── index.html
│       ├── styles.css
│       └── app.js
└── tests/
    ├── __init__.py
    └── test_app.py
```

---

## 8. Database Design

The database was designed around the pharmacy workflow.

The main tables are:

### Users

Stores registered application users.

Important fields:

* `id`
* `email`
* `password_hash`
* `created_at`

### Medicines

Stores medicine-level information.

Important fields:

* `id`
* `name`
* `sku`
* `reorder_threshold`
* `created_at`

### Batches

Stores batch-level inventory.

Important fields:

* `id`
* `medicine_id`
* `batch_no`
* `quantity`
* `expiry_date`
* `status`
* `created_at`

A unique constraint was added for:

```text
medicine_id + batch_no
```

This prevents the same medicine batch from being inserted multiple times.

An index was also added to support FEFO ordering:

```text
medicine_id + expiry_date + id
```

### Expiry Alerts

Stores expiry warnings.

Important fields:

* `id`
* `batch_id`
* `message`
* `status`
* `created_at`

### Outbox Messages

Stores integration notifications.

Important fields:

* `id`
* `event_type`
* `recipient`
* `subject`
* `message`
* `status`
* `created_at`

---

## 9. FEFO Implementation

The inventory logic uses:

**First Expiry, First Out.**

When dispensing medicine, the application finds sellable batches ordered by:

```text
expiry_date ASC
```

The soonest-expiring valid batch is consumed first.

If the requested quantity is larger than the first batch's available quantity, the remaining quantity is taken from the next valid batch.

Expired batches are excluded from dispensing.

This directly models the pharmacy requirement.

---

## 10. Sellable Stock

A batch is considered sellable only when:

* Its quantity is greater than zero.
* Its status is active.
* Its expiry date has not passed.

Therefore expired stock is not included in the sellable stock total.

This prevents expired inventory from appearing as available stock.

---

## 11. Authentication

The application implements:

* Registration.
* Login.
* JWT access tokens.
* Password hashing.

Passwords are never stored as plain text.

The authenticated API uses:

```text
Authorization: Bearer <token>
```

Protected endpoints require a valid authenticated user.

---

## 12. API Design

The application exposes REST-style endpoints for:

### Authentication

```text
POST /auth/register
POST /auth/login
GET  /auth/me
```

### Medicines

```text
POST /medicines
GET  /medicines
GET  /medicines/{medicine_id}
GET  /medicines/{medicine_id}/stock
POST /medicines/{medicine_id}/dispense
```

### Batches

```text
POST /batches
GET  /batches
```

### Automation

```text
POST /clock
GET  /alerts
```

### Integration

```text
GET  /outbox
POST /outbox/{message_id}/deliver
```

### Import

```text
POST /import
```

### Health

```text
GET /health
```

FastAPI automatically provides interactive API documentation through:

```text
/docs
```

---

## 13. Search, Sorting and Pagination

The medicine listing API supports:

* Search.
* Sorting.
* Pagination.

This allows the UI to handle a growing medicine catalogue rather than loading everything into the browser at once.

The response contains:

```text
items
page
page_size
total
total_pages
```

---

## 14. Frontend

A responsive frontend was created using:

* HTML
* CSS
* JavaScript

No frontend framework was required.

The frontend contains:

* Landing page.
* Hero section.
* Product explanation.
* Feature cards.
* Target audience section.
* Authentication UI.
* Inventory dashboard.
* Search.
* Sorting.
* Pagination.
* Medicine creation.
* Batch creation.
* Stock view.
* FEFO dispensing.
* Daily automation trigger.
* Expiry alerts.
* Notification outbox.
* CSV import.
* Workflow explanation.
* Future features.

The JavaScript communicates with the FastAPI backend using REST APIs.

---

## 15. Landing Page

The landing page was designed to clearly explain:

### What it is

MedStock Pharmacy is an inventory management system designed for neighborhood pharmacies.

### Key features

* FEFO dispensing.
* Expiry protection.
* Sellable stock tracking.
* Automated expiry checks.
* Reorder notifications.
* Messy CSV import.

### Target audience

The product is intended for:

* Neighborhood pharmacies.
* Pharmacy staff.
* Inventory managers.
* Small healthcare retailers.

### How it helps

The system helps pharmacy staff:

* Know what stock is sellable.
* Avoid dispensing expired medicines.
* Use soonest-expiring stock first.
* Detect approaching expiry.
* Identify medicines that need reordering.
* Import imperfect inventory data.

### Three future features

The landing page also describes three possible future improvements.

---

## 16. Expiry Automation

The `/clock` endpoint was implemented to make the daily automation testable.

The automation checks all active batches.

For batches that are already expired:

```text
status -> quarantined
```

For batches approaching expiry within the configured 7-day window:

* An expiry alert is generated.

The endpoint reports automation results.

This allows the assessment evaluator to trigger the workflow without waiting for an actual scheduled job.

---

## 17. Reorder Workflow

Each medicine has a:

```text
reorder_threshold
```

The application calculates current sellable stock.

If:

```text
sellable_stock < reorder_threshold
```

a reorder notification is added to the outbox.

The outbox acts as a reliable integration boundary.

The UI exposes the generated notification and provides a delivery action.

---

## 18. Messy CSV Import

A sample import file was added:

```text
sample_import.csv
```

The import workflow handles:

* Valid rows.
* Missing values.
* Quantity strings.
* Multiple date formats.
* Duplicate rows.
* Invalid rows.

The import result reports:

```text
imported
deduped
rejected
```

This makes the behavior measurable during assessment.

---

## 19. Testing

A Pytest test suite was created.

The tests cover:

### Health

```text
GET /health
```

### Authentication

Registration and login.

### Medicine creation

Creating a medicine through the authenticated API.

### Batch creation and stock

Creating a batch and checking sellable stock.

### FEFO

Creating multiple batches with different expiry dates and verifying that dispensing consumes the earlier-expiring batch first.

The test command is:

```bash
pytest
```

---

## 20. Running the Application

On Windows Command Prompt:

### Create virtual environment

```cmd
python -m venv .venv
```

### Activate it

```cmd
.venv\Scripts\activate
```

The prompt should then display:

```text
(.venv)
```

### Install dependencies

```cmd
pip install -r requirements.txt
```

### Run tests

```cmd
pytest
```

### Start the server

```cmd
uvicorn app.main:app --reload
```

The application is available at:

```text
http://127.0.0.1:8000
```

Swagger API documentation is available at:

```text
http://127.0.0.1:8000/docs
```

---

## 21. Assessment Demonstration Flow

The application can be demonstrated with the following workflow:

1. Open the landing page.
2. Register an account.
3. Log in.
4. Create a medicine.
5. Add multiple batches.
6. View sellable stock.
7. Dispense medicine.
8. Verify FEFO behavior.
9. Create/import inventory data.
10. Run `/clock`.
11. Review expiry alerts.
12. Review reorder notifications.
13. Mark an outbox notification as delivered.
14. Use Swagger to demonstrate the REST APIs.

---

## 22. Design Decisions

The implementation intentionally keeps the application relatively simple.

SQLite was selected because:

* It requires no separate database server.
* It is easy to run locally.
* It is suitable for an assessment project.
* SQLAlchemy keeps the application database layer structured.

FastAPI was selected because:

* It provides REST API support.
* It provides automatic OpenAPI documentation.
* Pydantic validation is integrated.
* It works well with Python.

Vanilla JavaScript was selected for the frontend because:

* No frontend build system is required.
* The project is easy to run.
* The API integration remains visible and understandable.

---

## 23. Security Considerations

The application includes:

* Password hashing.
* JWT authentication.
* Protected inventory endpoints.
* Input validation.
* Database uniqueness constraints.

The application is intended for assessment/local demonstration.

Before production deployment, additional security hardening would be required, including:

* Secure secret management.
* HTTPS.
* Production database configuration.
* More granular authorization.
* Rate limiting.
* Audit logging.
* Stronger email validation.
* Production-grade secret rotation.

---

## 24. AI-Assisted Development

AI assistance was used to:

* Plan the architecture.
* Design the database schema.
* Create API schemas.
* Implement authentication.
* Implement FEFO logic.
* Implement expiry automation.
* Implement messy CSV import.
* Implement the outbox notification pattern.
* Create frontend HTML/CSS/JavaScript.
* Create automated tests.
* Create README and reasoning documentation.
* Review the project structure and identify potential issues.

The final application should be reviewed and tested by the developer before submission.

---

## 25. Final Verification Checklist

Before submitting the repository, verify:

```text
[ ] README.md exists
[ ] REASONING.md exists
[ ] AI_LOGS.md exists
[ ] requirements.txt exists
[ ] .gitignore exists
[ ] sample_import.csv exists
[ ] app/ package exists
[ ] frontend files exist
[ ] tests exist
[ ] pytest passes
[ ] application starts successfully
[ ] registration works
[ ] login works
[ ] medicine creation works
[ ] batch creation works
[ ] stock calculation works
[ ] FEFO dispensing works
[ ] expired stock is excluded
[ ] /clock works
[ ] expiry alerts work
[ ] CSV import works
[ ] duplicate handling works
[ ] reorder notification works
[ ] /outbox works
[ ] Swagger documentation works
[ ] landing page contains required assessment content
```

---


