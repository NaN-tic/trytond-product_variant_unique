# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.const import OPERATORS
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import If, Eval
from trytond.transaction import Transaction
from trytond.modules.product.product import STATES, DEPENDS

__all__ = ['Template', 'Product', 'ProductByLocation',
    'OpenProductQuantitiesByWarehouse', 'OpenBOMTree']
__metaclass__ = PoolMeta

UNIQUE_STATES = STATES.copy()
UNIQUE_STATES.update({
        'invisible': ~Eval('unique_variant', False)
        })


class Template:
    __name__ = 'product.template'

    unique_variant = fields.Boolean('Unique variant')
    code = fields.Function(fields.Char("Code", states=UNIQUE_STATES,
            depends=DEPENDS + ['unique_variant']),
        'get_code', setter='set_code', searcher='search_code')

    @classmethod
    def __setup__(cls):
        super(Template, cls).__setup__()
        pool = Pool()
        Product = pool.get('product.product')
        cls.products.size = If(Eval('unique_variant', False), 1, 9999999)
        if hasattr(Product, 'attributes_string'):
            # Extra dependency with pro
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

    def get_code(self, name):
        if self.unique_variant:
            with Transaction().set_context(active_test=False):
                return self.products and self.products[0].code or None

    @classmethod
    def set_code(cls, templates, name, value):
        Product = Pool().get('product.product')

        products = set()
        for template in templates:
            if not template.unique_variant:
                continue
            with Transaction().set_context(active_test=False):
                if template.products:
                    products.add(template.products[0])
                elif value:
                    new_product = Product(template=template)
                    new_product.save()
                    products.add(new_product)
        if products:
            Product.write(list(products), {
                    'code': value,
                    })

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
    def search_domain(cls, domain, active_test=True, tables=None):
        def find_active_code(domain):
            active_found = code_found = False
            for arg in domain:
                if (isinstance(arg, (tuple, list)) and len(arg) == 3
                        and (tuple(arg) == ('active', '=', False)
                            or (arg[0] == 'active' and arg[1] == 'in'
                                and False in arg[2]))):
                    active_found = True
                elif (isinstance(arg, tuple)
                        or (isinstance(arg, list)
                            and len(arg) > 2
                            and arg[1] in OPERATORS)):
                    if arg[0] in ('code', 'rec_name'):
                        code_found = True
                elif isinstance(arg, list):
                    active_found_rec, code_found_rec = find_active_code(arg)
                    active_found |= active_found_rec
                    code_found |= code_found_rec
                if active_found and code_found:
                    break
            return active_found, code_found

        active_found, code_found = find_active_code(domain)
        with Transaction().set_context(
                search_inactive_products=(active_found and code_found)):
            return super(Template, cls).search_domain(domain,
                active_test=active_test, tables=tables)

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
                            if values['active']:
                                to_active_products += [p
                                    for p in template.products if not p.active]
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


class Product:
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

        cls._error_messages.update({
                'template_uniq': ('The Template of the Product Variant must '
                    'be unique.'),
                })

    @fields.depends('template', '_parent_sale.unique_variant')
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
            cls.raise_user_error('template_uniq')
        if cls.search([
                    ('id', 'not in', [p.id for p in unique_products]),
                    ('template', 'in', templates),
                    ], limit=1):
            cls.raise_user_error('template_uniq')

    @classmethod
    def search_domain(cls, domain, active_test=True, tables=None):
        if Transaction().context.get('search_inactive_products'):
            active_test = False
        return super(Product, cls).search_domain(domain,
            active_test=active_test, tables=tables)


class ProductByLocation:
    __name__ = 'product.by_location'

    @classmethod
    def __setup__(cls):
        super(ProductByLocation, cls).__setup__()
        cls._error_messages.update({
                'not_unique_variant': ('The template "%s" must be marked as '
                    'unique variant in order to be able to see it\'s stock'),
                })

    def default_start(self, fields):
        Template = Pool().get('product.template')
        try:
            res = super(ProductByLocation, self).default_start(fields)
        except AttributeError:
            res = {}
        context = Transaction().context
        if context['active_model'] == 'product.template':
            template = Template(context['active_id'])
            if not template.unique_variant:
                self.raise_user_error('not_unique_variant', template.rec_name)
        return res

    def do_open(self, action):
        Template = Pool().get('product.template')

        context = Transaction().context
        if context['active_model'] == 'product.template':
            template = Template(context['active_id'])
            if not template.products:
                return None, {}
            product_id = template.products[0].id
            new_context = {
                'active_model': 'product.template',
                'active_id': product_id,
                'active_ids': [product_id],
                }
            with Transaction().set_context(new_context):
                return super(ProductByLocation, self).do_open(action)
        return super(ProductByLocation, self).do_open(action)


class OpenProductQuantitiesByWarehouse:
    __name__ = 'stock.product_quantities_warehouse'

    @classmethod
    def __setup__(cls):
        super(OpenProductQuantitiesByWarehouse, cls).__setup__()
        cls._error_messages.update({
                'not_unique_variant': ('The template "%s" must be marked as '
                    'unique variant in order to be able to see it\'s stock'),
                })

    def default_start(self, fields):
        Template = Pool().get('product.template')
        try:
            res = super(OpenProductQuantitiesByWarehouse, self).default_start(
                fields)
        except AttributeError:
            res = {}
        context = Transaction().context
        if context['active_model'] == 'product.template':
            template = Template(context['active_id'])
            if not template.unique_variant:
                self.raise_user_error('not_unique_variant', template.rec_name)
        return res

    def do_open_(self, action):
        Template = Pool().get('product.template')

        context = Transaction().context
        if context['active_model'] == 'product.template':
            template = Template(context['active_id'])
            if not template.products:
                return None, {}
            product_id = template.products[0].id
            new_context = {
                'active_model': 'product.template',
                'active_id': product_id,
                'active_ids': [product_id],
                }
            with Transaction().set_context(new_context):
                return super(OpenProductQuantitiesByWarehouse,
                    self).do_open_(action)
        return super(OpenProductQuantitiesByWarehouse, self).do_open_(action)


class OpenBOMTree:
    __name__ = 'production.bom.tree.open'

    @classmethod
    def __setup__(cls):
        super(OpenBOMTree, cls).__setup__()
        cls._error_messages.update({
                'not_product_variant': ('The template "%s" not have '
                    'a product variant.'),
                })

    def default_start(self, fields):
        Template = Pool().get('product.template')

        context = Transaction().context

        new_context = {}
        if context['active_model'] == 'product.template':
            template = Template(context['active_id'])
            if not template.products:
                self.raise_user_error('not_product_variant', template.rec_name)
            product_id = template.products[0].id
            new_context.update({
                    'active_model': 'product.product',
                    'active_id': product_id,
                    'active_ids': [product_id],
                    })
        with Transaction().set_context(**new_context):
            return super(OpenBOMTree, self).default_start(fields)
