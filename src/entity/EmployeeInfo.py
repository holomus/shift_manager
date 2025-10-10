from pydantic import BaseModel
from .Job import Job
from .Interval import Interval
from .Shift import Shift
from .WorkConstraints import WorkConstraints

class EmployeeInfo(BaseModel):
    employee_id: str
    available_jobs: list[Job]
    available_intervals: list[Interval]
    preferred_intervals: list[Interval]
    work_constraints: list[WorkConstraints]
    last_sunday_shift: Shift | None