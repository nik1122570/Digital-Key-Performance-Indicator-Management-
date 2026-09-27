app_name = "kpi_management"
app_title = "KPI Management"
app_publisher = "SF Group"
app_description = "KPI Management for ERPNext"
app_email = ""
app_license = "Proprietary"
required_apps = ["erpnext", "hrms"]
before_install = "kpi_management.install.before_install"
after_install = "kpi_management.install.after_install"
after_migrate = "kpi_management.install.after_migrate"
app_include_js = ["/assets/kpi_management/js/kpi.js"]
scheduler_events = {"daily": ["kpi_management.scheduler.daily"]}
permission_query_conditions = {
    "KPI Review": "kpi_management.permissions.review_query",
    "KPI Structure Assignment": "kpi_management.permissions.assignment_query",
    "KPI Structure": "kpi_management.permissions.structure_query",
}
has_permission = {
    "KPI Review": "kpi_management.permissions.review_permission",
    "KPI Structure Assignment": "kpi_management.permissions.assignment_permission",
    "KPI Structure": "kpi_management.permissions.structure_permission",
}
doc_events = {
    "File": {"validate": "kpi_management.security.validate_file"},
    "Comment": {"validate": "kpi_management.security.validate_comment"},
}
permission_query_conditions["KPI Audit Event"] = "kpi_management.permissions.audit_query"
has_permission["KPI Audit Event"] = "kpi_management.permissions.audit_permission"
has_permission["File"] = "kpi_management.security.file_permission"
permission_query_conditions["File"] = "kpi_management.security.file_query"
override_doctype_class = {"File": "kpi_management.security.KPIProtectedFile"}

