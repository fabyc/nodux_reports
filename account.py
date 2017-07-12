# -*- coding: utf-8 -*-

#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from decimal import Decimal
from datetime import date
import operator
from sql.aggregate import Sum
from itertools import izip, groupby
from collections import OrderedDict
from trytond.model import ModelView, ModelSQL, ModelSingleton, fields
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.report import Report
from trytond.pyson import Eval, PYSONEncoder
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta
from trytond.modules.company import CompanyReport
import pytz
from datetime import datetime,timedelta
import time

__all__ = ['PrintCloseCashStart','PrintCloseCash', 'CloseCash',
'PrintSalesmanStart', 'PrintSalesman', 'ReportSalesman', 'PrintMoveAllStart',
'PrintMoveAll', 'ReportMoveAll', 'PrintAccountReceivable', 'AccountReceivable',
'ReportAccountReceivable', 'CuboVenta','CuboVentaLineas', 'CuboVentaReport',
'PrintWithholdingOutStart', 'PrintWithholdingOut', 'ReportWithholdingOut']
__metaclass__ = PoolMeta

TYPES = [
    ('',''),
    ('goods', 'Goods'),
    ('service', 'Service'),
    ]

TYPE_WITHHOLDING = [
    ('',''),
    ('fuente', 'Fuente'),
    ('iva', 'Iva'),
    ]


class PrintCloseCashStart(ModelView):
    'Print Close Cash'
    __name__ = 'nodux_reports.print_close_cash.start'
    company = fields.Many2One('company.company', 'Company', required=True)
    date = fields.Date("Date", help="Seleccione la fecha de la cual desea imprimir el reporte")
    general = fields.Boolean('Reporte General')
    usuario = fields.Many2One('res.user', 'Usuario', states={
        'invisible':Eval('general', True),
    })
    punto_venta = fields.Many2One('sale.shop', 'Local', states={
        'invisible': Eval('general', True),
    })

    @staticmethod
    def default_general():
        return True

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_date():
        date = Pool().get('ir.date')
        date = date.today()
        return date


class PrintCloseCash(Wizard):
    'Print Trial Balance Detailed'
    __name__ = 'nodux_reports.print_close_cash'
    start = StateView('nodux_reports.print_close_cash.start',
        'nodux_reports.print_close_cash_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Print', 'print_', 'tryton-print', default=True),
            ])
    print_ = StateAction('nodux_reports.report_close_cash')

    def do_print_(self, action):
        if self.start.general == True:
            data = {
                'company': self.start.company.id,
                'date' : self.start.date,
                'general' : True
                }
        else:
            if self.start.usuario:
                data = {
                    'company': self.start.company.id,
                    'date' : self.start.date,
                    'usuario' : self.start.usuario.id,
                    'general' : False
                    }
            elif self.start.punto_venta:
                data = {
                    'company': self.start.company.id,
                    'date' : self.start.date,
                    'punto_venta' : self.start.punto_venta.id,
                    'general' : False
                    }

        return action, data

    def transition_print_(self):
        return 'end'

