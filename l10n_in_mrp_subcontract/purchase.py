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
import time
import netsvc

from openerp.osv import osv, fields
from openerp.tools.translate import _
from openerp import SUPERUSER_ID
import openerp.addons.decimal_precision as dp
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
from datetime import datetime
from dateutil.relativedelta import relativedelta

class purchase_expected_date(osv.osv):
    _name = 'purchase.expected.date'
    _columns = {
        'product_id': fields.many2one('product.product', 'Product'),
        'production_id':  fields.many2one('mrp.production', 'Production Order'),
        'order_id':  fields.many2one('purchase.order', 'Purchase Order'),
        'production_scheduled_date':  fields.date('Production Scheduled Date'),
        'purchase_lead_time':  fields.integer('Product Purchase Lead Time'),
        'company_po_lead_time':  fields.integer('Company Purchase Lead Time'),
        'po_expected_date':  fields.date('Purchase Expected Date')
    }

purchase_expected_date()

class purchase_order(osv.osv):
    _inherit = 'purchase.order'

    def _make_expected_date_data(self, cr, uid, data, order_id, company_id , context=None):
        """ create product wise dictionary"""
        total_list = []
        for rec in data:
            if rec.get('product_id') and rec.get('production_id') and rec.get('move_id'):
                prod_obj = self.pool.get('mrp.production')
                product_obj = self.pool.get('product.product')
                comp_obj = self.pool.get('res.company')
                date_planned = prod_obj.browse(cr, uid, rec['production_id']).date_planned
                po_lead_time = product_obj.browse(cr, uid, rec['product_id']).seller_delay
                comp_lead_time = comp_obj.browse(cr, uid, company_id).po_lead
                scheduled_date = datetime.strptime(date_planned, DEFAULT_SERVER_DATETIME_FORMAT)
                po_expected_date = (scheduled_date - relativedelta(days=(int(po_lead_time) + int(comp_lead_time))) )
                total_list.append(
                                    {
                                    'product_id': int(rec['product_id']),
                                    'production_id': int(rec['production_id']),
                                    'production_scheduled_date': scheduled_date.strftime('%Y-%m-%d'),
                                    'purchase_lead_time':  int(po_lead_time),
                                    'po_expected_date': po_expected_date.strftime('%Y-%m-%d'),
                                    'company_po_lead_time': int(comp_lead_time),
                                    'order_id':order_id
                                     }
                                  )
        return total_list

    def _get_expected_dates_by_products(self, cr, uid, ids,context=None):
        """ Expected date Products wise"""
        res = {}
        context = context or {}
        if not ids: return res
        po_expd_obj = self.pool.get('purchase.expected.date')

        for order in self.browse(cr, uid, ids, context=context):
            unlink_ids = [x.id for x in order.expected_date_by_production_order]
            po_expd_obj.unlink(cr, SUPERUSER_ID, unlink_ids, context=context)

        line_data = []
        for order in self.browse(cr, uid, ids, context=context):
            if order.state not in ('draft'):
                return res
            produced_p_ids = [] 
            for line in order.order_line:
                if not line.product_id: pass
                if line.product_id and line.product_id.supply_method <> 'produce': pass
                produced_p_ids.append(line.product_id.id)

            produced_p_ids = list(set(produced_p_ids))
            if produced_p_ids:
                cr.execute("""
                            SELECT sm.product_id,mpm.production_id,mpm.move_id from mrp_production_move_ids mpm 
                            LEFT JOIN mrp_production mp on (mp.id = mpm.production_id) 
                            LEFT JOIN stock_move sm on (sm.id = mpm.move_id) 
                            WHERE sm.product_id IN %s 
                            AND sm.state not in ('done','cancel') 
                            AND mp.state in ('confirmed') 
                """, (tuple(produced_p_ids),))

                data = cr.dictfetchall()
                line_data = self._make_expected_date_data(cr, uid, data, order.id, order.company_id and order.company_id.id or 1)
            #create date lines on order
            for c_line in line_data:
                po_expd_obj.create(cr, uid, c_line,context=context)
        return True

    _columns = {
        'service_order': fields.boolean('Service Order'),
        'workorder_id':  fields.many2one('mrp.production.workcenter.line', 'Work-Order'),
        'service_delivery_order':  fields.many2one('stock.picking', 'Service Delivery Order'),
        'expected_date_by_production_order': fields.one2many('purchase.expected.date', 'order_id',string='Expected Dates By Production Order',readonly=True)
    }

    def create(self, cr, uid, vals, context=None):
        """ To update Expected Date lines"""
        context = context or {}
        new_id = super(purchase_order,self).create(cr, uid, vals,context=context)
        self._get_expected_dates_by_products(cr, uid, [new_id], context=context)
        return new_id

    def write(self, cr, uid, ids, vals, context=None):
        """ To update Expected Date lines"""
        context = context or {}
        res = super(purchase_order,self).write(cr, uid, ids, vals,context=context)
        if isinstance(ids,int):
            ids = [ids]
        if vals.get('order_line') or vals.get('state'):
            self._get_expected_dates_by_products(cr, uid, ids, context=context)
        return res

    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        default.update({
            'service_order': False,
            'workorder_id': False,
            'service_delivery_order': False,
        })
        return super(purchase_order, self).copy(cr, uid, id, default, context)

    def _check_warehouse_input_stock(self, cr, uid, order):
        """
        -Process
            -Warehouse, Stock location == input location, as it is
            otherwise
                -Warehouse stock location <> Purchase order destination location, as it is,
                or 
                -Warehouse input location <> Purchase order destination location, as it is,

                otherwise
                    -Process flow change
                        -Moves create from Supplier --> Stock input locations, instead of Supplier --> Order destination locations
        """
        stock_location_id = order.warehouse_id.lot_stock_id.id
        input_location_id = order.warehouse_id.lot_input_id.id
        location_id = order.location_id.id
        pass_to_qc = False
        #if (stock_location_id != input_location_id and stock_location_id == location_id) or (stock_location_id != input_location_id and input_location_id == location_id):
        if stock_location_id != input_location_id and input_location_id != location_id:
            location_id = input_location_id
            pass_to_qc = True
        return location_id, pass_to_qc

    def _prepare_order_line_move(self, cr, uid, order, order_line, picking_id, context=None):
        """
        -Process
            -call super method to get dictonary of moves
            -find and check stock input and stock id match or not?
                - If Its match then as it is flow,
                otherwise
                -moves transfer first to QC location(stock input) location then it will be transfered to stock location
        """
        res = super(purchase_order, self)._prepare_order_line_move(cr, uid, order, order_line, picking_id, context=context)
        location_id, pass_to_qc = self._check_warehouse_input_stock(cr, uid, order)
        res.update({'location_dest_id': location_id,'is_qc':pass_to_qc})
        return res

    def _prepare_order_picking(self, cr, uid, order, context=None):
        """
        -Process
            -call super method to get dictonary of moves
            -find and check stock input and stock id match or not?
                - If Its match then as it is flow,
                otherwise
                -Pass to Quality Control or Not ?
        """
        res = super(purchase_order, self)._prepare_order_picking(cr, uid, order, context=context)
        location_id, pass_to_qc = self._check_warehouse_input_stock(cr, uid, order)
        res.update({'pass_to_qc': pass_to_qc,'move_loc_id': order.location_id.id,'qc_loc_id':location_id})
        return res

    def _prepare_inv_line(self, cr, uid, account_id, order_line, context=None):
        """
        -Process
            -call super()
            -pass the purchase qty and Purchase Uom to invoice line
        """
        res = super(purchase_order, self)._prepare_inv_line(cr, uid, account_id, order_line, context=context)
        res.update({'pur_line_qty': order_line.line_qty or 0.0,'pur_line_uom_id': order_line.line_uom_id.id or False})
        return res

    def onchange_warehouse_id(self, cr, uid, ids, warehouse_id):
        """
        -Process
            -update location on create purchase order = stock location instead of input location
        """
        if not warehouse_id:
            return {}
        warehouse = self.pool.get('stock.warehouse').browse(cr, uid, warehouse_id)
        # update lot_stock_id instead of lot_input_id
        return {'value':{'location_id': warehouse.lot_stock_id.id, 'dest_address_id': False}}

    def _create_delivery_picking(self, cr, uid, order, context=None):
        """
        Process
            -Create Delivery Picking for outsource
        Return
            -Dictionary of picking
        """
        pick_name = self.pool.get('ir.sequence').get(cr, uid, 'stock.picking.out')
        production = order.workorder_id.production_id
        return {
            'name': pick_name,
            'origin': production.name,
            'date': time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
            'type': 'out',
            'state': 'draft',
            'partner_id': order.partner_id.id,
            'note': order.notes,
            'invoice_state': 'none',
            'company_id': order.company_id.id,
            'service_order':True,
            'workorder_id': order.workorder_id.id,
        }

    def _create_delivery_move(self, cr , uid, order, deliver_id, context=None):
        """
        Process
            -Create move for outsource
                From : Production Location
                To : Supplier Location
        Return
            -Dictionary of move
        """
        context = context or {}
        if not order.workorder_id:
            raise osv.except_osv(_('Warning!'), _('Can you check again, is this service order??!'))
        production = order.workorder_id.production_id

        #Delivery Order Locations
        source_location_id = production.product_id.property_stock_production.id
        dest_location_id = order.partner_id.property_stock_supplier.id
        list_data = []
        for l in order.order_line:
            if l.product_id and l.product_id.type <> 'service':
                list_data.append(
                                    {
                                        'name': l.product_id.name,
                                        'picking_id': deliver_id,
                                        'product_id': l.product_id.id,
                                        'date': time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                                        'date_expected': time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                                        'product_qty': l.product_qty or 0.0,
                                        'product_uom': l.product_id.uom_id.id,
                                        'product_uos_qty': l.product_qty or 0.0,
                                        'product_uos': l.product_id.uom_id.id,
                                        'partner_id': order.partner_id.id,
                                        'location_id': source_location_id,
                                        'location_dest_id': dest_location_id,
                                        'tracking_id': False,
                                        'state': 'draft',
                                        'company_id': production.company_id.id,
                                        'price_unit': l.product_id.standard_price or 0.0
                                    }
                                 )
        return list_data

    def action_picking_create(self, cr, uid, ids, context=None):
        """
        -Process
            -super call()
            -if service order then at the time of confirmation , it will generate Delivery order from production.
        """
        out_pick_obj = self.pool.get('stock.picking')
        move_obj = self.pool.get('stock.move')
        wf_service = netsvc.LocalService("workflow")
        res = super(purchase_order,self).action_picking_create(cr, uid, ids, context=context)
        for order in self.browse(cr, uid, ids):
            if order.service_order:
                # Create Delivery Order
                delivery_order_id = out_pick_obj.create(cr, uid, self._create_delivery_picking(cr, uid, order, context=context), context=context)
                # Create Move
                move_lines = self._create_delivery_move(cr, uid, order, delivery_order_id, context=context)
                for move in move_lines:
                    move_obj.create(cr, uid, move, context=context)

                #Picking Directly Done
                wf_service.trg_validate(uid, 'stock.picking', delivery_order_id, 'button_confirm', cr)
                out_pick_obj.action_move(cr, uid, [delivery_order_id], context)
                wf_service.trg_validate(uid, 'stock.picking', delivery_order_id, 'button_done', cr)

                order.write({'service_delivery_order': delivery_order_id})
                
        return res

