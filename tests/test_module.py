
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.exceptions import UserError


class ProductVariantUniqueTestCase(ModuleTestCase):
    'Test ProductVariantUnique module'
    module = 'product_variant_unique'

    @with_transaction()
    def test_unique_variant(self):
        pool = Pool()
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        Uom = pool.get('product.uom')
        kg, = Uom.search([('name', '=', 'Kilogram')])
        template, uniq_template = Template.create([{
                    'name': 'Test variant',
                    'type': 'goods',
                    'cost_price_method': 'fixed',
                    'default_uom': kg.id,
                    'products': [('create', [{
                                    'suffix_code': '1',
                                    }])]
                    }, {
                    'name': 'Test unique variant',
                    'type': 'goods',
                    'cost_price_method': 'fixed',
                    'default_uom': kg.id,
                    'unique_variant': True,
                    'products': [('create', [{
                                    'suffix_code': '2',
                                    }])]
                    }])
        products = Product.search([])
        self.assertEqual(len(products), 2)
        self.assertIsNone(template.code)
        self.assertEqual(sorted(p.code for p in products), ['1', '2'])

        with self.assertRaises(UserError) as cm:
            Product.create([{
                        'code': '1',
                        'template': uniq_template.id,
                        }, {
                        'code': '2',
                        'template': uniq_template.id,
                        }])
        self.assertEqual(cm.exception.message,
            'The Template of the Product Variant must be unique.')

        with self.assertRaises(UserError) as cm:
            Product.create([{
                        'code': '3',
                        'template': uniq_template.id,
                        }])
        self.assertEqual(cm.exception.message,
            'The Template of the Product Variant must be unique.')


del ModuleTestCase