class CloseCash(Report):
    __name__ = 'nodux_reports.close_cash'

    @classmethod
    def parse(cls, report, objects, data, localcontext):
        pool = Pool()
        User = pool.get('res.user')
        user = User(Transaction().user)
        Date = Pool().get('ir.date')
        Company = pool.get('company.company')
        Move = pool.get('account.move')
        MoveLine = pool.get ('account.move.line')
        Statement = pool.get('account.statement')
        StatementLine = pool.get('account.statement.line')
        Invoice = pool.get('account.invoice')
        module = None
        module_in_w = None
        module_out_w = None
        Module = pool.get('ir.module.module')
        module = Module.search([('name', '=', 'nodux_account_voucher_ec'), ('state', '=', 'installed')])
        module_in_w = Module.search([('name', '=', 'nodux_account_withholding_in_ec'), ('state', '=', 'installed')])
        module_out_w = Module.search([('name', '=', 'nodux_account_withholding_out_ec'), ('state', '=', 'installed')])
        module_advanced = Module.search([('name', '=', 'nodux_sale_payment_advanced_payment'), ('state', '=', 'installed')])

        if module:
            Voucher = pool.get('account.voucher')
        if module_in_w:
            WithholdingIn = pool.get('account.withholding')
        if module_out_w:
            WithholdingOut = pool.get('account.withholding')

        Invoice = pool.get('account.invoice')
        Sale = pool.get('sale.sale')
        fecha = data['date']
        general = data['general']
        company = Company(data['company'])
        ventas_efectivo =  Decimal(0.0)
        ventas_cheque_efectivo= Decimal(0.0)
        total_contado= Decimal(0.0)
        ventas_credito = Decimal(0.0)
        alcance_efectivo_credito = Decimal(0.0)
        notas_entrega = Decimal(0.0)
        total_credito = Decimal(0.0)
        c_a_efectivo = Decimal(0.0)
        c_a_retencion = Decimal(0.0)
        c_a_retencion_iva = Decimal(0.0)
        c_a_deposito = Decimal(0.0)
        total_recaudaciones = Decimal(0.0)
        efectivo_egreso = Decimal(0.0)
        total_egreso = Decimal(0.0)
        anticipos= Decimal(0.0)
        devolucion_retencion = Decimal(0.0)
        total_flujo = Decimal(0.0)
        total_caja = Decimal(0.0)
        total_ventas = total_contado + total_credito
        subtotal_ventas = Decimal(0.0)
        descuento = Decimal(0.0)
        subtotal_0 = Decimal(0.0)
        subtotal_12 = Decimal(0.0)
        subtotal_14 = Decimal(0.0)
        iva = Decimal(0.0)
        ventas_acumulativo = Decimal(0.0)
        ventas_depositos = Decimal(0.0)
        ventas_tarjeta_credito = Decimal(0.0)
        alcance_cheques_credito = Decimal(0.0)
        anticipos_utilizados = Decimal(0.0)
        c_a_cheques = Decimal(0.0)
        c_a_efectivo = Decimal(0.0)
        c_a_deposito = Decimal(0.0)
        c_a_anticipos = Decimal(0.0)
        c_a_tc = Decimal(0.0)


        if general == True:
            if company.timezone:
                timezone = pytz.timezone(company.timezone)
                dt = datetime.now()
                hora = datetime.astimezone(dt.replace(tzinfo=pytz.utc), timezone)

            monto = Decimal(0.0)
            move = Move.search([('post_date', '=', fecha)])
            voucher = None
            withholding = None
            #movimiento de venta -> credito contado, efectivo, cheque
            for m in move:
                invoice = None
                moveline = MoveLine.search([('move', '=', m.id), ('maturity_date', '!=', None), ('debit', '!=', Decimal(0.0))])
                o = m.origin
                referencia = str(o).split(",")
                if referencia[0] == 'account.voucher':
                    voucher = m.origin
                elif referencia[0] == 'account.invoice':
                    invoice = m.origin
                elif referencia[0] == 'account.withholding':
                    withholding = m.origin

                if voucher:
                    VoucherLine = pool.get('account.voucher.line')
                    VoucherPayMode = pool.get('account.voucher.line.paymode')
                    voucher_line = VoucherLine.search([('voucher','=', voucher.id)])
                    voucher_pay_mode = VoucherPayMode.search([('voucher','=', voucher.id)])

                    if voucher.voucher_type == 'receipt':
                        for v_p in voucher_pay_mode:
                            pago = v_p.pay_mode.name
                            pago = pago.lower()

                            if 'cheque' in pago:
                                for v_l in voucher_line:
                                    c_a_deposito = v_l.amount
                            if 'efectivo' in pago:
                                for v_l in voucher_line:
                                    alcance_efectivo_credito = v_l.amount
                                    #c_a_efectivo = v_l.amount
                            if 'tarjeta' in pago:
                                for v_l in voucher_line:
                                    monto = v_l.amount
                #descuentos
                if invoice:
                    sale = None
                    if invoice.type == 'out_invoice':
                        sales = Sale.search([('description', '=', invoice.description)])
                        for s in sales:
                            sale=s
                        if sale:
                            for line in sale.lines:
                                descuento_parcial = Decimal(line.product.template.list_price - line.unit_price)
                                if descuento_parcial > 0:
                                    descuento = descuento + descuento_parcial
                                else:
                                    descuento = Decimal(0.00)
                                if line.taxes:
                                    for t in line.taxes:
                                        if str('{:.0f}'.format(t.rate*100)) == '12':
                                            subtotal_12= subtotal_12 + (line.amount)
                                        if str('{:.0f}'.format(t.rate*100)) == '14':
                                            subtotal_14= subtotal_14 + (line.amount)
                                        if str('{:.0f}'.format(t.rate*100)) == '0':
                                            subtotal_0= subtotal_0 + (line.amount)
                                    subtotal_ventas = (subtotal_12 + subtotal_0 + subtotal_14)-descuento
                #retencion cliente
                """
                if withholding:
                    if withholding.type == 'out_withholding':
                        for w_t in withholding.taxes:
                            devolucion_retencion += w_t.amount
                            if devolucion_retencion < Decimal(0.0):
                                devolucion_retencion = devolucion_retencion * (-1)
                """
            if module:
                vouchers = Voucher.search([('date', '=', fecha)])
                for voucher in vouchers:
                    VoucherLine = pool.get('account.voucher.line')
                    VoucherPayMode = pool.get('account.voucher.line.paymode')
                    voucher_line = VoucherLine.search([('voucher','=', voucher.id)])
                    voucher_pay_mode = VoucherPayMode.search([('voucher','=', voucher.id)])
                    if voucher.voucher_type == 'payment':
                        for v_p_p in voucher_pay_mode:
                            pago = v_p_p.pay_mode.name
                            pago = pago.lower()
                            if 'efectivo' in pago:
                                for v_l_p in voucher_line:
                                    efectivo_egreso += v_l_p.amount

            #retencion proveedor
            """
            if module_in_w:
                withholding_ins = WithholdingIn.search([('withholding_date', '=', fecha), ('type', '=', 'in_withholding')])
                for w_i in withholding_ins:
                    for w_i_t in w_i.taxes:
                        c_a_retencion += w_i_t.amount
                if c_a_retencion < Decimal(0.0):
                    c_a_retencion = c_a_retencion *(-1)
            """
            #retencion de cliente
            if module_out_w:
                withholding_outs = WithholdingOut.search([('withholding_date', '=', fecha), ('type', '=', 'out_withholding')])
                for w_o in withholding_outs:
                    if w_o.efectivo == True:
                        devolucion_retencion += w_o.total_amount2
                    else:
                        for tax in w_o.taxes:
                            if tax.tipo == 'RENTA':
                                c_a_retencion += tax.amount
                            elif tax.tipo == 'IVA':
                                c_a_retencion_iva += tax.amoun
                if devolucion_retencion < Decimal(0.0):
                    devolucion_retencion = devolucion_retencion * (-1)
                if c_a_retencion < Decimal(0.0):
                    c_a_retencion = c_a_retencion * (-1)
                if c_a_retencion_iva < Decimal(0.0):
                    c_a_retencion_iva = c_a_retencion_iva * (-1)
            #calculo de anticipos
            anticipo = None
            if module:
                Anticipos = pool.get('account.voucher.line.credits')
                anticipo = Anticipos.search([('date', '=', fecha)])
            if anticipo:
                for a in anticipo:
                    anticipos += a.amount_original

            #ventas contado en efectivo
            statements = Statement.search([('date', '=', fecha), ('tipo_pago', '=','efectivo')])
            #statement_line = StatementLine.search([('date', '=', fecha)])
            if statements:
                for statement in statements:
                    for line in statement.lines:
                        if line.sale.acumulativo == True:
                            ventas_acumulativo += line.amount
                        else:
                            ventas_efectivo += line.amount

            #ventas cheque contado
            statements_ch = Statement.search([('date', '=', fecha), ('tipo_pago','=', 'cheque')])
            #statement_line = StatementLine.search([('date', '=', fecha)])
            if statements_ch:
                for statement in statements_ch:
                    for line in statement.lines:
                        if line.sale.acumulativo == True:
                            ventas_acumulativo += line.amount
                        else:
                            ventas_cheque_efectivo += line.amount

            #ventas_depositos
            statements_d = Statement.search([('date', '=', fecha), ('tipo_pago', '=', 'deposito')])
            #statement_line = StatementLine.search([('date', '=', fecha)])
            if statements_d:
                for statement in statements_d:
                    for line in statement.lines:
                        if line.sale.acumulativo == True:
                            ventas_acumulativo += line.amount
                        else:
                            ventas_depositos += line.amount

            #ventas_tarjeta_credito
            statements_tc = Statement.search([('date', '=', fecha), ('tipo_pago', '=', 'tarjeta')])
            #statement_line = StatementLine.search([('date', '=', fecha)])
            if statements_tc:
                for statement in statements_tc:
                    for line in statement.lines:
                        if line.sale.acumulativo == True:
                            ventas_acumulativo += line.amount
                        else:
                            ventas_tarjeta_credito += line.amount

            #ventas a credito
            sales = Sale.search([('pago','=', 'Credito'), ('sale_date', '=',fecha)])
            for sale in sales:
                ventas_credito += sale.total_amount

            #alcance_efectivo_credito alcance_cheques_credito

            #anticipos_utilizados
            if module_advanced:
                moves_advanced = Move.search([('date', '=', fecha)])
                for move_advanced in moves_advanced:
                    if 'Anticipo' in move_advanced.origin:
                        for line in move_advanced.lines:
                            if 'used' in line.description:
                                anticipos_utilizados += line.credit
            #detalle de cxc
            if module:
                vouchers = Voucher.search([('voucher_type', '=', 'receipt'), ('date', '=', fecha)])
                for voucher in vouchers:
                    for line in voucher.pay_lines:
                        if 'efec' in str(line.pay_mode.name).lower():
                            c_a_efectivo += line.pay_amount
                        if 'che' in str(line.pay_mode.name).lower():
                            c_a_cheques += line.pay_amount
                        if 'dep' in str(line.pay_mode.name).lower():
                            c_a_deposito += line.pay_amount
                        if 'tar' in str(line.pay_mode.name).lower():
                            c_a_tc += line.pay_amount

            #pendiente c_a_anticipos

            """
            invoices = Invoice.search([('invoice_date', '=', fecha)])
            for i in invoices:
                moveslines_c = MoveLine.search([('move', '=', i.move),('maturity_date', '!=', None), ('debit', '!=', Decimal(0.0))])
                for mlc in moveslines_c:
                    if mlc.maturity_date > fecha:
                        ventas_credito += mlc.debit
                        description = mlc.description
                for slc in statement_line:
                    if slc.invoice.id == i.id:
                        alcance_efectivo_credito += slc.amount
            """
        else:
            if data['usuario']:
                usuario = data['usuario']
            else:
                usuario = ""
                if data['punto_venta']:
                    punto_venta = data['punto_venta']
                else:
                    punto_venta = ""

            if usuario != "":
                if company.timezone:
                    timezone = pytz.timezone(company.timezone)
                    dt = datetime.now()
                    hora = datetime.astimezone(dt.replace(tzinfo=pytz.utc), timezone)

                monto = Decimal(0.0)
                move = Move.search([('post_date', '=', fecha), ('create_uid', '=', usuario)])
                voucher = None
                withholding = None
                #movimiento de venta -> credito contado, efectivo, cheque
                for m in move:
                    invoice = None
                    moveline = MoveLine.search([('move', '=', m.id), ('maturity_date', '!=', None), ('debit', '!=', Decimal(0.0))])
                    o = m.origin
                    referencia = str(o).split(",")
                    if referencia[0] == 'account.voucher':
                        voucher = m.origin
                    elif referencia[0] == 'account.invoice':
                        invoice = m.origin
                    elif referencia[0] == 'account.withholding':
                        withholding = m.origin

                    if voucher:
                        VoucherLine = pool.get('account.voucher.line')
                        VoucherPayMode = pool.get('account.voucher.line.paymode')
                        voucher_line = VoucherLine.search([('voucher','=', voucher.id)])
                        voucher_pay_mode = VoucherPayMode.search([('voucher','=', voucher.id)])

                        if voucher.voucher_type == 'receipt':
                            for v_p in voucher_pay_mode:
                                pago = v_p.pay_mode.name
                                pago = pago.lower()

                                if 'cheque' in pago:
                                    for v_l in voucher_line:
                                        c_a_deposito = v_l.amount
                                if 'efectivo' in pago:
                                    for v_l in voucher_line:
                                        alcance_efectivo_credito = v_l.amount
                                        #c_a_efectivo = v_l.amount
                                if 'tarjeta' in pago:
                                    for v_l in voucher_line:
                                        monto = v_l.amount
                    #descuentos
                    if invoice:
                        sale = None
                        if invoice.type == 'out_invoice':
                            sales = Sale.search([('description', '=', invoice.description)])
                            for s in sales:
                                sale=s
                            if sale:
                                for line in sale.lines:
                                    descuento_parcial = Decimal(line.product.template.list_price - line.unit_price)
                                    if descuento_parcial > 0:
                                        descuento = descuento + descuento_parcial
                                    else:
                                        descuento = Decimal(0.00)
                                    if line.taxes:
                                        for t in line.taxes:
                                            if str('{:.0f}'.format(t.rate*100)) == '12':
                                                subtotal_12= subtotal_12 + (line.amount)
                                            if str('{:.0f}'.format(t.rate*100)) == '14':
                                                subtotal_14= subtotal_14 + (line.amount)
                                            if str('{:.0f}'.format(t.rate*100)) == '0':
                                                subtotal_0 = subtotal_0 + (line.amount)
                                        subtotal_ventas = (subtotal_12 + subtotal_0 + subtotal_14)-descuento

                if module:
                    vouchers = Voucher.search([('date', '=', fecha), ('write_uid', '=', usuario)])
                    for voucher in vouchers:
                        VoucherLine = pool.get('account.voucher.line')
                        VoucherPayMode = pool.get('account.voucher.line.paymode')
                        voucher_line = VoucherLine.search([('voucher','=', voucher.id)])
                        voucher_pay_mode = VoucherPayMode.search([('voucher','=', voucher.id)])
                        if voucher.voucher_type == 'payment':
                            for v_p_p in voucher_pay_mode:
                                pago = v_p_p.pay_mode.name
                                pago = pago.lower()
                                if 'efectivo' in pago:
                                    for v_l_p in voucher_line:
                                        efectivo_egreso += v_l_p.amount

                #retencion proveedor
                if module_in_w:
                    withholding_ins = WithholdingIn.search([('withholding_date', '=', fecha), ('type', '=', 'in_withholding'), ('write_uid', '=', usuario)])
                    for w_i in withholding_ins:
                        for w_i_t in w_i.taxes:
                            c_a_retencion += w_i_t.amount
                    if c_a_retencion < Decimal(0.0):
                        c_a_retencion = c_a_retencion * (-1)
                #retencion de cliente
                if module_out_w:
                    withholding_outs = WithholdingOut.search([('withholding_date', '=', fecha), ('type', '=', 'out_withholding'), ('write_uid', '=', usuario)])
                    for w_o in withholding_outs:
                        for w_o_t in w_o.taxes:
                            devolucion_retencion += w_o_t.amount
                    if devolucion_retencion < Decimal(0.0):
                        devolucion_retencion = devolucion_retencion * (-1)
                #calculo de anticipos
                anticipo = None
                if module:
                    Anticipos = pool.get('account.voucher.line.credits')
                    anticipo = Anticipos.search([('date', '=', fecha), ('write_uid', '=', usuario)])
                if anticipo:
                    for a in anticipo:
                        anticipos += a.amount_original

                #ventas contado en efectivo
                statements = Statement.search([('date', '=', fecha), ('tipo_pago', 'efectivo')])
                #statement_line = StatementLine.search([('date', '=', fecha)])
                if statements:
                    for statement in statements:
                        for line in statement.lines:
                            if line.sale.acumulativo == True:
                                ventas_acumulativo += line.amount
                            else:
                                ventas_efectivo += line.amount

                #ventas cheque contado
                statements_ch = Statement.search([('date', '=', fecha), ('tipo_pago', 'cheque')])
                #statement_line = StatementLine.search([('date', '=', fecha)])
                if statements_ch:
                    for statement in statements_ch:
                        for line in statement.lines:
                            if line.sale.acumulativo == True:
                                ventas_acumulativo += line.amount
                            else:
                                ventas_cheque_efectivo += line.amount

                #ventas_depositos
                statements_d = Statement.search([('date', '=', fecha), ('tipo_pago', 'deposito')])
                #statement_line = StatementLine.search([('date', '=', fecha)])
                if statements_d:
                    for statement in statements_d:
                        for line in statement.lines:
                            if line.sale.acumulativo == True:
                                ventas_acumulativo += line.amount
                            else:
                                ventas_depositos += line.amount

                #ventas_tarjeta_credito
                statements_tc = Statement.search([('date', '=', fecha), ('tipo_pago', 'tarjeta')])
                #statement_line = StatementLine.search([('date', '=', fecha)])
                if statements_tc:
                    for statement in statements_tc:
                        for line in statement.lines:
                            if line.sale.acumulativo == True:
                                ventas_acumulativo += line.amount
                            else:
                                ventas_tarjeta_credito += line.amount

                #ventas a credito
                sales = Sale.search([('pago', 'Credito'), ('sale_date', fecha)])
                for sale in sales:
                    ventas_credito += sale.total_amount

        if ventas_credito > 0 :
            ventas_credito = ventas_credito - alcance_efectivo_credito
        else:
            ventas_credito = ventas_credito
        ventas_efectivo = ventas_efectivo - alcance_efectivo_credito
        total_contado = ventas_efectivo + ventas_cheque_efectivo + ventas_acumulativo
        total_credito = ventas_credito - anticipos_utilizados
        total_recaudaciones = c_a_efectivo + c_a_deposito
        total_egreso = efectivo_egreso
        total_flujo = (total_contado + c_a_efectivo + alcance_efectivo_credito) - (anticipos+devolucion_retencion+total_egreso)
        total_caja = anticipos + total_flujo

        localcontext['company'] = company
        localcontext['fecha'] = fecha.strftime('%d/%m/%Y')
        localcontext['fecha_fin'] = fecha.strftime('%d/%m/%Y')
        localcontext['hora'] = hora.strftime('%H:%M:%S')
        localcontext['fecha_im'] = hora.strftime('%d/%m/%Y')
        localcontext['ventas_efectivo']= ventas_efectivo
        #pendiente localcontext['alcance_efectivo_voucher'] = alcance_efectivo_voucher
        localcontext['ventas_depositos'] = ventas_depositos
        localcontext['ventas_cheque_efectivo'] = ventas_cheque_efectivo
        #pendiente localcontext['anticipos_ventas_cheque_efectivo'] = anticipos_ventas_cheque_efectivo
        localcontext['ventas_tarjeta_credito'] = ventas_tarjeta_credito
        localcontext['ventas_acumulativo']= ventas_acumulativo
        localcontext['total_contado']= total_contado
        localcontext['ventas_credito']= ventas_credito
        #pendientelocalcontext['alcance_efectivo_credito']= alcance_efectivo_credito
        #pendientelocalcontext['alcance_cheques_credito']= alcance_cheques_credito
        localcontext['anticipos_utilizados'] = anticipos_utilizados
        localcontext['total_credito']= total_credito
        localcontext['c_a_cheques']= c_a_cheques
        localcontext['c_a_efectivo']= c_a_efectivo
        #pendientelocalcontext['c_a_notas_debito']= c_a_notas_debito
        #pendientelocalcontext['c_a_notas_credito']= c_a_notas_credito
        localcontext['c_a_retencion_iva'] = c_a_retencion_iva
        localcontext['c_a_retencion'] = c_a_retencion
        localcontext['c_a_deposito']=c_a_deposito
        localcontext['c_a_anticipos'] = c_a_anticipos
        localcontext['c_a_tc'] = c_a_tc
        localcontext['total_recaudaciones']=total_recaudaciones
        localcontext['efectivo_egreso']=efectivo_egreso
        localcontext['total_egreso']=total_egreso
        #localcontext['efectivo_ingreso']=efectivo_ingreso
        #localcontext['deposito_ingreso']=deposito_ingreso
        #localcontext['total_comp_ingreso']=total_comp_ingreso

        localcontext['anticipos']= anticipos
        localcontext['devolucion_retencion']= devolucion_retencion
        localcontext['total_flujo']= total_flujo
        localcontext['total_caja']= total_caja
        localcontext['total_ventas']= total_contado + total_credito
        localcontext['subtotal_ventas']= subtotal_ventas
        localcontext['descuentos']=descuento
        #localcontext['descuentos_efectivos'] = descuentos_efectivos
        #localcontext['descuentos_unitarios'] = descuentos_unitarios
        localcontext['subtotal_0']=subtotal_0
        localcontext['subtotal_12']=subtotal_12
        localcontext['subtotal_14']=subtotal_14
        localcontext['iva']= (subtotal_12 * 12)/100
        localcontext['iva14']= (subtotal_14 * 14)/100

        return super(CloseCash, cls).parse(report, objects, data, localcontext)