purchase_order()

class purchase_order_line(osv.osv):
    _inherit = 'purchase.order.line'

    def _get_p_uom_id(self, cr, uid, *args):
        cr.execute('select id from product_uom order by id limit 1')
        res = cr.fetchone()
        return res and res[0] or False

    _columns = {
        'product_qty': fields.float('Issue Quantity', digits_compute=dp.get_precision('Product Unit of Measure'), required=True),
        'line_qty': fields.float('Purchase Quantity'),
        'line_uom_id':  fields.many2one('product.uom', 'Purchase UoM'),
        'consignment_variation': fields.char('Variation(±)'),
        'process_move_id':fields.many2one('stock.moves.workorder', 'Process Line'),
    }

    _defaults = {
        'line_uom_id':_get_p_uom_id,
        'consignment_variation':'0.0'
    }

    def onchange_product_id(self, cr, uid, ids, pricelist_id, product_id, qty, uom_id,
            partner_id, date_order=False, fiscal_position_id=False, date_planned=False,
            name=False, price_unit=False, context=None):
        """
        onchange handler of product_id.
        """
        prod_obj = self.pool.get('product.product')
        res = super(purchase_order_line, self).onchange_product_id(cr, uid, ids, pricelist_id, product_id, qty, uom_id,
            partner_id, date_order=date_order, fiscal_position_id=fiscal_position_id, date_planned=date_planned,
            name=name, price_unit=price_unit, context=context)
        if product_id:
            p = prod_obj.browse(cr, uid, product_id)
            p_qty = res['value'].get('product_qty', 0.0)
            res['value'].update({
                        'line_qty': p_qty * p.p_coefficient,
                        'line_uom_id':p.p_uom_id.id
                        })
        return res

    def create(self, cr, uid, vals , context=None):
        """
            Process
                -Future use
        """
        return super(purchase_order_line, self).create(cr, uid, vals, context=context)


    def add_variations(self, cr, uid, ids , context=None):
        """
            Process
                -call wizard to add variation on line
        """
        context = context or {}
        models_data = self.pool.get('ir.model.data')
        # Get consume wizard
        dummy, form_view = models_data.get_object_reference(cr, uid, 'l10n_in_mrp_subcontract', 'view_consignment_variation_po')
        current = self.browse(cr, uid, ids[0], context=context)
        context.update({
                        'uom': current.line_uom_id.name,
                        })
        return {
            'name': _('Add Consignment Variation'),
            'view_type': 'form',
            'view_mode': 'form',
            'context':context,
            'res_model': 'consignment.variation.po',
            'views': [(form_view or False, 'form')],
            'type': 'ir.actions.act_window',
            'target':'new'
        }


purchase_order_line()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
