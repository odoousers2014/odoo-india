# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import datetime
from openerp.osv import fields, osv
from openerp import netsvc
import openerp.addons.decimal_precision as dp

class purchase_order_line(osv.Model):
    _inherit = 'purchase.order.line'
    
    def _amount_line(self, cr, uid, ids, prop, arg, context=None):
        res = super(purchase_order_line, self)._amount_line(cr, uid, ids, prop, arg, context=context)
        cur_obj=self.pool.get('res.currency')
        tax_obj = self.pool.get('account.tax')
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] -= line.discount
            taxes = tax_obj.compute_all(cr, uid, line.taxes_id, res[line.id], 1, line.product_id, line.order_id.partner_id)
            cur = line.order_id.pricelist_id.currency_id
            res[line.id] = cur_obj.round(cr, uid, cur, taxes['total'])
        return res

    _columns = {
        'discount': fields.float('Discount'),
        'price_subtotal': fields.function(_amount_line, string='Subtotal', digits_compute= dp.get_precision('Account')),
                }
purchase_order_line()

class purchase_order(osv.Model):
    _inherit = 'purchase.order'
    
    def _amount_all(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        cur_obj=self.pool.get('res.currency')
        for order in self.browse(cr, uid, ids, context=context):
            res[order.id] = {
                'amount_untaxed': 0.0,
                'amount_tax': 0.0,
                'amount_total': 0.0,
                'other_charges': 0.0,
            }
            val = val1 = 0.0
            cur = order.pricelist_id.currency_id
            for line in order.order_line:
               val1 += line.price_subtotal
               for c in self.pool.get('account.tax').compute_all(cr, uid, line.taxes_id, line.price_subtotal, 1, line.product_id, order.partner_id)['taxes']:
                    val += c.get('amount', 0.0)
            other_charge = (order.package_and_forwording + order.insurance + order.octroi) - order.commission
            res[order.id]['amount_tax']=cur_obj.round(cr, uid, cur, val)
            res[order.id]['amount_untaxed']=cur_obj.round(cr, uid, cur, val1)
            res[order.id]['other_charges'] = cur_obj.round(cr, uid, cur, other_charge)
            res[order.id]['amount_total']=res[order.id]['amount_untaxed'] + res[order.id]['amount_tax'] + res[order.id]['other_charges']
        return res
    
    def _get_order(self, cr, uid, ids, context=None):
        return super(purchase_order, self.pool.get('purchase.order'))._get_order(cr, uid, ids, context=context)
    
    _columns = {
        'package_and_forwording': fields.float('Packing & Forwarding'),
        'insurance': fields.float('Insurance'),
        'commission': fields.float('Commission'),
        'other_charge': fields.float('Other Charges'),
        'other_discount': fields.float('Other Discount'),
        'octroi': fields.float('Octroi'),
        'delivey': fields.char('Ex. GoDown / Mill Delivey',size=50),
        'last_po_series': fields.many2one('product.order.series', 'PO Series'),
        'amount_untaxed': fields.function(_amount_all, digits_compute= dp.get_precision('Account'), string='Untaxed Amount',
            store={
                'purchase.order.line': (_get_order, None, 10),
            }, multi="sums", help="The amount without tax", track_visibility='always'),
        'amount_tax': fields.function(_amount_all, digits_compute= dp.get_precision('Account'), string='Taxes',
            store={
                'purchase.order.line': (_get_order, None, 10),
            }, multi="sums", help="The tax amount"),
        'amount_total': fields.function(_amount_all, digits_compute= dp.get_precision('Account'), string='Total',
            store={
                'purchase.order.line': (_get_order, None, 10),
            }, multi="sums",help="The total amount"),
        'other_charges': fields.function(_amount_all, digits_compute= dp.get_precision('Account'), string='Other Charges',
            store={
                'purchase.order.line': (_get_order, None, 10),
            }, multi="sums",help="The other charge"),
                }

    def wkf_confirm_order(self, cr, uid, ids, context=None):
        res = super(purchase_order, self).wkf_confirm_order(cr, uid, ids, context=context)
        proc_obj = self.pool.get('procurement.order')
        for po in self.browse(cr, uid, ids, context=context):
            
            if po.requisition_id and (po.requisition_id.exclusive=='exclusive'):
                for order in po.requisition_id.purchase_ids:
                    suppler = order.partner_id.id
                    if order.id != po.id:
                        proc_ids = proc_obj.search(cr, uid, [('purchase_id', '=', order.id)])
                        if proc_ids and po.state=='confirmed':
                            proc_obj.write(cr, uid, proc_ids, {'purchase_id': po.id})
                        wf_service = netsvc.LocalService("workflow")
                        wf_service.trg_validate(uid, 'purchase.order', order.id, 'purchase_cancel', cr)
                    po.requisition_id.tender_done(context=context)
                for line in po.requisition_id.line_ids:
                    today = datetime.datetime.today()
                    year = datetime.datetime.today().year
                    month = datetime.datetime.today().month
                    if month<4:
                        po_year=str(datetime.datetime.today().year-1)+'-'+str(datetime.datetime.today().year)
                    else:
                        po_year=str(datetime.datetime.today().year)+'-'+str(datetime.datetime.today().year+1)
                    self.pool.get('product.product').write(cr,uid,line.product_id.id,{'last_supplier_code':suppler,'last_po_date':today.strftime("%Y-%m-%d"),'last_po_year':po_year},context=context)
        return res    
purchase_order()