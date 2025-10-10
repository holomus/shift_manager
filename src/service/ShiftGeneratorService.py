from entity import EmployeeInfo, ShiftTemplate, JobDemand, Shift, WorkConstraints
from ortools.sat.python import cp_model
from fastapi import HTTPException

class ShiftGeneratorService:
    _MAX_SOLVE_TIME_IN_SECONDS = 10.0

    def _get_shift_name(
            self,
            employee_id: str,
            job_id: str,
            template_id: str,
            day_of_week: int,
    ) -> str:
        return f"shift_{employee_id}_{job_id}_{template_id}_{day_of_week}"

    def _add_employee_work_constraints(
            self, 
            model: cp_model.CpModel,
            employees: list[EmployeeInfo], 
            shift_templates: list[ShiftTemplate],
            shifts: list[Shift]
    ) -> tuple[list[cp_model.IntVar], list[int], list[cp_model.BoolVarT], list[int]]:
        return [], [], [], []

    def _add_open_shifts(
            self, 
            model: cp_model.CpModel,
            shift_templates: list[ShiftTemplate], 
            job_demands: list[JobDemand]
    ) -> tuple[list[cp_model.IntVar], list[int], list[cp_model.BoolVarT], list[int]]:
        if len(job_demands) == 0:
            return [], [], [], []
        return [], [], [], []

    def generate_shifts_by_week(
            self,
            employees: list[EmployeeInfo],
            shift_templates: list[ShiftTemplate],
            job_demands: list[JobDemand],
            shifts: list[Shift]
    ) -> tuple[str, float, list[Shift]]:
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
                            if last_shift is not None and last_shift.end_minute is not None:
                                if shift.start_minute < last_shift.end_minute - 24 * 60 + work_constraints.min_rest_minutes:
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
                    if (employee.employee_id, job.job_id, shift.template_id, d) in shifts
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

                                key1 = (employee.employee_id, job1.job_id, shift1.template_id, d)
                                key2 = (employee.employee_id, job2.job_id, shift2.template_id, shift2_day)

                                if key1 in  shifts and key2 in shifts and shift2_start < shift1_end + work_constraints.min_rest_minutes:
                                    model.AddBoolOr([shifts[key1].Not(), shifts[key2].Not()])

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
                model.add_max_equality(overwork, [excess, 0]) # overwork = max(0, excess)

                obj_int_vars.append(overwork)
                obj_int_coeffs.append(work_constraints.over_weekly_minutes_penalty)

        # Add open shifts to model
        open_shifts = {}
        max_demand_per_key = {}

        # First pass: compute max demand per (job_id, shift_template, day)
        for job_demand in job_demands:
            for demand in job_demand.demand_intervals:
                for d in range(demand.day_of_week - 1, demand.day_of_week + 2):
                    if d < 0 or d >= num_days:
                        continue
                    for shift in shift_templates:
                        if shift.usage_penalty > 0:
                            continue

                        shift_start = shift.start_minute
                        shift_end = shift.end_minute

                        if d < demand.day_of_week:
                            shift_start -= 24 * 60
                            shift_end -= 24 * 60
                        elif d > demand.day_of_week:
                            shift_start += 24 * 60
                            shift_end += 24 * 60

                        # only allow open shifts that overlap this demand
                        if shift_start < demand.end_minute and shift_end > demand.start_minute:
                            key = (job_demand.job_id, shift.template_id, d)
                            max_demand_per_key[key] = max(
                                max_demand_per_key.get(key, 0),
                                demand.demand
                            )

        # Second pass: create open shift variables using the maximum demand per key
        for key, max_demand in max_demand_per_key.items():
            job_id, template_id, d = key
            open_shifts[key] = model.new_int_var(
                0,
                max_demand,
                f"open_shifts_{job_id}_{template_id}_{d}"
            )

            # Optionally add penalties if needed
            # obj_int_vars.append(open_shifts[key])
            # obj_int_coeffs.append(job_demand.open_shift_penalty)

        for job_demand in job_demands:
            demand_intervals = sorted(job_demand.demand_intervals, key=lambda x: (x.day_of_week, x.start_minute))
            for demand in demand_intervals:
                coverage_terms = []
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

                        key = (job_demand.job_id, shift.template_id, d)
                        if key in open_shifts:
                            overlap = min(shift_end, demand.end_minute) - max(shift_start, demand.start_minute)
                            if overlap > 0:
                                coverage_terms.append(open_shifts[key] * overlap)                                 

                actual_coverage = sum(coverage_terms) if coverage_terms else 0
                required_minutes = demand.demand * demand.get_duration()

                unmet = model.new_int_var(
                    0, demand.demand  * demand.get_duration(),
                    f"unmet_{demand.day_of_week}_{demand.start_minute}_{demand.end_minute}"
                )

                excess = model.new_int_var(
                    # 0, (len(employees) - demand.demand) * demand.get_duration(),
                    0, (demand.demand) * demand.get_duration(),
                    f"excess_{demand.day_of_week}_{demand.start_minute}_{demand.end_minute}"
                )

                model.add(actual_coverage + unmet - excess == required_minutes)

                obj_int_vars.append(unmet)
                obj_int_coeffs.append(job_demand.under_coverage_penalty)    # cost per missing person-minute

                obj_int_vars.append(excess)
                obj_int_coeffs.append(job_demand.over_coverage_penalty)   # cost per extra person-minute


        model.minimize(
            sum(obj_bool_vars[i] * obj_bool_coeffs[i] for i in range(len(obj_bool_vars)))
            + sum(obj_int_vars[i] * obj_int_coeffs[i] for i in range(len(obj_int_vars)))
        )

        solver = cp_model.CpSolver()
        
        solver.parameters.max_time_in_seconds = self._MAX_SOLVE_TIME_IN_SECONDS
        
        solution_printer = cp_model.ObjectiveSolutionPrinter()
        status = solver.solve(model, solution_printer)

        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "No feasible solution found",
                    "solver_status": solver.status_name(status),
                    "stats": solver.ResponseStats(),
                },
            )
        
        shifts_result: list[Shift] = []

        for (employee_id, job_id, template_id, d), var in shifts.items():
            if (solver.boolean_value(var)):
                shifts_result.append(
                    Shift(
                        employee_id=employee_id,
                        job_id=job_id,
                        template_id=template_id,
                        day_of_week=d,
                        start_minute=None,
                        end_minute=None,
                    )
                )

        for (job_id, template_id, d), var in open_shifts.items():
            count = solver.value(var)
            if count > 0:
                for _ in range(count):
                    shifts_result.append(
                        Shift(
                            employee_id=None,
                            job_id=job_id,
                            template_id=template_id,
                            day_of_week=d,
                            start_minute=None,
                            end_minute=None,
                        )
                    )

        return (solver.status_name(status), solver.objective_value, shifts_result)
                        
