from entity import EmployeeInfo, ShiftTemplate, JobDemand, Shift, WorkConstraints
from google.protobuf import text_format
from ortools.sat.python import cp_model

from absl import flags

_PARAMS = flags.DEFINE_string(
    "params", "max_time_in_seconds:10.0", "Sat solver parameters."
)

class ShiftGeneratorService:
    def _get_shift_name(
            self,
            employee_id: str,
            job_id: str,
            template_id: str,
            dayOfWeek: int,
    ) -> str:
        return f"shift_{employee_id}_{job_id}_{template_id}_{dayOfWeek}"

    def generate_shifts_by_week(
            self,
            employees: list[EmployeeInfo],
            shift_templates: list[ShiftTemplate],
            job_demands: list[JobDemand],
            work_constraints: WorkConstraints,
    ) -> list[Shift]:
        model = cp_model.CpModel()

        shift_templates = sorted(shift_templates, key=lambda x: x.start_minute)

        # Linear terms of the objective in a minimization context.
        obj_int_vars: list[cp_model.IntVar] = []
        obj_int_coeffs: list[int] = []
        obj_bool_vars: list[cp_model.BoolVarT] = []
        obj_bool_coeffs: list[int] = []

        num_days = 7

        shifts = {}

        # Decision variables: whether an employee works a shift on a given day.
        for employee in employees:
            for job in employee.available_jobs:
                for shift in shift_templates:
                    for d in range(num_days):
                        if d == 0:
                            last_shift = employee.last_sunday_shift
                            if last_shift is not None and shift.start_minute < last_shift.end_minute - 24 * 60 + work_constraints.min_rest_minutes:
                                continue

                        shifts[
                            employee.employee_id,
                            job.job_id,
                            shift.template_id,
                            d,
                        ] = model.new_bool_var(self._get_shift_name(employee.employee_id, job.job_id, shift.template_id, d))

                        obj_bool_vars.append(shifts[employee.employee_id, job.job_id, shift.template_id, d])
                        obj_bool_coeffs.append(shift.usage_penalty)

        # At most shift per day.
        for employee in employees:
            for d in range(num_days):
                model.add_at_most_one(
                    shifts[employee.employee_id, job.job_id, shift.template_id, d]
                    for job in employee.available_jobs
                    for shift in shift_templates
                )

        # Minimal rest between shifts.
        for employee in employees:
            for d in range(num_days - 1):
                for i1, job1 in enumerate(employee.available_jobs):
                    for s1, shift1 in enumerate(shift_templates):
                        for i2, job2 in enumerate(employee.available_jobs):
                            for s2, shift2 in enumerate(shift_templates):
                                if job1 == job2 and s1 == s2:
                                    continue

                                if (i2, s2) <= (i1, s1):
                                    continue

                                shift1_end = shift1.end_minute
                                shift2_start = shift2.start_minute
                                shift2_day = d

                                if s2 < s1:
                                    shift2_start += 24 * 60
                                    shift2_day += 1

                                if shift2_start < shift1_end + work_constraints.min_rest_minutes:
                                    model.AddBoolXOr(
                                        (
                                            shifts[employee.employee_id, job1.job_id, shift1.template_id, d],
                                            shifts[employee.employee_id, job2.job_id, shift2.template_id, shift2_day]
                                        )
                                    )

        # Weekly work time constraints.
        for employee in employees:
            total_minutes = []
            for job in employee.available_jobs:
                for shift in shift_templates:
                    for d in range(num_days):
                        if (employee.employee_id, job.job_id, shift.template_id, d) in shifts:
                            total_minutes.append(
                                shifts[employee.employee_id, job.job_id, shift.template_id, d] * shift.get_duration()
                            )
            
            if total_minutes:
                total_weekly_minutes = model.new_int_var(0, work_constraints.hard_max_weekly_minutes, f"total_weekly_minutes_{employee.employee_id}")

                model.add(total_weekly_minutes == sum(total_minutes))

                excess = model.new_int_var(
                    -work_constraints.soft_max_weekly_minutes,
                    work_constraints.hard_max_weekly_minutes - work_constraints.soft_max_weekly_minutes,
                    f"excess_{employee.employee_id}"
                )
                model.add(excess == total_weekly_minutes - work_constraints.soft_max_weekly_minutes)

                overwork = model.new_int_var(
                    0,
                    work_constraints.hard_max_weekly_minutes - work_constraints.soft_max_weekly_minutes,
                    f"overwork_{employee.employee_id}"
                )

                model.add_max_equality(overwork, [excess, 0])

                obj_int_vars.append(overwork)
                obj_int_coeffs.append(work_constraints.soft_max_weekly_minutes_penalty)


        for job_demand in job_demands:
            coverage_terms = []
            demand_intervals = sorted(job_demand.demand_intervals, key=lambda x: (x.day_of_week, x.start_minute))
            for demand in demand_intervals:
                for employee in employees:
                    if job_demand.job_id in [job.job_id for job in employee.available_jobs]:
                        for d in range(demand.day_of_week - 1, demand.day_of_week + 2):
                            if d < 0 or d >= num_days:
                                continue
                            for shift in shift_templates:
                                shift_start = shift.start_minute
                                shift_end = shift.end_minute

                                if d < demand.day_of_week:
                                    shift_start -= 24 * 60
                                    shift_end -= 24 * 60

                                if d > demand.day_of_week:
                                    shift_start += 24 * 60
                                    shift_end += 24 * 60

                                if (employee.employee_id, job_demand.job_id, shift.template_id, d) in shifts:
                                    overlap = min(shift_end, demand.end_minute) - max(shift_start, demand.start_minute)
                                    if overlap > 0:
                                        shift_var = shifts[employee.employee_id, job_demand.job_id, shift.template_id, d]
                                        coverage_terms.append(shift_var * overlap)                                    

                actual_coverage = sum(coverage_terms) if coverage_terms else 0
                required_minutes = demand.demand * demand.get_duration()

                unmet = model.new_int_var(
                    0, demand.demand,
                    f"unmet_{demand.day_of_week}_{demand.start_minute}_{demand.end_minute}"
                )

                excess = model.new_int_var(
                    0, len(employees) - demand.demand,
                    f"excess_{demand.day_of_week}_{demand.start_minute}_{demand.end_minute}"
                )

                model.add(actual_coverage + unmet - excess == required_minutes)

                obj_int_vars.append(unmet)
                obj_int_coeffs.append(job_demand.under_coverage_penalty_coefficient)    # cost per missing person-minute

                obj_int_vars.append(excess)
                obj_int_coeffs.append(job_demand.over_coverage_penalty_coefficient)   # cost per extra person-minute


        model.minimize(
            sum(obj_bool_vars[i] * obj_bool_coeffs[i] for i in range(len(obj_bool_vars)))
            + sum(obj_int_vars[i] * obj_int_coeffs[i] for i in range(len(obj_int_vars)))
        )

        solver = cp_model.CpSolver()
        text_format.Parse(_PARAMS.value, solver.parameters)
        
        solution_printer = cp_model.ObjectiveSolutionPrinter()
        status = solver.solve(model, solution_printer)

        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            raise Exception(
                f"No solution found. Status: {status}\n"
                f"Stats:\n{solver.ResponseStats()}"
            )
        
        shifts_result = []

        for employee in employees:
            for job in employee.available_jobs:
                for shift in shift_templates:
                    for d in range(num_days):
                        if (solver.boolean_value(shifts[employee.employee_id, job.job_id, shift.template_id, d])):
                            shifts_result.append(
                                Shift(
                                    employee_id=employee.employee_id,
                                    job_id=job.job_id,
                                    template_id=shift.template_id,
                                    day_of_week=d,
                                    start_minute=shift.start_minute,
                                    end_minute=shift.end_minute,
                                )
                            )

        return shifts_result
                        
