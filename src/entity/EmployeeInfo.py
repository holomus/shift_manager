from pydantic import BaseModel
from .Job import Job
from .Interval import Interval
from .Shift import Shift

class EmployeeInfo(BaseModel):
    employee_id: str
    available_jobs: list[Job]
    unavailable_intervals: list[Interval]
    last_sunday_shift: Shift | None