class PrintSalesmanStart(ModelView):
    'Print Salesman Start'
    __name__ = 'nodux_reports.print_salesman.start'
    company = fields.Many2One('company.company', 'Company', required=True)
    date_start = fields.Date("Fecha Inicio", required= True)
    date_end = fields.Date("Fecha Fin", required= True)
    vendedor = fields.Many2One('company.employee', 'Vendedor', required = True)

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_date_start():
        date = Pool().get('ir.date')
        date = date.today()
        return date

    @staticmethod
    def default_date_end():
        date = Pool().get('ir.date')
        date = date.today()
        return date

#crear referencias
class PrintSalesman(Wizard):
    'Print Salesman'
    __name__ = 'nodux_reports.print_salesman'
    start = StateView('nodux_reports.print_salesman.start',
        'nodux_reports.print_salesman_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Print', 'print_', 'tryton-print', default=True),
            ])
    print_ = StateAction('nodux_reports.report_salesman')

    def do_print_(self, action):
        data = {
            'company': self.start.company.id,
            'date_start' : self.start.date_start,
            'date_end' : self.start.date_end,
            'vendedor' : self.start.vendedor.id
            }
        return action, data

    def transition_print_(self):
        return 'end'

class ReportSalesman(Report):
    __name__ = 'nodux_reports.report_salesman'

    @classmethod
    def parse(cls, report, objects, data, localcontext):
        pool = Pool()
        User = pool.get('res.user')
        user = User(Transaction().user)
        Date = pool.get('ir.date')
        Vendedor = pool.get('company.employee')
        Company = pool.get('company.company')
        Move = pool.get('account.move')
        MoveLine = pool.get ('account.move.line')
        StatementLine = pool.get('account.statement.line')
        Invoice = pool.get('account.invoice')
        Sale = pool.get('sale.sale')
        fecha = data['date_start']
        fecha_fin = data['date_end']
        company = Company(data['company'])
        vendedor = Vendedor(data['vendedor'])
        listas = []
        listas_total = []
        ventas_efectivo =  Decimal(0.0)
        total_iva =  Decimal(0.0)
        subtotal_total =  Decimal(0.0)
        subtotal12 = Decimal(0.0)
        subtotal0 = Decimal(0.0)
        term_pago = []
        term_pago_total = []

        sales = Sale.search([('sale_date', '>=', fecha), ('sale_date', '<=', fecha_fin), ('employee', '=', vendedor), ('devolucion', '=', False)])

        if sales:
            for s in sales:
                if s.price_list in listas:
                    pass
                elif s.price_list == None:
                    pass
                else:
                    listas.append(s.price_list)

                if s.payment_term in term_pago:
                    pass
                else:
                    term_pago.append(s.payment_term)

                if s.total_amount > Decimal(0.0):
                    ventas_efectivo += s.total_amount
                    total_iva += s.tax_amount
                    subtotal_total += s.untaxed_amount
                    for line in s.lines:
                        if  line.taxes:
                            for t in line.taxes:
                                if str('{:.0f}'.format(t.rate*100)) == '12':
                                    subtotal12 += (line.amount)
                    for line in s.lines:
                        if  line.taxes:
                            for t in line.taxes:
                                if str('{:.0f}'.format(t.rate*100)) == '0':
                                    subtotal0 += (line.amount)

        for l in listas:
            total_lista_precio = Decimal(0.0)
            lineas_listas = {}
            for s in sales:
                if s.price_list == l:
                    total_lista_precio += s.untaxed_amount
            lineas_listas['lista'] = l.name
            lineas_listas['total'] = total_lista_precio
            listas_total.append(lineas_listas)

        for t in term_pago:
            total_term_pago = Decimal(0.0)
            lineas_pagos = {}
            for s in sales:
                if s.payment_term == t:
                    total_term_pago += s.untaxed_amount
            lineas_pagos['pago'] = t.name
            lineas_pagos['total'] = total_term_pago
            term_pago_total.append(lineas_pagos)

        if company.timezone:
            timezone = pytz.timezone(company.timezone)
            dt = datetime.now()
            hora = datetime.astimezone(dt.replace(tzinfo=pytz.utc), timezone)

        localcontext['company'] = company
        localcontext['vendedor'] = vendedor
        localcontext['fecha'] = fecha.strftime('%d/%m/%Y')
        localcontext['fecha_fin'] = fecha_fin.strftime('%d/%m/%Y')
        localcontext['hora'] = hora.strftime('%H:%M:%S')
        localcontext['fecha_im'] = hora.strftime('%d/%m/%Y')
        localcontext['total_ventas'] = ventas_efectivo
        localcontext['sales'] = sales
        localcontext['listas_total'] = listas_total
        localcontext['total_iva'] = total_iva
        localcontext['subtotal_total'] = subtotal_total
        localcontext['term_pago_total'] = term_pago_total
        localcontext['subtotal12'] = subtotal12
        localcontext['subtotal0'] = subtotal0

        return super(ReportSalesman, cls).parse(report, objects, data, localcontext)

class PrintMoveAllStart(ModelView):
    'Print Move All Start'
    __name__ = 'nodux_reports.print_move_all.start'
    company = fields.Many2One('company.company', 'Company', required=True)
    date_start = fields.Date("Fecha Inicio", required= True)
    date_end = fields.Date("Fecha Fin", required= True)

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_date_start():
        date = Pool().get('ir.date')
        date = date.today()
        return date

    @staticmethod
    def default_date_end():
        date = Pool().get('ir.date')
        date = date.today()
        return date

#crear referencias
class PrintMoveAll(Wizard):
    'Print Move All'
    __name__ = 'nodux_reports.print_move_all'
    start = StateView('nodux_reports.print_move_all.start',
        'nodux_reports.print_move_all_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Print', 'print_', 'tryton-print', default=True),
            ])
    print_ = StateAction('nodux_reports.report_move_all')

    def do_print_(self, action):
        data = {
            'company': self.start.company.id,
            'date_start' : self.start.date_start,
            'date_end' : self.start.date_end,
        }
        return action, data

    def transition_print_(self):
        return 'end'

class ReportMoveAll(Report):
    __name__ = 'nodux_reports.report_move_all'

    @classmethod
    def parse(cls, report, objects, data, localcontext):
        pool = Pool()
        User = pool.get('res.user')
        user = User(Transaction().user)
        Date = pool.get('ir.date')
        Vendedor = pool.get('company.employee')
        Company = pool.get('company.company')
        Statement = pool.get('account.statement')
        Move = pool.get('account.move')
        MoveLine = pool.get ('account.move.line')
        StatementLine = pool.get('account.statement.line')
        Invoice = pool.get('account.invoice')
        Sale = pool.get('sale.sale')
        fecha = data['date_start']
        fecha_fin = data['date_end']
        company = Company(data['company'])
        account = None
        number_invoice = None
        ventas_efectivo =  Decimal(0.0)
        move_lines = []
        subtotal14 = Decimal(0.0)
        subtotal0 = Decimal(0.0)
        description_14 = ""
        sales = Sale.search([('sale_date', '>=', fecha), ('sale_date', '<=', fecha_fin), ('state', '!=', 'anulled'), ('state', '!=', 'draft'), ('state', '!=', 'quotation'), ('devolucion', '=', None)])
        ventas_efectivo = Decimal(0.0)
        total = Decimal(0.0)
        account_revenue = None
        account_revenue_0 = None

        for sale in sales:
            if sale.total_amount > Decimal(0.0):
                ventas_efectivo += sale.total_amount
                for line in sale.lines:
                    if  line.taxes:
                        for t in line.taxes:
                            if str('{:.0f}'.format(t.rate*100)) == '14':
                                if account_revenue == None:
                                    if line.product.account_category == True:
                                        if line.product.category.taxes_parent == True:
                                            account_revenue= line.product.category.parent.account_revenue
                                        else:
                                            account_revenue= line.product.category.account_revenue
                                    else:
                                        account_revenue = line.product.account_revenue
                                if line.amount > 0:
                                    description_14 = t.description
                                    subtotal14= subtotal14 + (line.amount)

                            if str('{:.0f}'.format(t.rate*100)) == '0':
                                if account_revenue_0 == None:
                                    if line.product.account_category == True:
                                        if line.product.category.taxes_parent == True:
                                            account_revenue_0= line.product.category.parent.account_revenue
                                        else:
                                            account_revenue_0= line.product.category.account_revenue
                                    else:
                                        account_revenue_0 = line.product.account_revenue

                                if line.amount > 0:
                                    subtotal0= subtotal0 + (line.amount)

                invoices = Invoice.search([('description', '=', sale.reference), ('description', '!=', None), ('type', '=', 'out_invoice')])
                if invoices:
                    for i in invoices:
                        invoice = i

                number_invoice = invoice.number
                lineas = {}

                if sale.payments:
                    for s in sale.payments:
                        account = s.statement.journal.journal.debit_account
                        amount = s.amount
                    lineas['cod'] = account.code
                    lineas['party'] = sale.party
                    lineas['account'] = account.name
                    lineas['number'] = number_invoice
                    lineas['debit'] = amount

                else:
                    iva = Decimal(0.0)
                    total = Decimal(0.0)
                    if invoice.move:
                        for line in invoice.move.lines:
                            if line.party != None and line.credit > 0:
                                iva = line.credit
                            if line.party != None and line.debit > 0:
                                account = line.account
                                total = line.debit

                    lineas['cod'] = account.code
                    lineas['party'] = sale.party
                    lineas['account'] = account.name
                    lineas['number'] = number_invoice
                    lineas['debit'] = total - iva

                move_lines.append(lineas)

        total = ventas_efectivo
        total_iva = total - (subtotal14 + subtotal0)
        total_credito = subtotal0 + subtotal14 + total_iva

        if company.timezone:
            timezone = pytz.timezone(company.timezone)
            dt = datetime.now()
            hora = datetime.astimezone(dt.replace(tzinfo=pytz.utc), timezone)


        localcontext['company'] = company
        localcontext['fecha'] = fecha.strftime('%d/%m/%Y')
        localcontext['fecha_fin'] = fecha_fin.strftime('%d/%m/%Y')
        localcontext['hora'] = hora.strftime('%H:%M:%S')
        localcontext['fecha_im'] = hora.strftime('%d/%m/%Y')
        localcontext['total_ventas'] = ventas_efectivo
        localcontext['total_iva'] = total_iva
        localcontext['subtotal0'] = subtotal0
        localcontext['subtotal14'] = subtotal14
        localcontext['description_14'] = description_14
        localcontext['move_lines'] = move_lines
        localcontext['total_credito'] = total_credito
        localcontext['total'] = total
        localcontext['descripcion_sub_14'] = account_revenue
        localcontext['descripcion_sub_0'] = account_revenue_0

        return super(ReportMoveAll, cls).parse(report, objects, data, localcontext)

class PrintAccountReceivable(ModelView):
    'Print Account Receivable'
    __name__ = 'nodux_reports.print_account_receivable.start'
    company = fields.Many2One('company.company', 'Company', required=True)
    date_start = fields.Date("Fecha Inicio", required= True)
    date_end = fields.Date("Fecha Fin", required= True)
    vendedor = fields.Many2One('company.employee', 'Vendedor', required = True)
    vencidas = fields.Boolean('Cuentas Vencidas')
    clientes = fields.Boolean('Todos los clientes')
    cliente = fields.Many2One('party.party', 'Cliente',  states={
        'invisible' : Eval('clientes', True),
        'required' : ~Eval('clientes', True),
    })
    detallado = fields.Boolean('Reporte detallado')

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_vencidas():
        return True

    @staticmethod
    def default_clientes():
        return True

    @staticmethod
    def default_detallado():
        return True

    @staticmethod
    def default_date_start():
        date = Pool().get('ir.date')
        date = date.today()
        return date

    @staticmethod
    def default_date_end():
        date = Pool().get('ir.date')
        date = date.today()
        return date

