#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .account import *

def register():
    Pool.register(
        PrintCloseCashStart,
        PrintSalesmanStart,
        PrintMoveAllStart,
        PrintAccountReceivable,
        CuboVenta,
        CuboVentaLineas,
        PrintWithholdingOutStart,
        module='nodux_reports', type_='model')
    Pool.register(
        PrintCloseCash,
        PrintSalesman,
        PrintMoveAll,
        AccountReceivable,
        PrintWithholdingOut,
        module='nodux_reports', type_='wizard')
    Pool.register(
        CloseCash,
        ReportSalesman,
        ReportMoveAll,
        ReportAccountReceivable,
        CuboVentaReport,
        ReportWithholdingOut,
        module='nodux_reports', type_='report')
