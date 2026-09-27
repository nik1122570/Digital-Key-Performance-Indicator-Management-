/* SF KPI: all business mutations go through narrow server actions. */
frappe.provide('kpi_management');

kpi_management.call = async function(frm, method, extra = {}) {
    const response = await frappe.call({method: `kpi_management.api.${method}`,
        args: {name: frm.doc.name, modified: frm.doc.modified, ...extra}, freeze: true});
    if (response.message?.name && response.message.name !== frm.doc.name) {
        frappe.set_route('Form', 'KPI Review', response.message.name);
    } else if (response.message?.deleted) {
        frappe.set_route('List', 'KPI Review');
    } else {
        await frm.reload_doc();
    }
    return response.message;
};

kpi_management.reason = function(frm, title, method, extra = {}) {
    frappe.prompt([{fieldname:'reason', fieldtype:'Small Text', label:__('Reason'), reqd:1}],
        values => kpi_management.call(frm, method, {...extra, reason:values.reason}), __(title), __('Confirm'));
};

kpi_management.pick_row = function(frm, title, callback, applicableOnly = false) {
    const rows = frm.doc.items.filter(r => !applicableOnly || !r.not_applicable);
    if (!rows.length) { frappe.msgprint(__('There are no applicable components.')); return; }
    const options = rows.map(r => `${r.idx}. ${r.objective}${r.not_applicable ? ' [N/A]' : ''}`);
    frappe.prompt([{fieldname:'row',label:__('Component'),fieldtype:'Select',options,reqd:1}],
        values => callback(rows[options.indexOf(values.row)]), __(title), __('Continue'));
};

kpi_management.entry = function(frm, final) {
    kpi_management.pick_row(frm, final ? 'Enter final rating' : 'Enter self assessment', row => {
        const stage = final ? 'final' : 'self';
        const fields = [{fieldname:'context',fieldtype:'HTML', options:
            `<p><b>${frappe.utils.escape_html(row.objective)}</b></p><p>${frappe.utils.escape_html(row.metric)}</p>` +
            `<p>${__('Target')}: ${frappe.utils.escape_html(row.target_display)} · ${__('Original weight')}: ${row.original_weight} · ${__('Effective weight')}: ${row.effective_weight}</p>`}];
        let actualField;
        if (!final) {
            const numeric = ['Percentage','Number','Currency','Duration'].includes(row.indicator);
            const suffix = numeric ? 'number' : {'Yes No':'choice','Date':'date','Text':'text'}[row.indicator];
            actualField = `actual_${suffix}`;
            const unit = row.indicator === 'Percentage' ? '%' : row.currency || row.duration_unit || '';
            const df = {fieldname:actualField,fieldtype:numeric ? 'Float' : {'choice':'Select','date':'Date','text':'Small Text'}[suffix],
                label:`${__('Actual result')} ${unit}`, reqd:!numeric, precision:6,
                default:row.actual_entered ? row[actualField] : null};
            if (suffix === 'choice') df.options = '\nYes\nNo';
            fields.push(df);
        } else {
            fields.push({fieldtype:'HTML',fieldname:'self_context',options:`<p>${__('Self rating')}: ${row.self_rating} / ${row.original_weight}</p><p>${frappe.utils.escape_html(row.employee_comment || '')}</p>`});
        }
        fields.push({fieldname:`${stage}_rating`,fieldtype:'Float',precision:2,label:`${__('Rating')} (0 – ${row.original_weight})`,
            description:__('Rate against the ORIGINAL weight. The server calculates normalized points.'),
            default:row[`${stage}_rating_entered`] ? row[`${stage}_rating`] : null});
        const comment = final ? 'reviewer_comment' : 'employee_comment';
        fields.push({fieldname:comment,fieldtype:'Small Text',label:final ? __('Reviewer comment (required for variance)') : __('Employee comment'),default:row[comment],reqd:!final});
        fields.push({fieldname:'confirm_entry',fieldtype:'Check',label:final ? __('I confirm this rating, including zero if shown.') : __('I confirm this actual result and rating, including zero if shown.'),default:0});
        const dialog = new frappe.ui.Dialog({title:__(final ? 'Final assessment' : 'Self assessment'),fields,
            primary_action_label:__('Record entry'), primary_action:async values => {
                if (!values.confirm_entry) { frappe.msgprint(__('Confirm the entered values before recording.')); return; }
                const entry = {name:row.name,[`${stage}_rating`]:values[`${stage}_rating`],[comment]:values[comment]};
                if (!final) entry[actualField] = values[actualField];
                await kpi_management.call(frm, final ? 'record_final' : 'record_self', {entries:[entry], summary:{}});
                dialog.hide();
            }});
        dialog.show();
    }, true);
};

kpi_management.summary = function(frm, final) {
    const keys = final ? ['final_summary','strengths','improvement_actions'] : ['employee_summary','development_needs'];
    frappe.prompt(keys.map((key,index) => ({fieldname:key,fieldtype:'Small Text',label:frappe.model.unscrub(key),default:frm.doc[key],reqd:index === 0})),
        values => kpi_management.call(frm, final ? 'record_final' : 'record_self',{entries:[],summary:values}),__('Assessment summary'),__('Save summary'));
};

kpi_management.overview = function(frm) {
    const e = value => frappe.utils.escape_html(String(value ?? ''));
    const groups = {};
    for (const row of frm.doc.items || []) (groups[row.perspective_label || __('Unclassified')] ||= []).push(row);
    let html = `<div class="text-muted small">${__('Scores below are normalized points. Enter ratings against each component’s original weight.')}</div>`;
    for (const [perspective,rows] of Object.entries(groups)) {
        html += `<h5 class="mt-4">${e(perspective)}</h5><div class="table-responsive"><table class="table table-bordered"><thead><tr><th>${__('KPI and Target')}</th><th>${__('Actual')}</th><th>${__('Original / Effective Weight')}</th><th>${__('Self / Final Points')}</th></tr></thead><tbody>`;
        for (const row of rows) {
            let actual = row.actual_text || row.actual_date || row.actual_choice || '';
            if (['Percentage','Number','Currency','Duration'].includes(row.indicator)) actual = `${row.actual_number} ${row.indicator === 'Percentage' ? '%' : row.currency || row.duration_unit || ''}`;
            if (!row.actual_entered) actual = __('Not entered');
            if (row.not_applicable) actual = `N/A — ${row.na_reason}`;
            const self = row.not_applicable ? 'N/A' : row.self_rating_entered ? flt(row.self_points).toFixed(2) : __('Not entered');
            const final = row.not_applicable ? 'N/A' : row.final_rating_entered ? flt(row.final_points).toFixed(2) : __('Not entered');
            html += `<tr><td><b>${e(row.objective)}</b><br>${e(row.target_display)}</td><td>${e(actual)}</td><td>${e(flt(row.original_weight).toFixed(2))} / ${e(flt(row.effective_weight).toFixed(2))}</td><td>${e(self)} / ${e(final)}</td></tr>`;
        }
        html += '</tbody></table></div>';
    }
    frm.fields_dict.assessment_overview.$wrapper.html(html);
};