#crear referencias
class AccountReceivable(Wizard):
    'Account Receivable'
    __name__ = 'nodux_reports.print_account_receivable'
    start = StateView('nodux_reports.print_account_receivable.start',
        'nodux_reports.print_account_receivable_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Print', 'print_', 'tryton-print', default=True),
            ])
    print_ = StateAction('nodux_reports.account_receivable')

    def do_print_(self, action):
        if self.start.clientes == False:
            data = {
                'company': self.start.company.id,
                'date_start' : self.start.date_start,
                'date_end' : self.start.date_end,
                'vendedor' : self.start.vendedor.id,
                'vencidas' : self.start.vencidas,
                'clientes' : self.start.clientes,
                'cliente' : self.start.cliente.id,
                'detallado' : self.start.detallado,
                }
        else:
            data = {
                'company': self.start.company.id,
                'date_start' : self.start.date_start,
                'date_end' : self.start.date_end,
                'vendedor' : self.start.vendedor.id,
                'vencidas' : self.start.vencidas,
                'clientes' : self.start.clientes,
                'detallado' : self.start.detallado,
                }
        return action, data

    def transition_print_(self):
        return 'end'

class ReportAccountReceivable(Report):
    __name__ = 'nodux_reports.account_receivable'

    @classmethod
    def parse(cls, report, objects, data, localcontext):
        pool = Pool()
        User = pool.get('res.user')
        user = User(Transaction().user)
        Date = pool.get('ir.date')
        Vendedor = pool.get('company.employee')
        Company = pool.get('company.company')
        Move = pool.get('account.move')
        MoveLine = pool.get ('account.move.line')
        StatementLine = pool.get('account.statement.line')
        Invoice = pool.get('account.invoice')
        Sale = pool.get('sale.sale')
        fecha = data['date_start']
        fecha_fin = data['date_end']
        company = Company(data['company'])
        vendedor = Vendedor(data['vendedor'])
        ventas_efectivo =  Decimal(0.0)
        account_lineas = []
        total = Decimal(0.0)
        account_lineas_out_det = []
        total_out_det = Decimal(0.0)

        if data['clientes'] == True:
            sales = Sale.search([('sale_date', '>=', fecha), ('devolucion', '=', False), ('sale_date', '<=', fecha_fin), ('employee', '=', vendedor.id), ('state', '=', 'processing')])
        else:
            sales = Sale.search([('sale_date', '>=', fecha), ('devolucion', '=', False), ('sale_date', '<=', fecha_fin), ('employee', '=', vendedor.id), ('state', '=', 'processing'), ('party', '=', data['cliente'])])
        terceros = []
        if sales:
            for s in sales:
                if s.party in terceros:
                    pass
                else:
                    terceros.append(s.party)
        if data['detallado'] == True:
            if data['vencidas'] == True:
                account_lineas = []
                totales = []
                abono = Decimal(0.0)
                Date = pool.get('ir.date')
                date_now = Date.today()
                total_final = Decimal(0.0)
                if terceros != []:
                    for party in terceros:
                        monto_total_individual = Decimal(0.0)
                        saldo_total_individual = Decimal(0.0)
                        lineas_totales = {}
                        for sale in sales:
                            if sale.party == party:
                                lineas = {}
                                amount = Decimal(0.0)
                                invoices = Invoice.search([('description','=', sale.reference), ('description', '!=', None), ('party', '=', party.id)])
                                if invoices:
                                    for i in invoices:
                                        move = i.move
                                        invoice = i
                                    lines = MoveLine.search([('move', '=', move), ('party', '!=', None), ('maturity_date', '!=', None)])
                                    if lines:
                                        for l in lines:
                                            date = l.maturity_date
                                abono = (invoice.total_amount - invoice.amount_to_pay)
                                saldo = invoice.amount_to_pay
                                monto_total_individual += abono
                                saldo_total_individual = +invoice.amount_to_pay

                                dias = date_now - date
                                dias = dias.days
                                if dias < 0:
                                    dias = 0

                                if (date <= date_now):
                                    lineas['number'] = invoice.number
                                    lineas['tipo'] = 'FC'
                                    lineas['fecha'] = invoice.invoice_date
                                    lineas['fecha_vence'] = date
                                    lineas['cliente'] = invoice.party
                                    lineas['total'] = invoice.total_amount
                                    lineas['abono'] = abono
                                    lineas['saldo'] = invoice.amount_to_pay
                                    lineas['dias'] = dias
                                    lineas['vencida'] = True
                                    account_lineas.append(lineas)

                        lineas_totales['party'] = party.id
                        lineas_totales['abono'] = monto_total_individual
                        lineas_totales['saldo'] = saldo_total_individual
                        total_final +=  saldo_total_individual
            else:
                account_lineas = []
                totales = []
                abono = Decimal(0.0)
                Date = pool.get('ir.date')
                date_now = Date.today()
                total_final = Decimal(0.0)

                if terceros != []:
                    for party in terceros:
                        monto_total_individual = Decimal(0.0)
                        saldo_total_individual = Decimal(0.0)
                        lineas_totales = {}
                        for sale in sales:
                            if party == sale.party:
                                lineas = {}
                                amount = Decimal(0.0)
                                invoices = Invoice.search([('description','=', sale.reference), ('description', '!=', None), ('party', '=', party.id)])
                                if invoices:
                                    for i in invoices:
                                        move = i.move
                                        invoice = i
                                    lines = MoveLine.search([('move', '=', move), ('party', '!=', None), ('maturity_date', '!=', None)])
                                    if lines:
                                        for l in lines:
                                            date = l.maturity_date
                                abono = (invoice.total_amount - invoice.amount_to_pay)
                                monto_total_individual += abono
                                saldo_total_individual += invoice.amount_to_pay
                                dias = date_now - date
                                dias = dias.days
                                if dias < 0:
                                    dias = 0
                                if (date <= date_now):
                                    lineas['number'] = invoice.number
                                    lineas['tipo'] = 'FC'
                                    lineas['fecha'] = invoice.invoice_date
                                    lineas['fecha_vence'] = date
                                    lineas['cliente'] = invoice.party
                                    lineas['total'] = invoice.total_amount
                                    lineas['abono'] = abono
                                    lineas['saldo'] = invoice.amount_to_pay
                                    lineas['dias'] = dias
                                    lineas['vencida'] = True
                                    account_lineas.append(lineas)
                                else:
                                    lineas['number'] = invoice.number
                                    lineas['tipo'] = 'FC'
                                    lineas['fecha'] = invoice.invoice_date
                                    lineas['fecha_vence'] = date
                                    lineas['cliente'] = invoice.party
                                    lineas['total'] = invoice.total_amount
                                    lineas['abono'] = abono
                                    lineas['saldo'] = invoice.amount_to_pay
                                    lineas['dias'] = dias
                                    lineas['vencida'] = False
                                    account_lineas.append(lineas)

                        lineas_totales['party'] = party.id
                        lineas_totales['abono'] = monto_total_individual
                        lineas_totales['saldo'] = saldo_total_individual
                        total_final +=  saldo_total_individual
        else:
            if data['vencidas'] == True:
                Date = pool.get('ir.date')
                date_now = Date.today()
                total_out_det = Decimal(0.0)
                if terceros != []:
                    for party in terceros:
                        monto_total_individual = Decimal(0.0)
                        saldo_total_individual = Decimal(0.0)
                        lineas_totales = {}
                        for sale in sales:
                            if party == sale.party:
                                amount = Decimal(0.0)
                                invoices = Invoice.search([('description','=', sale.reference), ('description', '!=', None), ('party', '=', party.id)])
                                if invoices:
                                    for i in invoices:
                                        move = i.move
                                        invoice = i
                                    lines = MoveLine.search([('move', '=', move), ('party', '!=', None), ('maturity_date', '!=', None), ('reconciliation', '=', None)])
                                    if lines:
                                        for l in lines:
                                            date = l.maturity_date
                                            if (date <= date_now):
                                                saldo_total_individual += l.debit
                        if saldo_total_individual > Decimal(0.0):
                            lineas_totales['party'] = party
                            lineas_totales['abono'] = Decimal(0.0)
                            lineas_totales['saldo'] = saldo_total_individual
                            account_lineas_out_det.append(lineas_totales)
                        total_out_det +=  saldo_total_individual
            else:
                Date = pool.get('ir.date')
                date_now = Date.today()
                total_out_det = Decimal(0.0)
                account_lineas_out_det = []
                if terceros != []:

                    for party in terceros:
                        monto_total_individual = Decimal(0.0)
                        saldo_total_individual = Decimal(0.0)
                        lineas_totales = {}

                        for sale in sales:
                            if party == sale.party:
                                lineas = {}
                                amount = Decimal(0.0)
                                invoices = Invoice.search([('description','=', sale.reference), ('description', '!=', None), ('party', '=', party.id)])
                                if invoices:
                                    for i in invoices:
                                        move = i.move
                                        invoice = i
                                    lines = MoveLine.search([('move', '=', move), ('party', '!=', None), ('maturity_date', '!=', None), ('reconciliation', '=', None)])
                                    if lines:
                                        for l in lines:
                                            date = l.maturity_date
                                            saldo_total_individual += l.debit
                        if saldo_total_individual > Decimal(0.0):
                            lineas_totales['party'] = party
                            lineas_totales['abono'] = Decimal(0.0)
                            lineas_totales['saldo'] = saldo_total_individual
                            account_lineas_out_det.append(lineas_totales)
                        total_out_det +=  saldo_total_individual

        if company.timezone:
            timezone = pytz.timezone(company.timezone)
            dt = datetime.now()
            hora = datetime.astimezone(dt.replace(tzinfo=pytz.utc), timezone)
        localcontext['company'] = company
        localcontext['vendedor'] = vendedor
        localcontext['fecha'] = fecha.strftime('%d/%m/%Y')
        localcontext['fecha_fin'] = fecha_fin.strftime('%d/%m/%Y')
        localcontext['hora'] = hora.strftime('%H:%M:%S')
        localcontext['fecha_im'] = hora.strftime('%d/%m/%Y')
        localcontext['total_ventas'] = ventas_efectivo
        localcontext['account_lineas'] = account_lineas
        localcontext['total'] = total_final
        localcontext['detallado'] = data['detallado']
        localcontext['account_lineas_out_det'] = account_lineas_out_det
        localcontext['total_out_det'] = total_out_det

        return super(ReportAccountReceivable, cls).parse(report, objects, data, localcontext)

