from pydantic import BaseModel

class Shift(BaseModel):
    employee_id: str | None
    template_id: str
    job_id: str
    day_of_week: int
    start_minute: int | None
    end_minute: int | None