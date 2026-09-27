frappe.query_reports["My KPI Performance"] = {
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
    },
    {
      "fieldname": "final_reviewed_by",
      "label": "Final Reviewer",
      "fieldtype": "Link",
      "options": "User"
    },
    {
      "fieldname": "review_year",
      "label": "Review Year",
      "fieldtype": "Int"
    },
    {
      "fieldname": "period_start",
      "label": "Period Start From",
      "fieldtype": "Date"
    },
    {
      "fieldname": "period_end",
      "label": "Period End To",
      "fieldtype": "Date"
    }
  ]
};

