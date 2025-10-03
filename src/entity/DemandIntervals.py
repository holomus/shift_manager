from pydantic import BaseModel

class DemandIntervals(BaseModel):
    start_minute: int
    end_minute: int
    day_of_week: int
    demand: int

    def get_duration(self) -> int:
        return self.end_minute - self.start_minute