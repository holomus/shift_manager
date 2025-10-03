from pydantic import BaseModel
from .DemandIntervals import DemandIntervals

class JobDemand(BaseModel):
    job_id: str
    under_coverage_penalty_coefficient: int
    over_coverage_penalty_coefficient: int
    demand_intervals: list[DemandIntervals]