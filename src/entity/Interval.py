from pydantic import BaseModel

class Interval(BaseModel):
    start_minute: int
    end_minute: int