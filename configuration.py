# This file is part product_variant module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta

__all__ = ['Configuration']


class Configuration(metaclass=PoolMeta):
    __name__ = 'product.configuration'
    unique_variant = fields.Boolean('Unique variant', help='Default value'
        ' for the unique variant field in template form.')
