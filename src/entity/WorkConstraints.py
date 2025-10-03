from pydantic import BaseModel

class WorkConstraints(BaseModel):
    min_rest_minutes: int
    soft_max_weekly_minutes: int
    soft_max_weekly_minutes_penalty: int
    hard_max_weekly_minutes: int