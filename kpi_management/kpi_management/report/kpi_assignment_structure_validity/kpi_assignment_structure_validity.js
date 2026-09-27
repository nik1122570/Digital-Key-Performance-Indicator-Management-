frappe.query_reports["KPI Assignment Structure Validity"] = {
  "filters": [
    {
      "fieldname": "company",
      "label": "Company",
      "fieldtype": "Link",
      "options": "Company"
    },
    {
      "fieldname": "department",
      "label": "Department",
      "fieldtype": "Link",
      "options": "Department"
    },
    {
      "fieldname": "employee",
      "label": "Employee",
      "fieldtype": "Link",
      "options": "Employee"
    },
    {
      "fieldname": "review_frequency",
      "label": "Frequency",
      "fieldtype": "Select",
      "options": "\nMonthly\nQuarterly\nSemi-Annual"
    }
  ]
};

