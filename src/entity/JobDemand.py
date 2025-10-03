from pydantic import BaseModel
from .DemandIntervals import DemandIntervals

class JobDemand(BaseModel):
    job_id: str
    under_coverage_penalty: int
    over_coverage_penalty: int
    demand_intervals: list[DemandIntervals]
    open_shift_penalty: int