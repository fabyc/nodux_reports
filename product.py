#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import datetime
from decimal import Decimal
from sql import Literal
from sql.aggregate import Max
from sql.functions import Now
from sql.conditionals import Coalesce

from trytond.model import ModelSQL, ModelView, fields
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.pyson import PYSONEncoder, Eval, Or
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta
from trytond.tools import grouped_slice

__all__ = ['Product']
__metaclass__ = PoolMeta

class Product():
    __name__ = "product.product"

    @classmethod
    def products_by_location(cls, location_ids, product_ids=None,
            with_childs=False, grouping=('product',)):
        """
        Compute for each location and product the stock quantity in the default
        uom of the product.

        The context with keys:
            stock_skip_warehouse: if set, quantities on a warehouse are no more
                quantities of all child locations but quantities of the storage
                zone.

        Return a dictionary with location id and grouping as key
                and quantity as value.
        """
        pool = Pool()
        Location = pool.get('stock.location')
        Move = pool.get('stock.move')

        # Skip warehouse location in favor of their storage location
        # to compute quantities. Keep track of which ids to remove
        # and to add after the query.
        storage_to_remove = set()
        wh_to_add = {}
        if Transaction().context.get('stock_skip_warehouse'):
            location_ids = set(location_ids)
            for location in Location.browse(list(location_ids)):
                if location.type == 'warehouse':
                    location_ids.remove(location.id)
                    if location.storage_location.id not in location_ids:
                        storage_to_remove.add(location.storage_location.id)
                    location_ids.add(location.storage_location.id)
                    wh_to_add[location.id] = location.storage_location.id
            location_ids = list(location_ids)

        grouping_filter = (product_ids,) + tuple(None for k in grouping[1:])
        query = Move.compute_quantities_query(location_ids, with_childs,
            grouping=grouping, grouping_filter=grouping_filter)
        if query is None:
            return {}
        quantities = Move.compute_quantities(query, location_ids, with_childs,
            grouping=grouping, grouping_filter=grouping_filter)

        if wh_to_add:
            for wh, storage in wh_to_add.iteritems():
                for key in quantities:
                    if key[0] == storage:
                        quantities[(wh,) + key[1:]] = quantities[key]
                        if storage in storage_to_remove:
                            del quantities[key]
        return quantities