class CuboVenta(ModelSQL, ModelView):
    'Cubo Venta'
    __name__ = 'account.cubo_venta'

    fecha_inicio = fields.Date('Desde')
    fecha_fin = fields.Date('Hasta')
    bodega = fields.Many2One('stock.location', 'Bodega',
        domain=[('type', '=', 'warehouse')])
    usuario = fields.Many2One('res.user', 'Usuario')
    vendedor = fields.Many2One('company.employee', 'Vendedor')
    country = fields.Many2One('country.country', 'Country')
    zona = fields.Many2One("country.subdivision",
            'Subdivision', domain=[('country', '=', Eval('country'))],
            depends=['country'])
    cliente = fields.Many2One('party.party', 'Cliente')
    marca = fields.Many2One('product.brand', 'Marca')
    lista_precio = fields.Many2One('product.price_list', 'Precio')
    categoria = fields.Many2One('product.category', 'Categoria')
    tipo = fields.Selection(TYPES, 'Tipo')
    lines = fields.One2Many('account.cubo_venta_lineas', 'cubo_ref', 'Lineas', readonly=True)
    cantidad = fields.Float('Cantidad')
    cajas = fields.Float('Cajas')
    stock = fields.Float('Stock')
    total = fields.Numeric('Total')
    costo_total = fields.Numeric('Costo')

    @classmethod
    def __setup__(cls):
        super(CuboVenta, cls).__setup__()

    @staticmethod
    def default_country():
        pool = Pool()
        Country = pool.get('country.country')
        countries = Country.search([('code', '=', 'EC')])
        for country in countries:
            return country.id

    @staticmethod
    def default_fecha_inicio():
        date = Pool().get('ir.date')
        date = date.today()
        return date

    @staticmethod
    def default_fecha_fin():
        date = Pool().get('ir.date')
        date = date.today()
        return date

    @fields.depends('fecha_inicio', 'fecha_fin', 'bodega', 'usuario', 'vendedor',
        'country','zona','cliente', 'marca', 'lista_precio', 'categoria', 'tipo',
        'lines')
    def on_change_fecha_inicio(self):
        pool = Pool()
        res = {}
        res['lines'] = {}
        Sale = pool.get('sale.sale')
        Invoice = pool.get('account.invoice')
        cantidad = 0
        cajas = 0
        stock = 0
        total_sumatoria = 0
        costo_total_sumatoria = 0
        grouping=('product',)

        if self.fecha_inicio and self.fecha_fin == None and self.bodega == None and self.usuario == None and self.vendedor == None and self.zona == None and self.cliente == None and self.marca == None and self.lista_precio== None and self.categoria == None and self.tipo == None:
            if self.lines:
                res['lines']['remove'] = [x['id'] for x in self.lines]

            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_inicio)])

            for sale in sales:
                if sale.state == "draft":
                    pass
                elif sale.devolucion == True:
                    pass
                else:
                    invoices = Invoice.search([('description','=',sale.reference), ('description', '!=', None),('type', '=', 'out_invoice')])
                    for i in invoices:
                        invoice = i

                    for l in sale.lines:

                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                        if costo_total > Decimal(0.0):
                            utilidad = ((l.amount - costo_total)*100)/costo_total
                        else:
                            utilidad = Decimal(100)

                        stock_individual = 0

                        if self.bodega:
                            location_ids = [self.bodega.id]
                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                    grouping=grouping)
                            for clave, valor in cantidad_bodega.iteritems():
                                stock_individual = valor
                        else:
                            Location = Pool().get('stock.location')
                            locations = Location.search([('type','=', 'warehouse')])
                            for location in locations:
                                location_ids = [location.id]
                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                for clave, valor in cantidad_bodega.iteritems():
                                    stock_individual += valor

                        cubo_line = {
                            'codigo': l.product.code,
                            'item': l.product.template.name,
                            'cantidad': l.quantity,
                            'cajas': 0,
                            'stock': stock_individual,
                            'total': l.amount,
                            'costo_total': costo_total,
                            'utilidad': utilidad,
                            'factura':invoice.number
                        }
                        cantidad +=  l.quantity
                        cajas += 0
                        stock += stock_individual
                        total_sumatoria += l.amount
                        costo_total_sumatoria += costo_total
                        res['lines'].setdefault('add', []).append((0, cubo_line))
            res['cantidad'] = cantidad
            res['cajas'] = cajas
            res['stock'] = stock
            res['total'] = total_sumatoria
            res['costo_total'] = costo_total_sumatoria
            return res
        else:
            return res

    @fields.depends('fecha_inicio', 'fecha_fin', 'bodega', 'usuario', 'vendedor',
        'country','zona','cliente', 'marca', 'lista_precio', 'categoria', 'tipo',
        'lines')
    def on_change_fecha_fin(self):
        pool = Pool()
        res = {}
        res['lines'] = {}
        Sale = pool.get('sale.sale')
        Invoice = pool.get('account.invoice')
        cantidad = 0
        cajas = 0
        stock = 0
        total_sumatoria = 0
        costo_total_sumatoria = 0
        grouping=('product',)

        if self.fecha_inicio and self.fecha_fin:
            if self.lines:
                res['lines']['remove'] = [x['id'] for x in self.lines]

            if self.bodega != None:
                if self.vendedor != None:
                    if self.lista_precio != None:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('employee', '=', self.vendedor), ('price_list', '=', self.lista_precio), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('employee', '=', self.vendedor), ('price_list', '=', self.lista_precio)])
                    else:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('employee', '=', self.vendedor), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('employee', '=', self.vendedor)])

                else:
                    if self.lista_precio != None:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('price_list', '=', self.lista_precio), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('price_list', '=', self.lista_precio)])
                    else:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega),('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega)])
            else:

                if self.vendedor != None:
                    if self.lista_precio != None:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('employee', '=', self.vendedor), ('price_list', '=', self.lista_precio), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('employee', '=', self.vendedor), ('price_list', '=', self.lista_precio)])
                    else:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('employee', '=', self.vendedor), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('employee', '=', self.vendedor)])

                else:
                    if self.lista_precio != None:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('price_list', '=', self.lista_precio), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin),('price_list', '=', self.lista_precio)])
                    else:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin)])

            for sale in sales:
                if sale.state == "draft":
                    pass
                elif sale.devolucion == True:
                    pass
                else:
                    invoices = Invoice.search([('description','=',sale.reference), ('description', '!=', None),('type', '=', 'out_invoice')])
                    for i in invoices:
                        invoice = i

                    for l in sale.lines:
                        if self.tipo:
                            if self.categoria:
                                if self.marca:
                                    if self.tipo == l.product.template.type and self.categoria == l.product.template.category and self.marca == l.product.template.brand:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)

                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor

                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock': stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad': utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                                else:
                                    if self.tipo == l.product.template.type and self.categoria == l.product.template.category:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)

                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor

                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock': stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad': utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                            else:
                                if self.marca:
                                    if self.tipo == l.product.template.type and self.marca == l.product.template.brand:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor

                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock': stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad': utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                                else:
                                    if self.tipo == l.product.template.type:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)

                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor

                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock': stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad': utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                        else:
                            if self.categoria:
                                if self.marca:
                                    if self.categoria == l.product.template.category and self.marca == l.product.template.brand:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor

                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock': stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad': utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                                else:
                                    if self.categoria == l.product.template.category:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor

                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock': stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad': utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                            else:
                                if self.marca:
                                    if self.marca == l.product.template.brand:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor

                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock': stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad': utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                                else:
                                    costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                    if costo_total > Decimal(0.0):
                                        utilidad = ((l.amount - costo_total)*100)/costo_total
                                    else:
                                        utilidad = Decimal(100)
                                    stock_individual = 0
                                    if self.bodega:
                                        location_ids = [self.bodega.id]
                                        cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                grouping=grouping)
                                        for clave, valor in cantidad_bodega.iteritems():
                                            stock_individual = valor
                                    else:
                                        Location = Pool().get('stock.location')
                                        locations = Location.search([('type','=', 'warehouse')])
                                        for location in locations:
                                            location_ids = [location.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual += valor

                                    cubo_line = {
                                        'codigo': l.product.code,
                                        'item': l.product.template.name,
                                        'cantidad': l.quantity,
                                        'cajas': 0,
                                        'stock': stock_individual,
                                        'total': l.amount,
                                        'costo_total': costo_total,
                                        'utilidad': utilidad,
                                        'factura':invoice.number
                                    }
                                    cantidad +=  l.quantity
                                    cajas += 0
                                    stock += stock_individual
                                    total_sumatoria += l.amount
                                    costo_total_sumatoria += costo_total
                                    res['lines'].setdefault('add', []).append((0, cubo_line))

            res['cantidad'] = cantidad
            res['cajas'] = cajas
            res['stock'] = stock
            res['total'] = total_sumatoria
            res['costo_total'] = costo_total_sumatoria
            return res
        else:
            return res

    @fields.depends('fecha_inicio', 'fecha_fin', 'bodega', 'usuario', 'vendedor',
        'country','zona','cliente', 'marca', 'lista_precio', 'categoria', 'tipo',
        'lines')
    def on_change_bodega(self):
        pool = Pool()
        res = {}
        res['lines'] = {}
        Sale = pool.get('sale.sale')
        Invoice = pool.get('account.invoice')
        cantidad = 0
        cajas = 0
        stock = 0
        total_sumatoria = 0
        costo_total_sumatoria = 0
        grouping=('product',)

        if self.fecha_inicio and self.fecha_fin:
            if self.lines:
                res['lines']['remove'] = [x['id'] for x in self.lines]

            if self.bodega != None:
                if self.vendedor != None:
                    if self.lista_precio != None:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('employee', '=', self.vendedor), ('price_list', '=', self.lista_precio), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('employee', '=', self.vendedor), ('price_list', '=', self.lista_precio)])
                    else:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('employee', '=', self.vendedor), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('employee', '=', self.vendedor)])

                else:
                    if self.lista_precio != None:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('price_list', '=', self.lista_precio), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('price_list', '=', self.lista_precio)])
                    else:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega),('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega)])
            else:

                if self.vendedor != None:
                    if self.lista_precio != None:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('employee', '=', self.vendedor), ('price_list', '=', self.lista_precio), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('employee', '=', self.vendedor), ('price_list', '=', self.lista_precio)])
                    else:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('employee', '=', self.vendedor), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('employee', '=', self.vendedor)])

                else:
                    if self.lista_precio != None:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('price_list', '=', self.lista_precio), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin),('price_list', '=', self.lista_precio)])
                    else:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin)])

            for sale in sales:
                if sale.state == "draft":
                    pass
                elif sale.devolucion == True:
                    pass
                else:
                    invoices = Invoice.search([('description','=',sale.reference), ('description', '!=', None),('type', '=', 'out_invoice')])
                    for i in invoices:
                        invoice = i

                    for l in sale.lines:
                        if self.tipo:
                            if self.categoria:
                                if self.marca:
                                    if self.tipo == l.product.template.type and self.categoria == l.product.template.category and self.marca == l.product.template.brand:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor

                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock': stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad': utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                                else:
                                    if self.tipo == l.product.template.type and self.categoria == l.product.template.category:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor

                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock': stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad': utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                            else:
                                if self.marca:
                                    if self.tipo == l.product.template.type and self.marca == l.product.template.brand:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor

                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock': stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad': utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                                else:
                                    if self.tipo == l.product.template.type:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor

                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock':stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad': utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                        else:
                            if self.categoria:
                                if self.marca:
                                    if self.categoria == l.product.template.category and self.marca == l.product.template.brand:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor

                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock':stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad': utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                                else:
                                    if self.categoria == l.product.template.category:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor

                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock': stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad': utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                            else:
                                if self.marca:
                                    if self.marca == l.product.template.brand:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor

                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock': stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad': utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                                else:
                                    costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                    if costo_total > Decimal(0.0):
                                        utilidad = ((l.amount - costo_total)*100)/costo_total
                                    else:
                                        utilidad = Decimal(100)
                                    stock_individual = 0
                                    if self.bodega:
                                        location_ids = [self.bodega.id]
                                        cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                grouping=grouping)
                                        for clave, valor in cantidad_bodega.iteritems():
                                            stock_individual = valor
                                    else:
                                        Location = Pool().get('stock.location')
                                        locations = Location.search([('type','=', 'warehouse')])
                                        for location in locations:
                                            location_ids = [location.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual += valor

                                    cubo_line = {
                                        'codigo': l.product.code,
                                        'item': l.product.template.name,
                                        'cantidad': l.quantity,
                                        'cajas': 0,
                                        'stock': stock_individual,
                                        'total': l.amount,
                                        'costo_total': costo_total,
                                        'utilidad': utilidad,
                                        'factura':invoice.number
                                    }
                                    cantidad +=  l.quantity
                                    cajas += 0
                                    stock += stock_individual
                                    total_sumatoria += l.amount
                                    costo_total_sumatoria += costo_total
                                    res['lines'].setdefault('add', []).append((0, cubo_line))

            res['cantidad'] = cantidad
            res['cajas'] = cajas
            res['stock'] = stock
            res['total'] = total_sumatoria
            res['costo_total'] = costo_total_sumatoria
            return res
        else:
            return res

    @fields.depends('fecha_inicio', 'fecha_fin', 'bodega', 'usuario', 'vendedor',
        'country','zona','cliente', 'marca', 'lista_precio', 'categoria', 'tipo',
        'lines')
    def on_change_usuario(self):
        pool = Pool()
        res = {}
        res['lines'] = {}
        Sale = pool.get('sale.sale')
        Invoice = pool.get('account.invoice')
        cantidad = 0
        cajas = 0
        stock = 0
        total_sumatoria = 0
        costo_total_sumatoria = 0
        grouping=('product',)

        if self.fecha_inicio and self.fecha_fin:
            if self.lines:
                res['lines']['remove'] = [x['id'] for x in self.lines]

            if self.bodega != None:
                if self.vendedor != None:
                    if self.lista_precio != None:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('employee', '=', self.vendedor), ('price_list', '=', self.lista_precio), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('employee', '=', self.vendedor), ('price_list', '=', self.lista_precio)])
                    else:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('employee', '=', self.vendedor), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('employee', '=', self.vendedor)])

                else:
                    if self.lista_precio != None:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('price_list', '=', self.lista_precio), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('price_list', '=', self.lista_precio)])
                    else:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega),('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega)])
            else:

                if self.vendedor != None:
                    if self.lista_precio != None:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('employee', '=', self.vendedor), ('price_list', '=', self.lista_precio), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('employee', '=', self.vendedor), ('price_list', '=', self.lista_precio)])
                    else:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('employee', '=', self.vendedor), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('employee', '=', self.vendedor)])

                else:
                    if self.lista_precio != None:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('price_list', '=', self.lista_precio), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin),('price_list', '=', self.lista_precio)])
                    else:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin)])

            for sale in sales:
                if sale.state == "draft":
                    pass
                elif sale.devolucion == True:
                    pass
                else:
                    invoices = Invoice.search([('description','=',sale.reference), ('description', '!=', None),('type', '=', 'out_invoice')])
                    for i in invoices:
                        invoice = i
                    for l in sale.lines:
                        if self.tipo:
                            if self.categoria:
                                if self.marca:
                                    if self.tipo == l.product.template.type and self.categoria == l.product.template.category and self.marca == l.product.template.brand:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor

                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock': stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad':utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                                else:
                                    if self.tipo == l.product.template.type and self.categoria == l.product.template.category:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor

                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock': stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad':utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                            else:
                                if self.marca:
                                    if self.tipo == l.product.template.type and self.marca == l.product.template.brand:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock': stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad':utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                                else:
                                    if self.tipo == l.product.template.type:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock': stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad':utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                        else:
                            if self.categoria:
                                if self.marca:
                                    if self.categoria == l.product.template.category and self.marca == l.product.template.brand:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock': stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad':utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                                else:
                                    if self.categoria == l.product.template.category:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock': stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad':utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                            else:
                                if self.marca:
                                    if self.marca == l.product.template.brand:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock': stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad':utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                                else:
                                    costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                    if costo_total > Decimal(0.0):
                                        utilidad = ((l.amount - costo_total)*100)/costo_total
                                    else:
                                        utilidad = Decimal(100)
                                    stock_individual = 0
                                    if self.bodega:
                                        location_ids = [self.bodega.id]
                                        cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                grouping=grouping)
                                        for clave, valor in cantidad_bodega.iteritems():
                                            stock_individual = valor
                                    else:
                                        Location = Pool().get('stock.location')
                                        locations = Location.search([('type','=', 'warehouse')])
                                        for location in locations:
                                            location_ids = [location.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual += valor
                                    cubo_line = {
                                        'codigo': l.product.code,
                                        'item': l.product.template.name,
                                        'cantidad': l.quantity,
                                        'cajas': 0,
                                        'stock': stock_individual,
                                        'total': l.amount,
                                        'costo_total': costo_total,
                                        'utilidad':utilidad,
                                        'factura':invoice.number
                                    }
                                    cantidad +=  l.quantity
                                    cajas += 0
                                    stock += stock_individual
                                    total_sumatoria += l.amount
                                    costo_total_sumatoria += costo_total
                                    res['lines'].setdefault('add', []).append((0, cubo_line))

            res['cantidad'] = cantidad
            res['cajas'] = cajas
            res['stock'] = stock
            res['total'] = total_sumatoria
            res['costo_total'] = costo_total_sumatoria
            return res
        else:
            return res

    @fields.depends('fecha_inicio', 'fecha_fin', 'bodega', 'usuario', 'vendedor',
        'country','zona','cliente', 'marca', 'lista_precio', 'categoria', 'tipo',
        'lines')
    def on_change_vendedor(self):
        pool = Pool()
        res = {}
        res['lines'] = {}
        Sale = pool.get('sale.sale')
        Invoice = pool.get('account.invoice')
        cantidad = 0
        cajas = 0
        stock = 0
        total_sumatoria = 0
        costo_total_sumatoria = 0
        grouping=('product',)

        if self.fecha_inicio and self.fecha_fin:
            if self.lines:
                res['lines']['remove'] = [x['id'] for x in self.lines]

            if self.bodega != None:
                if self.vendedor != None:
                    if self.lista_precio != None:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('employee', '=', self.vendedor), ('price_list', '=', self.lista_precio), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('employee', '=', self.vendedor), ('price_list', '=', self.lista_precio)])
                    else:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('employee', '=', self.vendedor), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('employee', '=', self.vendedor)])

                else:
                    if self.lista_precio != None:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('price_list', '=', self.lista_precio), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('price_list', '=', self.lista_precio)])
                    else:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega),('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega)])
            else:

                if self.vendedor != None:
                    if self.lista_precio != None:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('employee', '=', self.vendedor), ('price_list', '=', self.lista_precio), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('employee', '=', self.vendedor), ('price_list', '=', self.lista_precio)])
                    else:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('employee', '=', self.vendedor), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('employee', '=', self.vendedor)])

                else:
                    if self.lista_precio != None:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('price_list', '=', self.lista_precio), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin),('price_list', '=', self.lista_precio)])
                    else:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin)])

            for sale in sales:
                if sale.state == "draft":
                    pass
                elif sale.devolucion == True:
                    pass
                else:
                    invoices = Invoice.search([('description','=',sale.reference), ('description', '!=', None),('type', '=', 'out_invoice')])
                    for i in invoices:
                        invoice = i

                    for l in sale.lines:
                        if self.tipo:
                            if self.categoria:
                                if self.marca:
                                    if self.tipo == l.product.template.type and self.categoria == l.product.template.category and self.marca == l.product.template.brand:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock': stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad': utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                                else:
                                    if self.tipo == l.product.template.type and self.categoria == l.product.template.category:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock': stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad': utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                            else:
                                if self.marca:
                                    if self.tipo == l.product.template.type and self.marca == l.product.template.brand:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock': stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad': utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                                else:
                                    if self.tipo == l.product.template.type:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock': stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad': utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                        else:
                            if self.categoria:
                                if self.marca:
                                    if self.categoria == l.product.template.category and self.marca == l.product.template.brand:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock': stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad': utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                                else:
                                    if self.categoria == l.product.template.category:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock': stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad': utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                            else:
                                if self.marca:
                                    if self.marca == l.product.template.brand:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock': stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad': utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                                else:
                                    costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                    if costo_total > Decimal(0.0):
                                        utilidad = ((l.amount - costo_total)*100)/costo_total
                                    else:
                                        utilidad = Decimal(100)
                                    stock_individual = 0
                                    if self.bodega:
                                        location_ids = [self.bodega.id]
                                        cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                grouping=grouping)
                                        for clave, valor in cantidad_bodega.iteritems():
                                            stock_individual = valor
                                    else:
                                        Location = Pool().get('stock.location')
                                        locations = Location.search([('type','=', 'warehouse')])
                                        for location in locations:
                                            location_ids = [location.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual += valor
                                    cubo_line = {
                                        'codigo': l.product.code,
                                        'item': l.product.template.name,
                                        'cantidad': l.quantity,
                                        'cajas': 0,
                                        'stock':stock_individual,
                                        'total': l.amount,
                                        'costo_total': costo_total,
                                        'utilidad': utilidad,
                                        'factura':invoice.number
                                    }
                                    cantidad +=  l.quantity
                                    cajas += 0
                                    stock += stock_individual

                                    total_sumatoria += l.amount
                                    costo_total_sumatoria += costo_total
                                    res['lines'].setdefault('add', []).append((0, cubo_line))

            res['cantidad'] = cantidad
            res['cajas'] = cajas
            res['stock'] = stock
            res['total'] = total_sumatoria
            res['costo_total'] = costo_total_sumatoria
            return res
        else:
            return res

    @fields.depends('fecha_inicio', 'fecha_fin', 'bodega', 'usuario', 'vendedor',
        'country','zona','cliente', 'marca', 'lista_precio', 'categoria', 'tipo',
        'lines')
    def on_change_cliente(self):
        pool = Pool()
        res = {}
        res['lines'] = {}
        Sale = pool.get('sale.sale')
        Invoice = pool.get('account.invoice')
        cantidad = 0
        cajas = 0
        stock = 0
        total_sumatoria = 0
        costo_total_sumatoria = 0
        grouping=('product',)

        if self.fecha_inicio and self.fecha_fin:
            if self.lines:
                res['lines']['remove'] = [x['id'] for x in self.lines]

            if self.bodega != None:
                if self.vendedor != None:
                    if self.lista_precio != None:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('employee', '=', self.vendedor), ('price_list', '=', self.lista_precio), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('employee', '=', self.vendedor), ('price_list', '=', self.lista_precio)])
                    else:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('employee', '=', self.vendedor), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('employee', '=', self.vendedor)])

                else:
                    if self.lista_precio != None:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('price_list', '=', self.lista_precio), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('price_list', '=', self.lista_precio)])
                    else:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega),('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega)])
            else:

                if self.vendedor != None:
                    if self.lista_precio != None:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('employee', '=', self.vendedor), ('price_list', '=', self.lista_precio), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('employee', '=', self.vendedor), ('price_list', '=', self.lista_precio)])
                    else:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('employee', '=', self.vendedor), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('employee', '=', self.vendedor)])

                else:
                    if self.lista_precio != None:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('price_list', '=', self.lista_precio), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin),('price_list', '=', self.lista_precio)])
                    else:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin)])

            for sale in sales:
                if sale.state == "draft":
                    pass
                elif sale.devolucion == True:
                    pass
                else:
                    invoices = Invoice.search([('description','=',sale.reference), ('description', '!=', None),('type', '=', 'out_invoice')])
                    for i in invoices:
                        invoice = i

                    for l in sale.lines:
                        if self.tipo:
                            if self.categoria:
                                if self.marca:
                                    if self.tipo == l.product.template.type and self.categoria == l.product.template.category and self.marca == l.product.template.brand:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock': stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad':utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                                else:
                                    if self.tipo == l.product.template.type and self.categoria == l.product.template.category:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock':stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad':utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                            else:
                                if self.marca:
                                    if self.tipo == l.product.template.type and self.marca == l.product.template.brand:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock':stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad':utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                                else:
                                    if self.tipo == l.product.template.type:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock':stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad':utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                        else:
                            if self.categoria:
                                if self.marca:
                                    if self.categoria == l.product.template.category and self.marca == l.product.template.brand:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock':stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad':utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                                else:
                                    if self.categoria == l.product.template.category:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock':stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad':utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                            else:
                                if self.marca:
                                    if self.marca == l.product.template.brand:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock':stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad':utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                                else:
                                    costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                    if costo_total > Decimal(0.0):
                                        utilidad = ((l.amount - costo_total)*100)/costo_total
                                    else:
                                        utilidad = Decimal(100)
                                    stock_individual = 0
                                    if self.bodega:
                                        location_ids = [self.bodega.id]
                                        cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                grouping=grouping)
                                        for clave, valor in cantidad_bodega.iteritems():
                                            stock_individual = valor
                                    else:
                                        Location = Pool().get('stock.location')
                                        locations = Location.search([('type','=', 'warehouse')])
                                        for location in locations:
                                            location_ids = [location.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual += valor
                                    cubo_line = {
                                        'codigo': l.product.code,
                                        'item': l.product.template.name,
                                        'cantidad': l.quantity,
                                        'cajas': 0,
                                        'stock': stock_individual,
                                        'total': l.amount,
                                        'costo_total': costo_total,
                                        'utilidad':utilidad,
                                        'factura':invoice.number
                                    }
                                    cantidad +=  l.quantity
                                    cajas += 0
                                    stock += stock_individual
                                    total_sumatoria += l.amount
                                    costo_total_sumatoria += costo_total
                                    res['lines'].setdefault('add', []).append((0, cubo_line))

            res['cantidad'] = cantidad
            res['cajas'] = cajas
            res['stock'] = stock
            res['total'] = total_sumatoria
            res['costo_total'] = costo_total_sumatoria
            return res
        else:
            return res

    @fields.depends('fecha_inicio', 'fecha_fin', 'bodega', 'usuario', 'vendedor',
        'country','zona','cliente', 'marca', 'lista_precio', 'categoria', 'tipo',
        'lines')
    def on_change_marca(self):
        pool = Pool()
        res = {}
        res['lines'] = {}
        Sale = pool.get('sale.sale')
        Invoice = pool.get('account.invoice')
        cantidad = 0
        cajas = 0
        stock = 0
        total_sumatoria = 0
        costo_total_sumatoria = 0
        grouping=('product',)

        if self.fecha_inicio and self.fecha_fin:
            if self.lines:
                res['lines']['remove'] = [x['id'] for x in self.lines]

            if self.bodega != None:
                if self.vendedor != None:
                    if self.lista_precio != None:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('employee', '=', self.vendedor), ('price_list', '=', self.lista_precio), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('employee', '=', self.vendedor), ('price_list', '=', self.lista_precio)])
                    else:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('employee', '=', self.vendedor), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('employee', '=', self.vendedor)])

                else:
                    if self.lista_precio != None:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('price_list', '=', self.lista_precio), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('price_list', '=', self.lista_precio)])
                    else:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega),('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega)])
            else:

                if self.vendedor != None:
                    if self.lista_precio != None:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('employee', '=', self.vendedor), ('price_list', '=', self.lista_precio), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('employee', '=', self.vendedor), ('price_list', '=', self.lista_precio)])
                    else:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('employee', '=', self.vendedor), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('employee', '=', self.vendedor)])

                else:
                    if self.lista_precio != None:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('price_list', '=', self.lista_precio), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin),('price_list', '=', self.lista_precio)])
                    else:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin)])

            for sale in sales:
                if sale.state == "draft":
                    pass
                elif sale.devolucion == True:
                    pass
                else:
                    invoices = Invoice.search([('description','=',sale.reference), ('description', '!=', None),('type', '=', 'out_invoice')])
                    for i in invoices:
                        invoice = i

                    for l in sale.lines:
                        if self.tipo:
                            if self.categoria:
                                if self.marca:
                                    if self.tipo == l.product.template.type and self.categoria == l.product.template.category and self.marca == l.product.template.brand:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock':stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad':utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                                else:
                                    if self.tipo == l.product.template.type and self.categoria == l.product.template.category:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock':stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad':utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                            else:
                                if self.marca:
                                    if self.tipo == l.product.template.type and self.marca == l.product.template.brand:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock':stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad':utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                                else:
                                    if self.tipo == l.product.template.type:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock':stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad':utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                        else:
                            if self.categoria:
                                if self.marca:
                                    if self.categoria == l.product.template.category and self.marca == l.product.template.brand:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock':stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad':utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                                else:
                                    if self.categoria == l.product.template.category:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock':stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad':utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                            else:
                                if self.marca:
                                    if self.marca == l.product.template.brand:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock':stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad':utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                                else:
                                    costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                    if costo_total > Decimal(0.0):
                                        utilidad = ((l.amount - costo_total)*100)/costo_total
                                    else:
                                        utilidad = Decimal(100)
                                    stock_individual = 0
                                    if self.bodega:
                                        location_ids = [self.bodega.id]
                                        cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                grouping=grouping)
                                        for clave, valor in cantidad_bodega.iteritems():
                                            stock_individual = valor
                                    else:
                                        Location = Pool().get('stock.location')
                                        locations = Location.search([('type','=', 'warehouse')])
                                        for location in locations:
                                            location_ids = [location.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual += valor
                                    cubo_line = {
                                        'codigo': l.product.code,
                                        'item': l.product.template.name,
                                        'cantidad': l.quantity,
                                        'cajas': 0,
                                        'stock':stock_individual,
                                        'total': l.amount,
                                        'costo_total': costo_total,
                                        'utilidad':utilidad,
                                        'factura':invoice.number
                                    }
                                    cantidad +=  l.quantity
                                    cajas += 0
                                    stock += stock_individual
                                    total_sumatoria += l.amount
                                    costo_total_sumatoria += costo_total
                                    res['lines'].setdefault('add', []).append((0, cubo_line))

            res['cantidad'] = cantidad
            res['cajas'] = cajas
            res['stock'] = stock
            res['total'] = total_sumatoria
            res['costo_total'] = costo_total_sumatoria
            return res
        else:
            return res

    @fields.depends('fecha_inicio', 'fecha_fin', 'bodega', 'usuario', 'vendedor',
        'country','zona','cliente', 'marca', 'lista_precio', 'categoria', 'tipo',
        'lines')
    def on_change_lista_precio(self):
        pool = Pool()
        res = {}
        res['lines'] = {}
        Sale = pool.get('sale.sale')
        Invoice = pool.get('account.invoice')
        cantidad = 0
        cajas = 0
        stock = 0
        total_sumatoria = 0
        costo_total_sumatoria = 0
        grouping=('product',)

        if self.fecha_inicio and self.fecha_fin:
            if self.lines:
                res['lines']['remove'] = [x['id'] for x in self.lines]

            if self.bodega != None:
                if self.vendedor != None:
                    if self.lista_precio != None:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('employee', '=', self.vendedor), ('price_list', '=', self.lista_precio), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('employee', '=', self.vendedor), ('price_list', '=', self.lista_precio)])
                    else:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('employee', '=', self.vendedor), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('employee', '=', self.vendedor)])

                else:
                    if self.lista_precio != None:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('price_list', '=', self.lista_precio), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('price_list', '=', self.lista_precio)])
                    else:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega),('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega)])
            else:

                if self.vendedor != None:
                    if self.lista_precio != None:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('employee', '=', self.vendedor), ('price_list', '=', self.lista_precio), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('employee', '=', self.vendedor), ('price_list', '=', self.lista_precio)])
                    else:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('employee', '=', self.vendedor), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('employee', '=', self.vendedor)])

                else:
                    if self.lista_precio != None:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('price_list', '=', self.lista_precio), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin),('price_list', '=', self.lista_precio)])
                    else:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin)])

            for sale in sales:
                if sale.state == "draft":
                    pass
                elif sale.devolucion == True:
                    pass
                else:
                    invoices = Invoice.search([('description','=',sale.reference), ('description', '!=', None),('type', '=', 'out_invoice')])
                    for i in invoices:
                        invoice = i

                    for l in sale.lines:
                        if self.tipo:
                            if self.categoria:
                                if self.marca:
                                    if self.tipo == l.product.template.type and self.categoria == l.product.template.category and self.marca == l.product.template.brand:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock':stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad':utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                                else:
                                    if self.tipo == l.product.template.type and self.categoria == l.product.template.category:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock':stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad':utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                            else:
                                if self.marca:
                                    if self.tipo == l.product.template.type and self.marca == l.product.template.brand:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock':stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad':utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                                else:
                                    if self.tipo == l.product.template.type:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock':stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad':utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                        else:
                            if self.categoria:
                                if self.marca:
                                    if self.categoria == l.product.template.category and self.marca == l.product.template.brand:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock':stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad':utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                                else:
                                    if self.categoria == l.product.template.category:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock':stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad':utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                            else:
                                if self.marca:
                                    if self.marca == l.product.template.brand:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)

                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock':stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad':utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                                else:
                                    costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                    if costo_total > Decimal(0.0):
                                        utilidad = ((l.amount - costo_total)*100)/costo_total
                                    else:
                                        utilidad = Decimal(100)
                                    stock_individual = 0
                                    if self.bodega:
                                        location_ids = [self.bodega.id]
                                        cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                grouping=grouping)
                                        for clave, valor in cantidad_bodega.iteritems():
                                            stock_individual = valor
                                    else:
                                        Location = Pool().get('stock.location')
                                        locations = Location.search([('type','=', 'warehouse')])
                                        for location in locations:
                                            location_ids = [location.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual += valor
                                    cubo_line = {
                                        'codigo': l.product.code,
                                        'item': l.product.template.name,
                                        'cantidad': l.quantity,
                                        'cajas': 0,
                                        'stock':stock_individual,
                                        'total': l.amount,
                                        'costo_total': costo_total,
                                        'utilidad':utilidad,
                                        'factura':invoice.number
                                    }
                                    cantidad +=  l.quantity
                                    cajas += 0
                                    stock += stock_individual
                                    total_sumatoria += l.amount
                                    costo_total_sumatoria += costo_total
                                    res['lines'].setdefault('add', []).append((0, cubo_line))

            res['cantidad'] = cantidad
            res['cajas'] = cajas
            res['stock'] = stock
            res['total'] = total_sumatoria
            res['costo_total'] = costo_total_sumatoria
            return res
        else:
            return res

    @fields.depends('fecha_inicio', 'fecha_fin', 'bodega', 'usuario', 'vendedor',
        'country','zona','cliente', 'marca', 'lista_precio', 'categoria', 'tipo',
        'lines')
    def on_change_categoria(self):
        pool = Pool()
        res = {}
        res['lines'] = {}
        Sale = pool.get('sale.sale')
        Invoice = pool.get('account.invoice')
        cantidad = 0
        cajas = 0
        stock = 0
        total_sumatoria = 0
        costo_total_sumatoria = 0
        grouping=('product',)

        if self.fecha_inicio and self.fecha_fin:
            if self.lines:
                res['lines']['remove'] = [x['id'] for x in self.lines]

            if self.bodega != None:
                if self.vendedor != None:
                    if self.lista_precio != None:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('employee', '=', self.vendedor), ('price_list', '=', self.lista_precio), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('employee', '=', self.vendedor), ('price_list', '=', self.lista_precio)])
                    else:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('employee', '=', self.vendedor), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('employee', '=', self.vendedor)])

                else:
                    if self.lista_precio != None:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('price_list', '=', self.lista_precio), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('price_list', '=', self.lista_precio)])
                    else:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega),('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega)])
            else:

                if self.vendedor != None:
                    if self.lista_precio != None:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('employee', '=', self.vendedor), ('price_list', '=', self.lista_precio), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('employee', '=', self.vendedor), ('price_list', '=', self.lista_precio)])
                    else:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('employee', '=', self.vendedor), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('employee', '=', self.vendedor)])

                else:
                    if self.lista_precio != None:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('price_list', '=', self.lista_precio), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin),('price_list', '=', self.lista_precio)])
                    else:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin)])

            for sale in sales:
                if sale.state == "draft":
                    pass
                elif sale.devolucion == True:
                    pass
                else:
                    invoices = Invoice.search([('description','=',sale.reference), ('description', '!=', None),('type', '=', 'out_invoice')])
                    for i in invoices:
                        invoice = i

                    for l in sale.lines:

                        if self.tipo:
                            if self.categoria:
                                if self.marca:
                                    if self.tipo == l.product.template.type and self.categoria == l.product.template.category and self.marca == l.product.template.brand:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock':stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad':utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                                else:
                                    if self.tipo == l.product.template.type and self.categoria == l.product.template.category:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock':stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad':utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                            else:
                                if self.marca:
                                    if self.tipo == l.product.template.type and self.marca == l.product.template.brand:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock': stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad':utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                                else:
                                    if self.tipo == l.product.template.type:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock': stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad':utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                        else:
                            if self.categoria:
                                if self.marca:
                                    if self.categoria == l.product.template.category and self.marca == l.product.template.brand:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock': stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad':utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                                else:
                                    if self.categoria == l.product.template.category:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock': stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad':utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                            else:
                                if self.marca:
                                    if self.marca == l.product.template.brand:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock': stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad':utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                                else:
                                    costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                    if costo_total > Decimal(0.0):
                                        utilidad = ((l.amount - costo_total)*100)/costo_total
                                    else:
                                        utilidad = Decimal(100)
                                    stock_individual = 0
                                    if self.bodega:
                                        location_ids = [self.bodega.id]
                                        cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                grouping=grouping)
                                        for clave, valor in cantidad_bodega.iteritems():
                                            stock_individual = valor
                                    else:
                                        Location = Pool().get('stock.location')
                                        locations = Location.search([('type','=', 'warehouse')])
                                        for location in locations:
                                            location_ids = [location.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual += valor
                                    cubo_line = {
                                        'codigo': l.product.code,
                                        'item': l.product.template.name,
                                        'cantidad': l.quantity,
                                        'cajas': 0,
                                        'stock': stock_individual,
                                        'total': l.amount,
                                        'costo_total': costo_total,
                                        'utilidad':utilidad,
                                        'factura':invoice.number
                                    }
                                    cantidad +=  l.quantity
                                    cajas += 0
                                    stock += stock_individual
                                    total_sumatoria += l.amount
                                    costo_total_sumatoria += costo_total
                                    res['lines'].setdefault('add', []).append((0, cubo_line))

            res['cantidad'] = cantidad
            res['cajas'] = cajas
            res['stock'] = stock
            res['total'] = total_sumatoria
            res['costo_total'] = costo_total_sumatoria
            return res
        else:
            return res

    @fields.depends('fecha_inicio', 'fecha_fin', 'bodega', 'usuario', 'vendedor',
        'country','zona','cliente', 'marca', 'lista_precio', 'categoria', 'tipo',
        'lines')
    def on_change_tipo(self):
        pool = Pool()
        res = {}
        res['lines'] = {}
        Sale = pool.get('sale.sale')
        Invoice = pool.get('account.invoice')
        cantidad = 0
        cajas = 0
        stock = 0
        total_sumatoria = 0
        costo_total_sumatoria = 0
        grouping=('product',)

        if self.fecha_inicio and self.fecha_fin:
            if self.lines:
                res['lines']['remove'] = [x['id'] for x in self.lines]

            if self.bodega != None:
                if self.vendedor != None:
                    if self.lista_precio != None:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('employee', '=', self.vendedor), ('price_list', '=', self.lista_precio), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('employee', '=', self.vendedor), ('price_list', '=', self.lista_precio)])
                    else:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('employee', '=', self.vendedor), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('employee', '=', self.vendedor)])

                else:
                    if self.lista_precio != None:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('price_list', '=', self.lista_precio), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega), ('price_list', '=', self.lista_precio)])
                    else:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega),('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('warehouse', '=', self.bodega)])
            else:

                if self.vendedor != None:
                    if self.lista_precio != None:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('employee', '=', self.vendedor), ('price_list', '=', self.lista_precio), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('employee', '=', self.vendedor), ('price_list', '=', self.lista_precio)])
                    else:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('employee', '=', self.vendedor), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('employee', '=', self.vendedor)])

                else:
                    if self.lista_precio != None:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('price_list', '=', self.lista_precio), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin),('price_list', '=', self.lista_precio)])
                    else:
                        if self.cliente != None:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin), ('party', '=', self.cliente)])
                        else:
                            sales = Sale.search([('sale_date', '>=', self.fecha_inicio), ('sale_date', '<=', self.fecha_fin)])

            for sale in sales:
                if sale.state == "draft":
                    pass
                elif sale.devolucion == True:
                    pass
                else:
                    invoices = Invoice.search([('description','=',sale.reference), ('description', '!=', None),('type', '=', 'out_invoice'), ('state', '!=', 'draft')])
                    for i in invoices:
                        invoice = i

                    for l in sale.lines:
                        if self.tipo:
                            if self.categoria:
                                if self.marca:
                                    if self.tipo == l.product.template.type and self.categoria == l.product.template.category and self.marca == l.product.template.brand:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock': stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad':utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total

                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                                else:
                                    if self.tipo == l.product.template.type and self.categoria == l.product.template.category:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock': stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad':utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                            else:
                                if self.marca:
                                    if self.tipo == l.product.template.type and self.marca == l.product.template.brand:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock': stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad':utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                                else:
                                    if self.tipo == l.product.template.type:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock': stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad':utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                        else:
                            if self.categoria:
                                if self.marca:
                                    if self.categoria == l.product.template.category and self.marca == l.product.template.brand:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock': stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad':utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                                else:
                                    if self.categoria == l.product.template.category:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock':stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad':utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                            else:
                                if self.marca:
                                    if self.marca == l.product.template.brand:
                                        costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                        if costo_total > Decimal(0.0):
                                            utilidad = ((l.amount - costo_total)*100)/costo_total
                                        else:
                                            utilidad = Decimal(100)
                                        stock_individual = 0
                                        if self.bodega:
                                            location_ids = [self.bodega.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                    grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual = valor
                                        else:
                                            Location = Pool().get('stock.location')
                                            locations = Location.search([('type','=', 'warehouse')])
                                            for location in locations:
                                                location_ids = [location.id]
                                                cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                                for clave, valor in cantidad_bodega.iteritems():
                                                    stock_individual += valor
                                        cubo_line = {
                                            'codigo': l.product.code,
                                            'item': l.product.template.name,
                                            'cantidad': l.quantity,
                                            'cajas': 0,
                                            'stock':stock_individual,
                                            'total': l.amount,
                                            'costo_total': costo_total,
                                            'utilidad':utilidad,
                                            'factura':invoice.number
                                        }
                                        cantidad +=  l.quantity
                                        cajas += 0
                                        stock += stock_individual
                                        total_sumatoria += l.amount
                                        costo_total_sumatoria += costo_total
                                        res['lines'].setdefault('add', []).append((0, cubo_line))
                                else:
                                    costo_total = (l.product.template.cost_price)*Decimal(l.quantity)
                                    if costo_total > Decimal(0.0):
                                        utilidad = ((l.amount - costo_total)*100)/costo_total
                                    else:
                                        utilidad = Decimal(100)
                                    stock_individual = 0
                                    if self.bodega:
                                        location_ids = [self.bodega.id]
                                        cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,
                                                grouping=grouping)
                                        for clave, valor in cantidad_bodega.iteritems():
                                            stock_individual = valor
                                    else:
                                        Location = Pool().get('stock.location')
                                        locations = Location.search([('type','=', 'warehouse')])
                                        for location in locations:
                                            location_ids = [location.id]
                                            cantidad_bodega = l.product.products_by_location(location_ids=location_ids, product_ids=[l.product.id], with_childs=True,grouping=grouping)
                                            for clave, valor in cantidad_bodega.iteritems():
                                                stock_individual += valor
                                    cubo_line = {
                                        'codigo': l.product.code,
                                        'item': l.product.template.name,
                                        'cantidad': l.quantity,
                                        'cajas': 0,
                                        'stock':stock_individual,
                                        'total': l.amount,
                                        'costo_total': costo_total,
                                        'utilidad':utilidad,
                                        'factura':invoice.number
                                    }
                                    cantidad +=  l.quantity
                                    cajas += 0
                                    stock += stock_individual
                                    total_sumatoria += l.amount
                                    costo_total_sumatoria += costo_total
                                    res['lines'].setdefault('add', []).append((0, cubo_line))
            res['cantidad'] = cantidad
            res['cajas'] = cajas
            res['stock'] = stock
            res['total'] = total_sumatoria
            res['costo_total'] = costo_total_sumatoria
            return res
        else:
            return res

    @fields.depends('cantidad','cajas','stock','total','costo_total','lines')
    def on_change_lines(self):
        pool = Pool()
        cantidad = 0
        cajas = 0
        stock = 0
        total_sumatoria = 0
        costo_total_sumatoria = 0
        grouping=('product',)
        res = {}
        if self.lines:
            for line in self.lines:
                cantidad +=  line.cantidad
                cajas += line.cajas
                stock += line.stock
                total_sumatoria += line.total
                costo_total_sumatoria += line.costo_total

            res['cantidad'] = cantidad
            res['cajas'] = cajas
            res['stock'] = stock
            res['total'] = total_sumatoria
            res['costo_total'] = costo_total_sumatoria
        return res

