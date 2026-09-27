frappe.ui.form.on('KPI Review', {
    async refresh(frm) {
        frm.disable_save();
        frm.page.clear_actions_menu();
        if (frm.is_new()) { frm.set_intro(__('Reviews are created from closed periods or the controlled amendment action.')); return; }
        const result = await frappe.call({method:'kpi_management.api.capabilities',args:{name:frm.doc.name}});
        const can = result.message;
        const d = frm.doc;
        kpi_management.overview(frm);
        frm.set_df_property('self_total','hidden',!d.self_complete);
        frm.set_df_property('final_total','hidden',!d.final_complete);
        const completed = d.docstatus === 1;
        const state = !d.applicable_weight ? __('No applicable components — submission blocked') : completed ? __('Official submitted result') : __('Draft — only entered ratings contribute to provisional totals');
        frm.set_intro(state, !d.applicable_weight ? 'orange' : completed ? 'green' : 'blue');
        frm.add_custom_button(__('Scorecard'), () => frappe.set_route('print','KPI Review',d.name), __('View'));
        if (d.docstatus === 0) {
            if (can.employee && d.workflow_state === 'Pending Self Rating') {
                frm.add_custom_button(__('Enter Self Assessment'), () => kpi_management.entry(frm,false));
                frm.add_custom_button(__('Employee Summary'), () => kpi_management.summary(frm,false));
                frm.add_custom_button(__('Send for Final Rating'), () => kpi_management.call(frm,'send_for_final'));
                frm.add_custom_button(__('Clear Self Entry'), () => kpi_management.pick_row(frm,'Clear self entry',r => kpi_management.call(frm,'record_self',{entries:[{name:r.name,clear:1}],summary:{}}),true), __('Actions'));
            }
            if (can.employee) {
                frm.add_custom_button(__('Request Applicability Change'), () => kpi_management.pick_row(frm,'Request applicability change',r => kpi_management.reason(frm,'Explain the requested change','request_applicability',{row_name:r.name})), __('Actions'));
            }
            if (can.reviewer) {
                frm.add_custom_button(__('Target Overrides — Applicability'), () => kpi_management.pick_row(frm,'Exclude or reinstate a component',r => kpi_management.reason(frm,r.not_applicable ? 'Reinstate component' : 'Mark component N/A','set_applicability',{row_name:r.name,excluded:r.not_applicable ? 0 : 1})), __('Actions'));
                if (d.workflow_state === 'Pending Final Rating') {
                    frm.add_custom_button(__('Enter Final Rating'), () => kpi_management.entry(frm,true));
                    frm.add_custom_button(__('Final Summary'), () => kpi_management.summary(frm,true));
                    frm.add_custom_button(__('Complete and Submit'), () => frappe.confirm(__('Submit the completed assessment?'),() => kpi_management.call(frm,'complete')));
                    frm.add_custom_button(__('Return to Employee'), () => kpi_management.reason(frm,'Return to employee','return_to_employee'),__('Actions'));
                    frm.add_custom_button(__('Clear Final Entry'), () => kpi_management.pick_row(frm,'Clear final entry',r => kpi_management.call(frm,'record_final',{entries:[{name:r.name,clear:1}],summary:{}}),true),__('Actions'));
                }
            }
            if (can.manager) frm.add_custom_button(__('Delete Draft for Correction'), () => kpi_management.reason(frm,'Delete Draft (full audit snapshot retained)','delete_draft'),__('Corrections'));
        }
        if (can.manager && completed) frm.add_custom_button(__('Cancel Review'),() => kpi_management.reason(frm,'Cancel submitted review','cancel'),__('Corrections'));
        if (can.manager && d.docstatus === 2) {
            frm.add_custom_button(__('Amend Review'),() => kpi_management.reason(frm,'Create a fresh assessment amendment','amend'),__('Corrections'));
            frm.add_custom_button(__('Amend with Corrected Assignment'),() => frappe.prompt([
                {fieldname:'corrected_assignment',label:__('Corrected submitted Assignment'),fieldtype:'Link',options:'KPI Structure Assignment',reqd:1,get_query:() => ({filters:{docstatus:1,employee:d.employee,review_frequency:d.review_frequency}})},
                {fieldname:'reason',label:__('Correction reason'),fieldtype:'Small Text',reqd:1}],
                values => kpi_management.call(frm,'amend',values),__('Correct source and amend'),__('Create Draft')),__('Corrections'));
        }
    }
});

