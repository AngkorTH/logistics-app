"""Router: Smart Dispatch Queue — คิวจ่ายงานจัดลำดับคนขับ (Supervisor+)

⚠️ Driver เข้าถึงไม่ได้ — guard ด้วย require_supervisor ทุก endpoint
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_supervisor
from app.models import User
from app.schemas.management import DispatchDriverOut, DispatchQueueOut
from app.services.dispatch import DriverQueueItem, build_dispatch_queue

router = APIRouter(prefix="/dispatch", tags=["dispatch"])


def _to_out(item: DriverQueueItem) -> DispatchDriverOut:
    trip = item.active_trip
    return DispatchDriverOut(
        id=item.driver.id,
        emp_id=item.driver.emp_id,
        name=item.driver.name,
        rating=item.driver.rating,
        current_status=item.current_status.value,
        prev_difficulty=item.prev_difficulty,
        prev_load_seconds=item.prev_load_seconds,
        active_trip_id=trip.id if trip else None,
        active_trip_code=trip.code if trip else None,
        plate=trip.plate if trip else None,
    )


def _matches(out: DispatchDriverOut, q: str) -> bool:
    """ค้นหาแบบ substring case-insensitive ด้วยชื่อคนขับ หรือเลขทะเบียนรถ"""
    needle = q.strip().lower()
    haystack = [out.name.lower(), out.emp_id.lower()]
    if out.plate:
        haystack.append(out.plate.lower())
    return any(needle in h for h in haystack)


@router.get("/queue", response_model=DispatchQueueOut)
def dispatch_queue(
    q: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_supervisor),
):
    """คิวจ่ายงาน: คนขับจัดกลุ่ม 3 สี · กลุ่ม White เรียงตาม Priority เรียบร้อยแล้ว

    q = คำค้น (ชื่อคนขับ / เลขทะเบียนรถ) — กรองทั้ง 3 กลุ่มสีแบบเรียลไทม์
    """
    groups = build_dispatch_queue(db)

    def render(items: list[DriverQueueItem]) -> list[DispatchDriverOut]:
        outs = [_to_out(i) for i in items]
        if q and q.strip():
            outs = [o for o in outs if _matches(o, q)]
        return outs

    return DispatchQueueOut(
        white=render(groups["white"]),
        orange=render(groups["orange"]),
        green=render(groups["green"]),
    )
