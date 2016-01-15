# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from .configuration import *
from .product import *


def register():
    Pool.register(
        Configuration,
        Template,
        Product,
        module='product_variant_unique', type_='model')
    Pool.register(
        ProductByLocation,
        OpenProductQuantitiesByWarehouse,
        OpenBOMTree,
        module='product_variant_unique', type_='wizard')
