frappe.ui.form.on('KPI Structure Assignment', {
    setup(frm) { frm.set_query('kpi_structure',() => ({filters:{docstatus:1}})); },
    async onload(frm) {
        if (frm.is_new()) {
            const s = await frappe.db.get_doc('KPI Settings');
            frm.set_value('self_due_days',s.default_self_due_days);
            frm.set_value('final_due_days',s.default_final_due_days);
        }
    },
    refresh(frm) {
        if (frm.doc.docstatus === 1 && frappe.user.has_role('KPI Manager')) {
            frm.add_custom_button(__('Recover Closed Period'),() => frappe.prompt([
                {fieldname:'period_start',label:__('Period Start'),fieldtype:'Date',reqd:1},
                {fieldname:'period_end',label:__('Period End'),fieldtype:'Date',reqd:1},
                {fieldname:'correction_reason',label:__('Correction reason (required after a Draft deletion)'),fieldtype:'Small Text'}],
                async values => { const r=await frappe.call({method:'kpi_management.api.recover_period',args:{assignment:frm.doc.name,...values},freeze:true});frappe.set_route('Form','KPI Review',r.message.name); },__('Generate one missing period'),__('Create Draft')));
        }
    }
});

