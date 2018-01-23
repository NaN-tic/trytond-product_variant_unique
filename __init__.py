# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from . import configuration
from . import product


def register():
    Pool.register(
        configuration.Configuration,
        product.Template,
        product.Product,
        module='product_variant_unique', type_='model')
    Pool.register(
        product.OpenBOMTree,
        module='product_variant_unique', type_='wizard')
