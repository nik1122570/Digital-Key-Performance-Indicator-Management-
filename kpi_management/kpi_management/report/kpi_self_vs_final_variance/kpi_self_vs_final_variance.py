from kpi_management.reports import execute as run_report


def execute(filters=None):
    return run_report("KPI Self vs Final Variance", filters)