class CuboVentaLineas(ModelSQL, ModelView):
    'Cubo Venta Lineas'
    __name__ = 'account.cubo_venta_lineas'

    cubo_ref = fields.Many2One('account.cubo_venta', 'Cubo')
    codigo = fields.Char("Codigo")
    item = fields.Char("Item")
    cantidad = fields.Float('Cantidad')
    cajas = fields.Float('Cajas')
    stock = fields.Float('Stock')
    total = fields.Numeric('Total')
    costo_total = fields.Numeric('Costo Total')
    utilidad = fields.Numeric('Utilidad')
    factura = fields.Char('Factura')
    fecha = fields.Date('Fecha')

    @classmethod
    def __setup__(cls):
        super(CuboVentaLineas, cls).__setup__()

class CuboVentaReport(Report):
    __name__ = 'nodux_reports.report_cubo_venta'

    @classmethod
    def parse(cls, report, records, data, localcontext):
        pool = Pool()
        User = pool.get('res.user')
        user = User(Transaction().user)
        CuboVentas = pool.get('account.cubo_venta')
        cubo_ventas = records[0]

        localcontext['user'] = user
        localcontext['company'] = user.company
        localcontext['fecha_inicio'] = cubo_ventas.fecha_inicio
        localcontext['fecha_fin'] = cubo_ventas.fecha_fin
        localcontext['bodega'] = cubo_ventas.bodega
        localcontext['usuario'] = cubo_ventas.usuario
        localcontext['vendedor'] = cubo_ventas.vendedor
        localcontext['country'] = cubo_ventas.country
        localcontext['zona'] = cubo_ventas.zona
        localcontext['cliente'] = cubo_ventas.cliente
        localcontext['marca'] = cubo_ventas.marca
        localcontext['lista_precio'] = cubo_ventas.lista_precio
        localcontext['categoria'] = cubo_ventas.categoria
        localcontext['tipo'] = cubo_ventas.tipo
        localcontext['lines'] = cubo_ventas.lines
        localcontext['cantidad'] = cubo_ventas.cantidad
        localcontext['cajas'] = cubo_ventas.cajas
        localcontext['stock'] = cubo_ventas.stock
        localcontext['total'] = cubo_ventas.total
        localcontext['costo_total'] = cubo_ventas.costo_total

        return super(CuboVentaReport, cls).parse(report, records, data,
                localcontext=localcontext)

