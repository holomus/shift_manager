from pydantic import BaseModel

class WorkConstraints(BaseModel):
    min_rest_minutes: int
    regular_weekly_minutes: int
    over_weekly_minutes_penalty: int
    under_weekly_minutes_penalty: int
    hard_max_weekly_minutes: int