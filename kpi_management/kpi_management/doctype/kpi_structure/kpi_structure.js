frappe.ui.form.on('KPI Structure', {
    setup(frm) {
        frm.set_query('kpi_component','components',() => ({filters:{disabled:0}}));
        frm.set_query('perspective','components',() => ({filters:{disabled:0}}));
    },
    refresh(frm) {
        const groups = {};
        (frm.doc.components || []).forEach(r => { const p=r.perspective_label || r.perspective || __('Unclassified'); groups[p]=(groups[p] || 0)+flt(r.weight); });
        frm.set_intro(Object.entries(groups).map(([p,w]) => `${frappe.utils.escape_html(p)}: ${w.toFixed(2)}%`).join(' · '));
    }
});
frappe.ui.form.on('KPI Structure Item', {
    async kpi_component(frm,cdt,cdn) {
        const row=locals[cdt][cdn];
        if (!row.kpi_component) return;
        const component=await frappe.db.get_doc('KPI Component',row.kpi_component);
        for (const field of ['objective','metric','indicator','perspective']) await frappe.model.set_value(cdt,cdn,field,component[field]);
        for (const field of ['target_number','target_choice','target_date','target_text','duration_unit','currency']) await frappe.model.set_value(cdt,cdn,field,field==='target_number' ? 0 : null);
        frm.refresh_field('components');
    },
    weight(frm) { frm.trigger('refresh'); }
});