class PrintWithholdingOutStart(ModelView):
    'Print Withholding Out Start'
    __name__ = 'nodux_reports.print_withholding_out.start'
    company = fields.Many2One('company.company', 'Company', required=True)
    date_start = fields.Date("Fecha Inicio", required= True)
    date_end = fields.Date("Fecha Fin", required= True)
    tipo = fields.Selection(TYPE_WITHHOLDING, "Tipo")

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_date_start():
        date = Pool().get('ir.date')
        date = date.today()
        return date

    @staticmethod
    def default_date_end():
        date = Pool().get('ir.date')
        date = date.today()
        return date

#crear referencias
class PrintWithholdingOut(Wizard):
    'Print Withholding Out'
    __name__ = 'nodux_reports.print_withholding_out'
    start = StateView('nodux_reports.print_withholding_out.start',
        'nodux_reports.print_withholding_out_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Print', 'print_', 'tryton-print', default=True),
            ])
    print_ = StateAction('nodux_reports.report_withholding_out')

    def do_print_(self, action):
        data = {
            'company': self.start.company.id,
            'date_start' : self.start.date_start,
            'date_end' : self.start.date_end,
            'tipo' : self.start.tipo
        }
        return action, data

    def transition_print_(self):
        return 'end'

class ReportWithholdingOut(Report):
    'Report Withholding Out'
    __name__ = 'nodux_reports.report_withholding_out'

    @classmethod
    def parse(cls, report, objects, data, localcontext):
        pool = Pool()
        User = pool.get('res.user')
        user = User(Transaction().user)
        Date = pool.get('ir.date')
        Company = pool.get('company.company')
        Withholding = pool.get('account.withholding')
        Move = pool.get('account.move')
        MoveLine = pool.get ('account.move.line')
        Invoice = pool.get('account.invoice')
        fecha = data['date_start']
        fecha_fin = data['date_end']
        company = Company(data['company'])
        total_retencion =  Decimal(0.0)
        tipo = data['tipo']

        withholdings = Withholding.search([('withholding_date', '>=', fecha), ('withholding_date', '<=', fecha_fin), ('type', '=', 'out_withholding')])

        for w in withholdings:
            for tax in w.taxes:
                if tax.tax.code_electronic:
                    pass
                else:
                    w.raise_user_error(u"No ha configurado el codigo del impuesto %s \n Dirijase a: \n Configuracion, Impuestos, Impuestos, Pestaña Codigo", tax.tax.description)
            total_retencion += w.total_amount2

        if company.timezone:
            timezone = pytz.timezone(company.timezone)
            dt = datetime.now()
            hora = datetime.astimezone(dt.replace(tzinfo=pytz.utc), timezone)

        localcontext['company'] = company
        localcontext['fecha'] = fecha.strftime('%d/%m/%Y')
        localcontext['fecha_fin'] = fecha_fin.strftime('%d/%m/%Y')
        localcontext['hora'] = hora.strftime('%H:%M:%S')
        localcontext['fecha_im'] = hora.strftime('%d/%m/%Y')
        localcontext['total_retencion'] = total_retencion
        localcontext['withholdings'] = withholdings
        localcontext['tipo'] = tipo


        return super(ReportWithholdingOut, cls).parse(report, objects, data, localcontext)
