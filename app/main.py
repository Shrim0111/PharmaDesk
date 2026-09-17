
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional
import csv
import io
import re

from fastapi import (
    Depends,
    FastAPI,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func
from sqlalchemy.orm import Session

from .database import Base, SessionLocal, engine
from .deps import get_current_user
from .models import Batch, ExpiryAlert, Medicine, OutboxMessage, User
from .schemas import (
    BatchCreate,
    BatchResponse,
    DispenseRequest,
    MedicineCreate,
    MedicineResponse,
    PaginatedMedicineResponse,
    Token,
    UserCreate,
    UserResponse,
)
from .security import (
    create_access_token,
    hash_password,
    verify_password,
)


# ============================================================
# Application setup
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="MedStock Pharmacy API",
    description=(
        "Pharmacy inventory management system with FEFO dispensing, "
        "expiry automation, messy CSV import, and reorder notifications."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

if STATIC_DIR.exists():
    app.mount(
        "/static",
        StaticFiles(directory=str(STATIC_DIR)),
        name="static",
    )


# ============================================================
# Database dependency
# ============================================================

def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


# ============================================================
# Utility helpers
# ============================================================

def today() -> date:
    return date.today()


def parse_date(value: str) -> date:
    """
    Accept:
    - YYYY-MM-DD
    - DD/MM/YYYY
    """

    if value is None:
        raise ValueError("Expiry date is required.")

    value = str(value).strip()

    if not value:
        raise ValueError("Expiry date is required.")

    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue

    raise ValueError(f"Invalid date: {value}")


def parse_quantity(value) -> int:
    """
    Accept values such as:
    - 10
    - "10"
    - "10 units"
    - "10 Units"
    """

    if value is None:
        raise ValueError("Quantity is required.")

    if isinstance(value, int):
        quantity = value
    else:
        text = str(value).strip()

        if not text:
            raise ValueError("Quantity is required.")

        match = re.search(r"\d+", text)

        if not match:
            raise ValueError(f"Invalid quantity: {value}")

        quantity = int(match.group())

    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero.")

    return quantity


def medicine_to_dict(medicine: Medicine) -> dict:
    return {
        "id": medicine.id,
        "name": medicine.name,
        "sku": medicine.sku,
        "reorder_threshold": medicine.reorder_threshold,
    }


def calculate_sellable_stock(
    db: Session,
    medicine_id: int,
) -> int:
    """
    Sellable stock means:
    - batch is active
    - quantity > 0
    - expiry date is strictly after today

    Expired batches are never included.
    """

    total = (
        db.query(
            func.coalesce(
                func.sum(Batch.quantity),
                0,
            )
        )
        .filter(
            Batch.medicine_id == medicine_id,
            Batch.status == "active",
            Batch.quantity > 0,
            Batch.expiry_date > today(),
        )
        .scalar()
    )

    return int(total or 0)


def create_outbox_message(
    db: Session,
    medicine: Medicine,
    subject: str,
    message: str,
) -> OutboxMessage:
    """
    Creates a Notification Service-style outbox event.

    The actual external notification service can consume these
    pending messages later.
    """

    outbox = OutboxMessage(
        event_type="reorder_alert",
        recipient="pharmacy-manager",
        subject=subject,
        message=message,
        status="pending",
    )

    db.add(outbox)

    return outbox


# ============================================================
# Landing page
# ============================================================

@app.get("/", include_in_schema=False)
def serve_frontend():
    index_file = STATIC_DIR / "index.html"

    if not index_file.exists():
        raise HTTPException(
            status_code=404,
            detail="Frontend not found.",
        )

    return FileResponse(index_file)


# ============================================================
# Health
# ============================================================

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "MedStock Pharmacy",
        "date": today().isoformat(),
    }


# ============================================================
# Authentication
# ============================================================

@app.post(
    "/auth/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    user_data: UserCreate,
    db: Session = Depends(get_db),
):
    email = user_data.email.lower().strip()

    existing_user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email is already registered.",
        )

    user = User(
        email=email,
        password_hash=hash_password(user_data.password),
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


@app.post(
    "/auth/login",
    response_model=Token,
)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    email = form_data.username.lower().strip()

    user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if not user or not verify_password(
        form_data.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # IMPORTANT:
    # security.py expects a string subject.
    token = create_access_token(str(user.id))

    return {
        "access_token": token,
        "token_type": "bearer",
    }


@app.get(
    "/auth/me",
    response_model=UserResponse,
)
def get_me(
    current_user: User = Depends(get_current_user),
):
    return current_user


# ============================================================
# Medicines
# ============================================================

@app.post(
    "/medicines",
    response_model=MedicineResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_medicine(
    medicine_data: MedicineCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sku = medicine_data.sku.strip()

    existing = (
        db.query(Medicine)
        .filter(Medicine.sku == sku)
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Medicine SKU already exists.",
        )

    medicine = Medicine(
        name=medicine_data.name.strip(),
        sku=sku,
        reorder_threshold=medicine_data.reorder_threshold,
    )

    db.add(medicine)
    db.commit()
    db.refresh(medicine)

    return medicine


@app.get(
    "/medicines",
    response_model=PaginatedMedicineResponse,
)
def list_medicines(
    search: Optional[str] = Query(
        default=None,
        description="Search by medicine name or SKU.",
    ),
    page: int = Query(
        default=1,
        ge=1,
    ),
    page_size: int = Query(
        default=8,
        ge=1,
        le=100,
    ),
    sort_by: str = Query(
        default="name",
        pattern="^(name|sku|reorder_threshold|id)$",
    ),
    sort_order: str = Query(
        default="asc",
        pattern="^(asc|desc)$",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Medicine)

    if search and search.strip():
        search_value = f"%{search.strip()}%"

        query = query.filter(
            (Medicine.name.ilike(search_value))
            | (Medicine.sku.ilike(search_value))
        )

    sort_column = getattr(
        Medicine,
        sort_by,
    )

    if sort_order == "desc":
        query = query.order_by(
            sort_column.desc()
        )
    else:
        query = query.order_by(
            sort_column.asc()
        )

    total = query.count()

    medicines = (
        query
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    results = []

    for medicine in medicines:
        stock = calculate_sellable_stock(
            db,
            medicine.id,
        )

        nearest_batch = (
            db.query(Batch)
            .filter(
                Batch.medicine_id == medicine.id,
                Batch.status == "active",
                Batch.quantity > 0,
                Batch.expiry_date > today(),
            )
            .order_by(
                Batch.expiry_date.asc(),
                Batch.id.asc(),
            )
            .first()
        )

        results.append(
            {
                **medicine_to_dict(medicine),
                "sellable_stock": stock,
                "nearest_expiry": (
                    nearest_batch.expiry_date.isoformat()
                    if nearest_batch
                    else None
                ),
            }
        )

    total_pages = (
        (total + page_size - 1) // page_size
        if total
        else 0
    )

    return {
        "items": results,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@app.get(
    "/medicines/{medicine_id}",
    response_model=MedicineResponse,
)
def get_medicine(
    medicine_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    medicine = (
        db.query(Medicine)
        .filter(Medicine.id == medicine_id)
        .first()
    )

    if not medicine:
        raise HTTPException(
            status_code=404,
            detail="Medicine not found.",
        )

    return medicine


# ============================================================
# Batches
# ============================================================

@app.post(
    "/batches",
    response_model=BatchResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_batch(
    batch_data: BatchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    medicine = (
        db.query(Medicine)
        .filter(
            Medicine.id == batch_data.medicine_id
        )
        .first()
    )

    if not medicine:
        raise HTTPException(
            status_code=404,
            detail="Medicine not found.",
        )

    batch_no = batch_data.batch_no.strip()

    existing = (
        db.query(Batch)
        .filter(
            Batch.medicine_id == batch_data.medicine_id,
            Batch.batch_no == batch_no,
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Batch number already exists for this medicine.",
        )

    if batch_data.expiry_date <= today():
        raise HTTPException(
            status_code=400,
            detail="Cannot create a batch that is already expired.",
        )

    batch = Batch(
        medicine_id=batch_data.medicine_id,
        batch_no=batch_no,
        quantity=batch_data.quantity,
        expiry_date=batch_data.expiry_date,
        status="active",
    )

    db.add(batch)
    db.commit()
    db.refresh(batch)

    return batch


@app.get("/batches")
def list_batches(
    medicine_id: Optional[int] = None,
    include_expired: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Batch)

    if medicine_id is not None:
        query = query.filter(
            Batch.medicine_id == medicine_id
        )

    if not include_expired:
        query = query.filter(
            Batch.status == "active"
        )

    batches = (
        query
        .order_by(
            Batch.expiry_date.asc(),
            Batch.id.asc(),
        )
        .all()
    )

    return batches


# ============================================================
# Sellable stock
# ============================================================

@app.get("/medicines/{medicine_id}/stock")
def get_medicine_stock(
    medicine_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    medicine = (
        db.query(Medicine)
        .filter(Medicine.id == medicine_id)
        .first()
    )

    if not medicine:
        raise HTTPException(
            status_code=404,
            detail="Medicine not found.",
        )

    sellable_batches = (
        db.query(Batch)
        .filter(
            Batch.medicine_id == medicine_id,
            Batch.status == "active",
            Batch.quantity > 0,
            Batch.expiry_date > today(),
        )
        .order_by(
            Batch.expiry_date.asc(),
            Batch.id.asc(),
        )
        .all()
    )

    batches = [
        {
            "id": batch.id,
            "batch_no": batch.batch_no,
            "quantity": batch.quantity,
            "expiry_date": batch.expiry_date.isoformat(),
            "status": batch.status,
        }
        for batch in sellable_batches
    ]

    total = sum(
        batch["quantity"]
        for batch in batches
    )

    return {
        "medicine_id": medicine_id,
        "medicine_name": medicine.name,
        "sku": medicine.sku,
        "reorder_threshold": medicine.reorder_threshold,
        "sellable_stock": total,
        "total_sellable_stock": total,
        "batches": batches,
    }


# ============================================================
# FEFO dispensing
# ============================================================

@app.post("/medicines/{medicine_id}/dispense")
def dispense_medicine(
    medicine_id: int,
    request: DispenseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    quantity_requested = request.quantity

    if quantity_requested <= 0:
        raise HTTPException(
            status_code=400,
            detail="Dispense quantity must be greater than zero.",
        )

    medicine = (
        db.query(Medicine)
        .filter(Medicine.id == medicine_id)
        .first()
    )

    if not medicine:
        raise HTTPException(
            status_code=404,
            detail="Medicine not found.",
        )

    # FEFO:
    # Earliest valid expiry date first.
    #
    # Expired batches are deliberately excluded.
    batches = (
        db.query(Batch)
        .filter(
            Batch.medicine_id == medicine_id,
            Batch.status == "active",
            Batch.quantity > 0,
            Batch.expiry_date > today(),
        )
        .order_by(
            Batch.expiry_date.asc(),
            Batch.id.asc(),
        )
        .all()
    )

    available = sum(
        batch.quantity
        for batch in batches
    )

    # Important:
    # Check the complete quantity before making
    # any deductions, so partial dispensing cannot occur.
    if available < quantity_requested:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Insufficient sellable stock. "
                f"Requested {quantity_requested}, "
                f"available {available}."
            ),
        )

    remaining = quantity_requested
    deductions = []

    for batch in batches:
        if remaining <= 0:
            break

        deduction = min(
            batch.quantity,
            remaining,
        )

        batch.quantity -= deduction
        remaining -= deduction

        deductions.append(
            {
                "batch_id": batch.id,
                "batch_no": batch.batch_no,
                "quantity_dispensed": deduction,
                "expiry_date": batch.expiry_date.isoformat(),
            }
        )

        if batch.quantity == 0:
            batch.status = "depleted"

    db.commit()

    new_stock = calculate_sellable_stock(
        db,
        medicine_id,
    )

    return {
        "message": "Medicine dispensed successfully.",
        "medicine_id": medicine_id,
        "medicine_name": medicine.name,
        "quantity_dispensed": quantity_requested,
        "dispensed": quantity_requested,
        "new_sellable_stock": new_stock,
        "fefo_deductions": deductions,
    }


# ============================================================
# Daily automation / Clock
# ============================================================

@app.post("/clock")
def run_clock(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_date = today()

    # --------------------------------------------------------
    # 1. Quarantine expired batches
    # --------------------------------------------------------

    expired_batches = (
        db.query(Batch)
        .filter(
            Batch.status == "active",
            Batch.expiry_date <= current_date,
            Batch.quantity > 0,
        )
        .all()
    )

    expired_count = 0

    for batch in expired_batches:
        batch.status = "quarantined"
        expired_count += 1

    # --------------------------------------------------------
    # 2. Create expiry alerts for next 7 days
    # --------------------------------------------------------

    alert_end_date = (
        current_date + timedelta(days=7)
    )

    expiring_batches = (
        db.query(Batch)
        .filter(
            Batch.status == "active",
            Batch.quantity > 0,
            Batch.expiry_date > current_date,
            Batch.expiry_date <= alert_end_date,
        )
        .all()
    )

    alerts_created = 0

    for batch in expiring_batches:
        existing_alert = (
            db.query(ExpiryAlert)
            .filter(
                ExpiryAlert.batch_id == batch.id,
                ExpiryAlert.status == "open",
            )
            .first()
        )

        if existing_alert:
            continue

        medicine = db.get(
            Medicine,
            batch.medicine_id,
        )

        medicine_name = (
            medicine.name
            if medicine
            else "Unknown medicine"
        )

        alert = ExpiryAlert(
            batch_id=batch.id,
            message=(
                f"{medicine_name} batch {batch.batch_no} "
                f"is expiring on "
                f"{batch.expiry_date.isoformat()}. "
                f"Remaining quantity: {batch.quantity}."
            ),
            status="open",
        )

        db.add(alert)
        alerts_created += 1

    db.flush()

    # --------------------------------------------------------
    # 3. Reorder automation
    # --------------------------------------------------------

    medicines = db.query(Medicine).all()

    reorder_alerts_created = 0

    for medicine in medicines:
        sellable_stock = calculate_sellable_stock(
            db,
            medicine.id,
        )

        if sellable_stock >= medicine.reorder_threshold:
            continue

        subject = (
            f"Reorder required: {medicine.name}"
        )

        existing_reorder = (
            db.query(OutboxMessage)
            .filter(
                OutboxMessage.event_type == "reorder_alert",
                OutboxMessage.status == "pending",
                OutboxMessage.subject == subject,
            )
            .first()
        )

        if existing_reorder:
            continue

        message = create_outbox_message(
            db=db,
            medicine=medicine,
            subject=subject,
            message=(
                f"{medicine.name} ({medicine.sku}) has "
                f"{sellable_stock} sellable units remaining. "
                f"Reorder threshold is "
                f"{medicine.reorder_threshold}."
            ),
        )

        db.add(message)
        reorder_alerts_created += 1

    db.commit()

    return {
        "message": "Daily pharmacy clock completed.",
        "run_date": current_date.isoformat(),
        "expired_quarantined": expired_count,
        "expiry_alerts_created": alerts_created,
        "reorder_alerts_created": reorder_alerts_created,
    }


# ============================================================
# Expiry alerts
# ============================================================

@app.get("/alerts")
def get_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alerts = (
        db.query(ExpiryAlert)
        .join(Batch)
        .join(Medicine)
        .filter(
            ExpiryAlert.status == "open"
        )
        .order_by(
            Batch.expiry_date.asc(),
            ExpiryAlert.id.asc(),
        )
        .all()
    )

    results = []

    for alert in alerts:
        results.append(
            {
                "id": alert.id,
                "batch_id": alert.batch_id,
                "medicine_name": alert.batch.medicine.name,
                "batch_no": alert.batch.batch_no,
                "expiry_date": (
                    alert.batch.expiry_date.isoformat()
                ),
                "message": alert.message,
                "status": alert.status,
            }
        )

    return results


# ============================================================
# Notification outbox
# ============================================================

@app.get("/outbox")
def get_outbox(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    messages = (
        db.query(OutboxMessage)
        .order_by(
            OutboxMessage.created_at.desc(),
            OutboxMessage.id.desc(),
        )
        .all()
    )

    return [
        {
            "id": message.id,
            "event_type": message.event_type,
            "recipient": message.recipient,
            "subject": message.subject,
            "message": message.message,
            "status": message.status,
            "created_at": (
                message.created_at.isoformat()
                if message.created_at
                else None
            ),
        }
        for message in messages
    ]


@app.post(
    "/outbox/{message_id}/deliver"
)
def deliver_outbox_message(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    message = (
        db.query(OutboxMessage)
        .filter(
            OutboxMessage.id == message_id
        )
        .first()
    )

    if not message:
        raise HTTPException(
            status_code=404,
            detail="Outbox message not found.",
        )

    message.status = "delivered"

    db.commit()
    db.refresh(message)

    return {
        "message": "Notification delivered.",
        "id": message.id,
        "status": message.status,
    }


# ============================================================
# Messy batch import
# ============================================================

@app.get("/import/template")
def import_template(
    current_user: User = Depends(get_current_user),
):
    content = (
        "sku,batch_no,quantity,expiry_date\n"
        "PARA-500,PARA001,10 units,31/12/2026\n"
        "PARA-500,PARA002,20,2027-01-15\n"
    )

    return StreamingResponse(
        iter([content]),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                'attachment; filename="batch_import_template.csv"'
            )
        },
    )


@app.post("/import/batches")
async def import_batches(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No file selected.",
        )

    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Only CSV files are supported.",
        )

    raw_content = await file.read()

    try:
        text = raw_content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="CSV file must use UTF-8 encoding.",
        )

    reader = csv.DictReader(
        io.StringIO(text)
    )

    required_columns = {
        "sku",
        "batch_no",
        "quantity",
        "expiry_date",
    }

    if not reader.fieldnames:
        raise HTTPException(
            status_code=400,
            detail="CSV file has no header row.",
        )

    actual_columns = {
        column.strip()
        for column in reader.fieldnames
        if column
    }

    missing_columns = (
        required_columns - actual_columns
    )

    if missing_columns:
        raise HTTPException(
            status_code=400,
            detail=(
                "Missing required columns: "
                + ", ".join(
                    sorted(missing_columns)
                )
            ),
        )

    imported = 0
    deduped = 0
    rejected = 0

    # Track duplicates inside the uploaded file.
    seen_rows = set()

    for row in reader:
        try:
            sku = (
                row.get("sku") or ""
            ).strip()

            batch_no = (
                row.get("batch_no") or ""
            ).strip()

            quantity_raw = row.get("quantity")
            expiry_raw = row.get("expiry_date")

            # ------------------------------------------------
            # Validate required values
            # ------------------------------------------------

            if (
                not sku
                or not batch_no
                or quantity_raw is None
                or expiry_raw is None
                or not str(expiry_raw).strip()
            ):
                rejected += 1
                continue

            quantity = parse_quantity(
                quantity_raw
            )

            expiry_date = parse_date(
                str(expiry_raw)
            )

            medicine = (
                db.query(Medicine)
                .filter(Medicine.sku == sku)
                .first()
            )

            # Unknown medicine/SKU.
            if not medicine:
                rejected += 1
                continue

            duplicate_key = (
                medicine.id,
                batch_no,
            )

            # ------------------------------------------------
            # Duplicate inside CSV
            # ------------------------------------------------

            if duplicate_key in seen_rows:
                deduped += 1
                continue

            seen_rows.add(duplicate_key)

            # ------------------------------------------------
            # Duplicate already in database
            # ------------------------------------------------

            existing = (
                db.query(Batch)
                .filter(
                    Batch.medicine_id == medicine.id,
                    Batch.batch_no == batch_no,
                )
                .first()
            )

            if existing:
                deduped += 1
                continue

            # ------------------------------------------------
            # Expired imports are quarantined, not sold.
            # ------------------------------------------------

            batch_status = (
                "quarantined"
                if expiry_date <= today()
                else "active"
            )

            batch = Batch(
                medicine_id=medicine.id,
                batch_no=batch_no,
                quantity=quantity,
                expiry_date=expiry_date,
                status=batch_status,
            )

            db.add(batch)
            imported += 1

        except (ValueError, TypeError):
            rejected += 1

    db.commit()

    return {
        "message": "Batch import completed.",
        "imported": imported,
        "deduped": deduped,
        "rejected": rejected,
    }


# ============================================================
# Development / assessment summary
# ============================================================

@app.get("/debug/summary")
def debug_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return {
        "users": db.query(User).count(),
        "medicines": db.query(Medicine).count(),
        "batches": db.query(Batch).count(),
        "active_batches": (
            db.query(Batch)
            .filter(Batch.status == "active")
            .count()
        ),
        "quarantined_batches": (
            db.query(Batch)
            .filter(Batch.status == "quarantined")
            .count()
        ),
        "expiry_alerts": (
            db.query(ExpiryAlert).count()
        ),
        "outbox_messages": (
            db.query(OutboxMessage).count()
        ),
    }

