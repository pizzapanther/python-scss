from scss.base import Node, Empty, ParseNode, warn
from scss.function import FUNCTION, unknown
from scss.value import Variable, NumberValue, BooleanValue


class VarDef(ParseNode, Empty):
    """ Variable definition.
    """
    def __init__(self, t, s):
        super(VarDef, self).__init__(t, s)
        self.name, self.expression, self.default = t[0], t[1], len(t) > 2
        self.value = self.expression
        self.root.set_var(self)

    def copy(self, ctx=None):
        if isinstance(self.expression, Variable):
            self.expression.ctx = ctx
        self.root.set_var(self)
        return self


class FunctionDefinition(Empty):
    def __init__(self, t, s):
        super(FunctionDefinition, self).__init__(t, s)
        self.name, self.params, self.body = t[1], t[2], t[3:]
        s.cache['fnc'][self.name] = self
        FUNCTION['%s:%s' % (self.name, len(self.params))] = self.wrapper

    def wrapper(self, *args, **kwargs):
        ctx = Mixin.get_context(self.params, args)
        map(lambda e:e.copy(ctx) if isinstance(e, ParseNode) else e, self.body)
        return self.body[-1]


class Mixin(ParseNode, Empty):
    """ @mixin class.
    """
    def __init__(self, t, s=None):
        super(Mixin, self).__init__(t, s)
        s.cache['mix'][t[1]] = self

    @staticmethod
    def get_context(defined, params):
        test = map(lambda x, y: (x, y), defined, params)
        return dict(( mp.name, v or mp.default ) for mp, v in test if mp)

    def include(self, target, params):
        if isinstance(target, Mixin):
            return

        ctx = self.get_context(getattr(self, 'mixinparam', []), params)
        for e in self.data:
            if isinstance(e, ParseNode):
                node = e.copy(ctx)
                node.parse(target)


class Include(ParseNode):
    """ @include
    """
    def __init__(self, t, s):
        super(Include, self).__init__(t, s)
        self.name, self.params = t[1], t[2:]

    def __str__(self):
        node = Node(tuple())
        if self.parse(node) and hasattr(node, 'ruleset'):
            return ''.join( r.__str__() for r in getattr(node, 'ruleset') )

        if self.root.get_opt('warn'):
            warn("Required mixin not found: %s:%d." % ( self.name, len(self.params)))
        return ''

    def parse(self, target):
        mixin = self.root.cache['mix'].get(self.name)
        if mixin:
            mixin.include(target, self.params)
            return True
        return False


class Extend(ParseNode):
    """ @extend at rule.
    """
    def parse(self, target):
        name = str(self.data[1])
        rulesets = self.root.cache['rset'].get(name)
        if rulesets:
            for rul in rulesets:
                for sg in target.selectorgroup:
                    rul.selectorgroup.append(sg.increase(rul.selectorgroup[0]))
        elif self.root.get_opt('warn'):
            warn("Ruleset for extend not found: %s" % name)


class Function(Variable):
    def __init__(self, t, s):
        super(Function, self).__init__(t, s)
        self.name, self.params = self.data[0], self.data[1:]

    @property
    def value(self):
        return self.__parse(self.ctx)

    def copy(self, ctx=None):
        return self.__parse(ctx)

    def __parse(self, ctx=None):
        func_name_a = "%s:%d" % (self.name, len(self.params))
        func_name_n = "%s:n" % self.name
        params = list()
        for value in self.params:
            while isinstance(value, Variable):
                value.ctx = ctx
                value = value.value
            params.append(value)
        func = FUNCTION.get(func_name_a) or FUNCTION.get(func_name_n)
        return func(*params, root=self.root) if func else unknown(self.name, *params)

    def __str__(self):
        return str(self.__parse())


class IfNode(ParseNode):
    def_else = Node([])

    def __init__(self, t, s):
        super(IfNode, self).__init__(t, s)
        self.cond, self.body, self.els = t[0], t[1], t[2] if len(t)>2 else self.def_else

    def __str__(self):
        return str(self.get_node())

    def get_node(self):
        return self.body if BooleanValue(self.cond).value else self.els

    def parse(self, target):
        if not isinstance(target, ( Mixin, Function )):
            node = self.get_node()
            for n in node.data:
                if isinstance(n, ParseNode):
                    n.parse(target)


class ForNode(ParseNode):
    def __init__(self, t, s):
        super(ForNode, self).__init__(t, s)
        self.var, self.first, self.second, self.body = t[1:]

    def copy(self, ctx=None):
        return self

    def __parse(self):
        name = self.var.data[0][1:]
        for i in xrange(int(float( self.first )), int(float( self.second ))+1):
            yield self.body.copy({name: NumberValue(i)})

    def __str__(self):
        return ''.join(str(n) for n in self.__parse())

    def parse(self, target):
        if not isinstance(target, ( Mixin, Function )):
            for node in self.__parse():
                for n in node.data:
                    if hasattr(n, 'parse'):
                        n.parse(target)
