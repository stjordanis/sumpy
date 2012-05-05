from __future__ import division

import numpy as np
import pyopencl as cl
import pyopencl.tools

import re

from pymbolic.mapper import IdentityMapper
import pymbolic.primitives as prim

from pytools import memoize_method


# {{{ hankel handling

import sumpy.hank103

HANKEL_PREAMBLE = sumpy.hank103.CODE+"""//CL//
typedef struct hank1_01_result_str
{
    cdouble_t order0, order1;
} hank1_01_result;

hank1_01_result hank1_01(cdouble_t z)
{
    hank1_01_result result;
    hank103(z, &result.order0, &result.order1, /*ifexpon*/ 1);
    return result;
}
"""

hank1_01_result_dtype = np.dtype([
    ("order0", np.complex128),
    ("order1", np.complex128),
    ])
cl.tools.register_dtype(hank1_01_result_dtype,
        "hank1_01_result")



class HankelGetter(object):
    @memoize_method
    def hank1_01(self, arg):
        from loopy.symbolic import TypedCSE
        return TypedCSE(
                prim.Variable("hank1_01")(arg),
                dtype=hank1_01_result_dtype)

    @memoize_method
    def hank1(self, order, arg):
        from loopy.symbolic import TypedCSE
        if order == 0:
            return TypedCSE(
                    prim.Lookup(self.hank1_01(arg), "order0"),
                    dtype=np.complex128)
        elif order == 1:
            return TypedCSE(
                    prim.Lookup(self.hank1_01(arg), "order1"),
                    dtype=np.complex128)
        elif order < 0:
            # AS (9.1.6)
            nu = -order
            return prim.wrap_in_cse(
                    (-1)**nu * self.hank1(nu, arg),
                    "hank1_neg%d" % nu)
        elif order > 1:
            # AS (9.1.27)
            nu = order-1
            return prim.CommonSubexpression(
                    2*nu/arg*self.hank1(nu, arg)
                    - self.hank1(nu-1, arg),
                    "hank1_%d" % order)
        else:
            assert False

    @memoize_method
    def hank1_deriv(self, order, arg, n_derivs):
        # AS (9.1.31)
        k = n_derivs
        nu = order
        from pytools import comb
        return prim.CommonSubexpression(
                2**(-k)*sum(
                    (-1)**idx*int(comb(k, idx)) * self.hank1(i, arg)
                    for idx, i in enumerate(range(nu-k, nu+k+1, 2))),
                "d%d_hank1_%d" % (n_derivs, order))





class HankelSubstitutor(IdentityMapper):
    def __init__(self, hank_getter):
        self.hank_getter = hank_getter

    def map_call(self, expr):
        if isinstance(expr.function, prim.Variable) and expr.function.name == "hankel_1":
            hank_order, hank_arg = expr.parameters
            result = self.hank_getter.hank1(hank_order, hank_arg)
            return result
        else:
            return IdentityMapper.map_call(self, expr)

# }}}




class PowerRewriter(IdentityMapper):
    def map_power(self, expr):
        exp = expr.exponent
        if isinstance(exp, int):
            new_base = prim.wrap_in_cse(expr.base)

            if exp > 1:
                return self.rec(prim.wrap_in_cse(new_base**(exp-1))*new_base)
            elif exp == 1:
                return new_base
            elif exp < 0:
                return self.rec((1/new_base)**(-exp))

        if (isinstance(expr.exponent, prim.Quotient)
                and isinstance(expr.exponent.numerator, int)
                and isinstance(expr.exponent.denominator, int)):

            p, q = expr.exponent.numerator, expr.exponent.denominator
            if q < 0:
                q *= -1
                p *= -1

            if q == 1:
                return self.rec(new_base**p)

            if q == 2:
                assert p != 0

                if p > 0:
                    orig_base = prim.wrap_in_cse(expr.base)
                    new_base = prim.wrap_in_cse(
                            prim.Variable("rsqrt")(orig_base) * orig_base)
                else:
                    new_base = prim.wrap_in_cse(prim.Variable("rsqrt")(expr.base))
                    p *= -1

                return self.rec(new_base**p)

        return IdentityMapper.map_power(self, expr)





class FractionKiller(IdentityMapper):
    def map_quotient(self, expr):
        num = expr.numerator
        denom = expr.denominator

        if isinstance(num, int) and isinstance(denom, int):
            if num % denom == 0:
                return num // denom
            return int(expr.numerator) / int(expr.denominator)

        return IdentityMapper.map_quotient(self, expr)




INDEXED_VAR_RE = re.compile("^([a-zA-Z_]+)([0-9]+)$")

class VectorComponentRewriter(IdentityMapper):
    def map_variable(self, expr):
        match_obj = INDEXED_VAR_RE.match(expr.name)
        if match_obj is not None:
            return prim.Variable(match_obj.group(1))[int(match_obj.group(2))]
        else:
            return IdentityMapper.map_variable(self, expr)




class MathConstantRewriter(IdentityMapper):
    def map_variable(self, expr):
        if expr.name == "pi":
            return prim.Variable("M_PI")
        else:
            return IdentityMapper.map_variable(self, expr)





def prepare_for_code(exprs):
    unwrap = False
    if not isinstance(exprs, (list, tuple)):
        exprs = [exprs]
        unwrap = True

    exprs = [HankelSubstitutor(HankelGetter())(expr) for expr in exprs]
    exprs = [VectorComponentRewriter()(expr) for expr in exprs]
    exprs = [PowerRewriter()(expr) for expr in exprs]
    exprs = [FractionKiller()(expr) for expr in exprs]
    exprs = [MathConstantRewriter()(expr) for expr in exprs]

    from pymbolic.cse import tag_common_subexpressions
    exprs = tag_common_subexpressions(exprs)

    if unwrap:
        exprs, = exprs

    return exprs
