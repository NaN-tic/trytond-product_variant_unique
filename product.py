# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import If, Eval
from trytond.transaction import Transaction
from trytond.modules.product.product import STATES, DEPENDS
from trytond.i18n import gettext
from trytond.exceptions import UserError

__all__ = ['Template', 'Product', 'OpenBOMTree', 'OpenReverseBOMTree']

UNIQUE_STATES = STATES.copy()
UNIQUE_STATES.update({
        'invisible': ~Eval('unique_variant', False)
        })


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'

    unique_variant = fields.Boolean('Unique variant')
    code = fields.Function(fields.Char("Code", states=UNIQUE_STATES,
            depends=DEPENDS + ['unique_variant']),
        'get_code', searcher='search_code')

    @classmethod
    def __setup__(cls):
        super(Template, cls).__setup__()
        pool = Pool()
        Product = pool.get('product.product')
        cls.products.size = If(Eval('unique_variant', False), 1, 9999999)
        cls.products.depends += ['unique_variant']
        if hasattr(Product, 'attributes_string'):
            # Extra dependency with product_attribute_search
            cls.attributes_string = fields.Function(fields.Char('Attributes'),
                'get_attributes_string', searcher='search_attributes_string')

    @staticmethod
    def default_unique_variant():
        pool = Pool()
        Config = pool.get('product.configuration')
        config = Config.get_singleton()
        if config:
            return config.unique_variant

    def get_rec_name(self, name):
        res = super(Template, self).get_rec_name(name)
        if self.code:
            res = '[%s] %s' % (self.code, res)
        return res

    @classmethod
    def search_rec_name(cls, name, clause):
        return ['OR', super(Template, cls).search_rec_name(name, clause),
            [('code',) + tuple(clause[1:])]]

    @classmethod
    def get_code(cls, templates, name):
        with Transaction().set_context(active_test=False):
            result = {}.fromkeys([x.id for x in templates], None)
            for template in cls.browse(templates):
                if template.unique_variant:
                    for product in template.products:
                        if product.code and product.active:
                            result[template.id] = product.code
                            break
        return result

    @classmethod
    def search_code(cls, name, clause):
        return [
            ('unique_variant', '=', True),
            ('products.code',) + tuple(clause[1:]),
            ]

    @staticmethod
    def order_code(tables):
        pool = Pool()
        Product = pool.get('product.product')
        table, _ = tables[None]
        product_table = tables.get('product')
        if product_table is None:
            product = Product.__table__()
            product_table = {
                None: (product, (product.template == table.id) &
                    table.unique_variant),
                }
            tables['product'] = product_table
        table, _ = product_table[None]
        return [table.code]

    @classmethod
    def get_attributes_string(cls, templates, name):
        result = {}.fromkeys([x.id for x in templates], '')
        for template in templates:
            if template.unique_variant and template.products:
                result[template.id] = template.products[0].attributes_string
        return result

    @classmethod
    def search_attributes_string(cls, name, clause):
        return [
            ('unique_variant', '=', True),
            ('products.attributes_string',) + tuple(clause[1:]),
            ]

    @classmethod
    def validate(cls, templates):
        pool = Pool()
        Product = pool.get('product.product')
        products = []
        for template in templates:
            if template.unique_variant and template.products:
                products.append(template.products[0])
        if products:
            Product.validate_unique_template(products)
        super(Template, cls).validate(templates)

    @classmethod
    def write(cls, *args):
        pool = Pool()
        Product = pool.get('product.product')

        to_active_products = []
        to_deactive_products = []
        actions = iter(args)
        for templates, values in zip(actions, actions):
            if 'active' in values:
                for template in templates:
                    if template.unique_variant:
                        with Transaction().set_context(active_test=False):
                            template, = cls.browse([template.id])
                            if values['active']:
                                to_active_products += [p
                                    for p in template.products]
                            else:
                                to_deactive_products += [p
                                    for p in template.products if p.active]
        super(Template, cls).write(*args)

        product_args = []
        if to_active_products:
            product_args.extend((to_active_products, {'active': True}))
        if to_deactive_products:
            product_args.extend((to_deactive_products, {'active': False}))
        if product_args:
            Product.write(*product_args)


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'

    unique_variant = fields.Function(fields.Boolean('Unique variant'),
        'on_change_with_unique_variant', searcher='search_unique_variant')

    @classmethod
    def __setup__(cls):
        super(Product, cls).__setup__()

        if not cls.active.states:
            cls.active.states = {}
        if cls.active.states.get('invisible'):
            cls.active.states['invisible'] = (cls.active.states['invisible']
                | Eval('unique_variant', False))
        else:
            cls.active.states['invisible'] = Eval('unique_variant', False)
        if 'unique_variant' not in cls.active.depends:
            cls.active.depends.append('unique_variant')

    @fields.depends('_parent_template.unique_variant', 'template')
    def on_change_with_unique_variant(self, name=None):
        if self.template:
            return self.template.unique_variant

    @classmethod
    def search_unique_variant(cls, name, clause):
        return [
            ('template.unique_variant',) + tuple(clause[1:]),
            ]

    @classmethod
    def validate(cls, products):
        cls.validate_unique_template(products)
        super(Product, cls).validate(products)

    @classmethod
    def validate_unique_template(cls, products):
        unique_products = list(set(p for p in products if p.unique_variant))
        templates = [p.template.id for p in unique_products]
        if len(set(templates)) != len(templates):
            raise UserError(gettext('product_variant_unique.template_uniq'))
        if cls.search([
                    ('id', 'not in', [p.id for p in unique_products]),
                    ('template', 'in', templates),
                    ], limit=1):
            raise UserError(gettext('product_variant_unique.template_uniq'))


class OpenReverseBOMTree(metaclass=PoolMeta):
    __name__ = 'production.bom.reverse_tree.open'

    def do_start(self, action):
        Template = Pool().get('product.template')
        context = Transaction().context
        new_context = {}
        if context['active_model'] == 'product.template':
            template = Template(context['active_id'])
            if not template.products:
                raise UserError(gettext(
                    'product_variant_unique.not_product_variant',
                    template=template.rec_name))
            product_id = template.products[0].id
            new_context.update({
                    'active_model': 'product.product',
                    'active_id': product_id,
                    'active_ids': [product_id],
                    })
            action['res_model'] = 'product.product'
            action['active_id'] = product_id
        with Transaction().set_context(**new_context):
            return super(OpenReverseBOMTree, self).do_start(action)


class OpenBOMTree(metaclass=PoolMeta):
    __name__ = 'production.bom.tree.open'

    def default_start(self, fields):
        Template = Pool().get('product.template')

        context = Transaction().context

        new_context = {}
        if context['active_model'] == 'product.template':
            template = Template(context['active_id'])
            if not template.products:
                raise UserError(gettext(
                    'product_variant_unique.not_product_variant',
                        template=template.rec_name))
            product_id = template.products[0].id
            new_context.update({
                    'active_model': 'product.product',
                    'active_id': product_id,
                    'active_ids': [product_id],
                    })
        with Transaction().set_context(**new_context):
            return super(OpenBOMTree, self).default_start(fields)
