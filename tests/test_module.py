
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from decimal import Decimal

from trytond.modules.company.tests import create_company, set_company
from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.exceptions import UserError


class ProductVariantUniqueTestCase(ModuleTestCase):
    'Test ProductVariantUnique module'
    module = 'product_variant_unique'
    extras = ['production_reverse_bom']

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

    @with_transaction()
    def test_set_list_price_used(self):
        pool = Pool()
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        ListPrice = pool.get('product.list_price')
        Uom = pool.get('product.uom')

        company = create_company()
        with set_company(company):
            kg, = Uom.search([('name', '=', 'Kilogram')])
            template, uniq_template = Template.create([{
                        'name': 'Template Price',
                        'type': 'goods',
                        'cost_price_method': 'fixed',
                        'default_uom': kg.id,
                        'unique_variant': False,
                        'products': [('create', [{
                                        'suffix_code': 'T1',
                                        }])],
                        }, {
                        'name': 'Variant Price',
                        'type': 'goods',
                        'cost_price_method': 'fixed',
                        'default_uom': kg.id,
                        'unique_variant': True,
                        'products': [('create', [{
                                        'suffix_code': 'V1',
                                        }])],
                        }])
            product, = template.products
            uniq_product, = uniq_template.products

            Product.write([product], {
                    'list_price_used': Decimal('10'),
                    })
            Product.write([uniq_product], {
                    'list_price_used': Decimal('20'),
                    })

            template = Template(template.id)
            uniq_template = Template(uniq_template.id)
            product = Product(product.id)
            uniq_product = Product(uniq_product.id)
            template_prices = ListPrice.search([
                    ('template', '=', template.id),
                    ])
            uniq_product_prices = ListPrice.search([
                    ('template', '=', uniq_template.id),
                    ])

            self.assertEqual(len(template_prices), 1)
            self.assertEqual(template_prices[0].product, product)
            self.assertEqual(template_prices[0].list_price, Decimal('10'))
            self.assertEqual(product.list_price_used, Decimal('10'))

            self.assertEqual(len(uniq_product_prices), 1)
            self.assertIsNone(uniq_product_prices[0].product)
            self.assertEqual(uniq_product_prices[0].list_price,
                Decimal('20'))
            self.assertEqual(uniq_product.list_price_used, Decimal('20'))


del ModuleTestCase
