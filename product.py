# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import If, Eval
from trytond.transaction import Transaction
from trytond.i18n import gettext
from trytond.exceptions import UserError

__all__ = ['Template', 'Product', 'OpenBOMTree', 'OpenReverseBOMTree']

UNIQUE_STATES = {
        'invisible': ~Eval('unique_variant', False)
        }


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'
    unique_variant = fields.Boolean('Unique variant')

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


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'
    unique_variant = fields.Function(fields.Boolean('Unique variant'),
        'on_change_with_unique_variant', searcher='search_unique_variant')

    @classmethod
    def __setup__(cls):
        super(Product, cls).__setup__()

        if 'unique_variant' not in cls.active.depends:
            cls.active.depends.append('unique_variant')

        if not cls.suffix_code.states:
            cls.suffix_code.states = {}
        if cls.suffix_code.states.get('readonly'):
            cls.suffix_code.states['readonly'] = (
                cls.suffix_code.states['readonly']
                | Eval('unique_variant', False))
        else:
            cls.suffix_code.states['readonly'] = Eval('unique_variant', False)
        if 'unique_variant' not in cls.suffix_code.depends:
            cls.suffix_code.depends.append('unique_variant')

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
        active_id = context.get('active_id')
        if active_id and context['active_model'] == 'product.template':
            template = Template(active_id)
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
