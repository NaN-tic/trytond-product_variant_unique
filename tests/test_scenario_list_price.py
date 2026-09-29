import unittest
from decimal import Decimal

from proteus import Model
from trytond.modules.company.tests.tools import create_company
from trytond.tests.test_tryton import drop_db
from trytond.tests.tools import activate_modules


class Test(unittest.TestCase):

    def setUp(self):
        drop_db()
        super().setUp()

    def tearDown(self):
        drop_db()
        super().tearDown()

    def test(self):
        activate_modules('product_variant_unique')
        create_company()

        Uom = Model.get('product.uom')
        Template = Model.get('product.template')
        unit, = Uom.find([('name', '=', 'Unit')])
        template = Template()
        template.name = 'Unique Variant Price'
        template.default_uom = unit
        template.type = 'goods'
        template.cost_price_method = 'fixed'
        template.list_price = Decimal('256')
        template.unique_variant = True
        product, = template.products
        product.list_price_used = None
        template.save()

        template.reload()
        self.assertEqual(template.list_price, Decimal('256'))
