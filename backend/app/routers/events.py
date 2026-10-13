from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.event import Event
from app.models.booking import Booking
from app.schemas.event import EventResponse
from app.services import refresh_event_statuses

router = APIRouter(prefix="/api/events", tags=["Events"])

@router.get("/", response_model=list[EventResponse])
def list_events(
    search: str | None = Query(default=None),
    category: str | None = Query(default=None),
    location: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    sort: str = Query(default="date", pattern="^(date|popularity|price)$"),
    db: Session = Depends(get_db),
):
    query = db.query(Event)
    if search:
        query = query.filter(Event.title.ilike(f"%{search.strip()}%"))
    if category:
        query = query.filter(Event.category.ilike(category))
    if location:
        query = query.filter(Event.location.ilike(f"%{location.strip()}%"))
    if date_from:
        query = query.filter(func.date(Event.event_date) >= date_from.isoformat())
    if date_to:
        query = query.filter(func.date(Event.event_date) <= date_to.isoformat())
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "date_from must be on or before date_to")
    if sort == "price":
        query = query.order_by(Event.ticket_price.asc(), Event.event_date.asc())
    elif sort == "popularity":
        confirmed_bookings = (
            db.query(func.count(Booking.id))
            .filter(Booking.event_id == Event.id, Booking.booking_status == "CONFIRMED")
            .correlate(Event)
            .scalar_subquery()
        )
        query = query.order_by(confirmed_bookings.desc(), Event.event_date.asc())
    else:
        query = query.order_by(Event.event_date.asc())
    events = query.all()
    refresh_event_statuses(db, events)
    return events

@router.get("/categories")
def categories():
    return {"categories": ["Music", "Tech", "Sports", "Business"]}

@router.get("/{event_id}", response_model=EventResponse)
def get_event(event_id: int, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(404, "Event not found")
    refresh_event_statuses(db, [event])
    return event
