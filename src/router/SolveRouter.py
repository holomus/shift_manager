from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from entity import EmployeeInfo, ShiftTemplate, JobDemand, WorkConstraints, Shift
from service import ShiftGeneratorService

router = APIRouter(
  prefix='/solve',
  tags=['solve']
)   

class SolveResponse(BaseModel):
    status: str
    objective_value: int
    shifts: list[Shift]

def get_shift_generator_service() -> ShiftGeneratorService:
    return ShiftGeneratorService()

@router.post("/by_week", response_model=SolveResponse)
def solve_by_week(
    employees: list[EmployeeInfo], 
    shift_templates: list[ShiftTemplate], 
    job_demands: list[JobDemand], 
    work_constraints: WorkConstraints, 
    shift_generator: ShiftGeneratorService = Depends(get_shift_generator_service)
):
    status, objective_value, shifts = shift_generator.generate_shifts_by_week(
        employees,
        shift_templates,
        job_demands,
        work_constraints
    )

    return {
        "status": status,
        "objective_value": objective_value,
        "shifts": shifts
    }