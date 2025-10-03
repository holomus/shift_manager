from pydantic import BaseModel

class ShiftTemplate(BaseModel):
    template_id: str
    start_minute: int
    end_minute: int
    usage_penalty: int

    def get_duration(self) -> int:
        return self.end_minute - self.start_minute