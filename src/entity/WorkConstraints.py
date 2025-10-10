from pydantic import BaseModel

class WorkConstraints(BaseModel):
    min_rest_minutes: int
    soft_max_weekly_minutes: int
    over_weekly_minutes_penalty: int
    hard_max_weekly_minutes: int
    max_daily_minutes: int
    max_working_days_sequence: int
    min_weekly_rest_days: int