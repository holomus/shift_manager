from pydantic import BaseModel

class Interval(BaseModel):
    day_of_week: int
    start_minute: int
    end_minute: int