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

{
    'name' : 'Maize Purchase',
    'version' : '0.1',
    'author' : 'OpenERP S.A.',
    'sequence': 110,
    'category': 'Maize Purchase Management',
    'website' : 'http://www.openerp.com',
    'summary' : 'Managing Purchase',
    'description' : """
This module inherits the base product module which maintains some product history data like last purchase order number, last supplier rate etc.
================================================================================================================================================================ 
""",
    'depends' : ['maize_product','maize_partner','maize_account'],
    
    'data' : [
        'maize_tax_data.xml',
        'code_data.xml',
        'purchase_dispatch_data.xml',
        'email_template_data.xml',
        'security/ir.model.access.csv',
    ],
    'update_xml' : [
        'wizard/comparison_report_view.xml',
        'wizard/inventory_control_view.xml',
        'wizard/update_excise_wizard.xml',
        'wizard/stock_move_split_view.xml',
        'wizard/department_excise_percentage_view.xml',
        
        'maize_purchase_view.xml',
        
#         'maize_report.xml',
#         'report/indent_report_view.xml',
#         'report/indent_purchase_report_view.xml',
#         'report/indentor_wise_indent_report_view.xml',
#         'report/project_cost_report_view.xml',
#         'report/product_major_group_stock_view.xml',
#         'report/purchase_order_information_view.xml',
#         'report/inputs_consumed_by_department_view.xml',
#         'report/format_rg_23a_part1_view.xml',
#         'report/indentorwise_purchase_report_view.xml'
    ],

    'demo': [],

    'installable' : True,
    'application' : True,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
