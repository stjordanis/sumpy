from __future__ import print_function, division

__copyright__ = """
Copyright (C) 2017 Matt Wala
Copyright (C) 2006-2016 SymPy Development Team
"""

# {{{ license and original license

__license__ = """
Modifications from original are under the following license:

Copyright (C) 2017 Matt Wala

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

===========================================================================

Based on sympy/simplify/tests/test_cse.py from SymPy 1.0, license as follows:

Copyright (c) 2006-2016 SymPy Development Team

All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

  a. Redistributions of source code must retain the above copyright notice,
     this list of conditions and the following disclaimer.
  b. Redistributions in binary form must reproduce the above copyright
     notice, this list of conditions and the following disclaimer in the
     documentation and/or other materials provided with the distribution.
  c. Neither the name of SymPy nor the names of its contributors
     may be used to endorse or promote products derived from this software
     without specific prior written permission.


THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL THE REGENTS OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH
DAMAGE.
"""

# }}}

import pytest
import sys

from sympy import (Add, Pow, exp, sqrt, symbols, sympify, S, cos, sin, Eq,
                   Function, Tuple, CRootOf, IndexedBase, Idx, Piecewise)
from sympy.simplify.cse_opts import sub_pre, sub_post
from sympy.functions.special.hyper import meijerg
from sympy.simplify import cse_opts


from sumpy.cse import (
    cse, preprocess_for_cse, postprocess_for_cse)


w, x, y, z = symbols('w,x,y,z')
x0, x1, x2, x3, x4, x5, x6, x7, x8, x9, x10, x11, x12 = symbols('x:13')


# Dummy "optimization" functions for testing.


def opt1(expr):
    return expr + y


def opt2(expr):
    return expr*z


def test_preprocess_for_cse():
    assert preprocess_for_cse(x, [(opt1, None)]) == x + y
    assert preprocess_for_cse(x, [(None, opt1)]) == x
    assert preprocess_for_cse(x, [(None, None)]) == x
    assert preprocess_for_cse(x, [(opt1, opt2)]) == x + y
    assert preprocess_for_cse(
        x, [(opt1, None), (opt2, None)]) == (x + y)*z


def test_postprocess_for_cse():
    assert postprocess_for_cse(x, [(opt1, None)]) == x
    assert postprocess_for_cse(x, [(None, opt1)]) == x + y
    assert postprocess_for_cse(x, [(None, None)]) == x
    assert postprocess_for_cse(x, [(opt1, opt2)]) == x*z
    # Note the reverse order of application.
    assert postprocess_for_cse(
        x, [(None, opt1), (None, opt2)]) == x*z + y


def test_cse_single():
    # Simple substitution.
    e = Add(Pow(x + y, 2), sqrt(x + y))
    substs, reduced = cse([e])
    assert substs == [(x0, x + y)]
    assert reduced == [sqrt(x0) + x0**2]


def test_cse_not_possible():
    # No substitution possible.
    e = Add(x, y)
    substs, reduced = cse([e])
    assert substs == []
    assert reduced == [x + y]
    # issue 6329
    eq = (meijerg((1, 2), (y, 4), (5,), [], x) +
          meijerg((1, 3), (y, 4), (5,), [], x))
    assert cse(eq) == ([], [eq])


def test_nested_substitution():
    # Substitution within a substitution.
    e = Add(Pow(w*x + y, 2), sqrt(w*x + y))
    substs, reduced = cse([e])
    assert substs == [(x0, w*x + y)]
    assert reduced == [sqrt(x0) + x0**2]


def test_subtraction_opt():
    # Make sure subtraction is optimized.
    e = (x - y)*(z - y) + exp((x - y)*(z - y))
    substs, reduced = cse(
        [e], optimizations=[(cse_opts.sub_pre, cse_opts.sub_post)])
    assert substs == [(x0, (x - y)*(y - z))]
    assert reduced == [-x0 + exp(-x0)]
    e = -(x - y)*(z - y) + exp(-(x - y)*(z - y))
    substs, reduced = cse(
        [e], optimizations=[(cse_opts.sub_pre, cse_opts.sub_post)])
    assert substs == [(x0, (x - y)*(y - z))]
    assert reduced == [x0 + exp(x0)]
    # issue 4077
    n = -1 + 1/x
    e = n/x/(-n)**2 - 1/n/x
    assert cse(e, optimizations=[(cse_opts.sub_pre, cse_opts.sub_post)]) == \
        ([], [0])


def test_multiple_expressions():
    e1 = (x + y)*z
    e2 = (x + y)*w
    substs, reduced = cse([e1, e2])
    assert substs == [(x0, x + y)]
    assert reduced == [x0*z, x0*w]
    l = [w*x*y + z, w*y]
    substs, reduced = cse(l)
    rsubsts, _ = cse(reversed(l))
    assert substs == rsubsts
    assert reduced == [z + x*x0, x0]
    l = [w*x*y, w*x*y + z, w*y]
    substs, reduced = cse(l)
    rsubsts, _ = cse(reversed(l))
    assert substs == rsubsts
    assert reduced == [x1, x1 + z, x0]
    l = [(x - z)*(y - z), x - z, y - z]
    substs, reduced = cse(l)
    rsubsts, _ = cse(reversed(l))
    assert substs == [(x0, -z), (x1, x + x0), (x2, x0 + y)]
    assert rsubsts == [(x0, -z), (x1, x0 + y), (x2, x + x0)]
    assert reduced == [x1*x2, x1, x2]
    l = [w*y + w + x + y + z, w*x*y]
    assert cse(l) == ([(x0, w*y)], [w + x + x0 + y + z, x*x0])
    assert cse([x + y, x + y + z]) == ([(x0, x + y)], [x0, z + x0])
    assert cse([x + y, x + z]) == ([], [x + y, x + z])
    assert cse([x*y, z + x*y, x*y*z + 3]) == \
        ([(x0, x*y)], [x0, z + x0, 3 + x0*z])


def test_issue_4203():
    assert cse(sin(x**x)/x**x) == ([(x0, x**x)], [sin(x0)/x0])


def test_dont_cse_tuples():
    from sympy import Subs
    f = Function("f")
    g = Function("g")

    name_val, (expr,) = cse(
        Subs(f(x, y), (x, y), (0, 1))
        + Subs(g(x, y), (x, y), (0, 1)))

    assert name_val == []
    assert expr == (Subs(f(x, y), (x, y), (0, 1))
            + Subs(g(x, y), (x, y), (0, 1)))

    name_val, (expr,) = cse(
        Subs(f(x, y), (x, y), (0, x + y))
        + Subs(g(x, y), (x, y), (0, x + y)))

    assert name_val == [(x0, x + y)]
    assert expr == Subs(f(x, y), (x, y), (0, x0)) + \
        Subs(g(x, y), (x, y), (0, x0))


def test_pow_invpow():
    assert cse(1/x**2 + x**2) == \
        ([(x0, x**2)], [x0 + 1/x0])
    assert cse(x**2 + (1 + 1/x**2)/x**2) == \
        ([(x0, x**2), (x1, 1/x0)], [x0 + x1*(x1 + 1)])
    assert cse(1/x**2 + (1 + 1/x**2)*x**2) == \
        ([(x0, x**2), (x1, 1/x0)], [x0*(x1 + 1) + x1])
    assert cse(cos(1/x**2) + sin(1/x**2)) == \
        ([(x0, x**(-2))], [sin(x0) + cos(x0)])
    assert cse(cos(x**2) + sin(x**2)) == \
        ([(x0, x**2)], [sin(x0) + cos(x0)])
    assert cse(y/(2 + x**2) + z/x**2/y) == \
        ([(x0, x**2)], [y/(x0 + 2) + z/(x0*y)])
    assert cse(exp(x**2) + x**2*cos(1/x**2)) == \
        ([(x0, x**2)], [x0*cos(1/x0) + exp(x0)])
    assert cse((1 + 1/x**2)/x**2) == \
        ([(x0, x**(-2))], [x0*(x0 + 1)])
    assert cse(x**(2*y) + x**(-2*y)) == \
        ([(x0, x**(2*y))], [x0 + 1/x0])


def test_issue_4499():
    # previously, this gave 16 constants
    from sympy.abc import a, b
    B = Function('B')  # noqa
    G = Function('G')  # noqa
    t = Tuple(*
        (a, a + S(1)/2, 2*a, b, 2*a - b + 1, (sqrt(z)/2)**(-2*a + 1)*B(2*a -
        b, sqrt(z))*B(b - 1, sqrt(z))*G(b)*G(2*a - b + 1),
        sqrt(z)*(sqrt(z)/2)**(-2*a + 1)*B(b, sqrt(z))*B(2*a - b,
        sqrt(z))*G(b)*G(2*a - b + 1), sqrt(z)*(sqrt(z)/2)**(-2*a + 1)*B(b - 1,
        sqrt(z))*B(2*a - b + 1, sqrt(z))*G(b)*G(2*a - b + 1),
        (sqrt(z)/2)**(-2*a + 1)*B(b, sqrt(z))*B(2*a - b + 1,
        sqrt(z))*G(b)*G(2*a - b + 1), 1, 0, S(1)/2, z/2, -b + 1, -2*a + b,
        -2*a))  # noqa
    c = cse(t)
    assert len(c[0]) == 11


def test_issue_6169():
    r = CRootOf(x**6 - 4*x**5 - 2, 1)
    assert cse(r) == ([], [r])
    # and a check that the right thing is done with the new
    # mechanism
    assert sub_post(sub_pre((-x - y)*z - x - y)) == -z*(x + y) - x - y


def test_cse_Indexed():  # noqa
    len_y = 5
    y = IndexedBase('y', shape=(len_y,))
    x = IndexedBase('x', shape=(len_y,))
    Dy = IndexedBase('Dy', shape=(len_y-1,))  # noqa
    i = Idx('i', len_y-1)

    expr1 = (y[i+1]-y[i])/(x[i+1]-x[i])
    expr2 = 1/(x[i+1]-x[i])
    replacements, reduced_exprs = cse([expr1, expr2])
    assert len(replacements) > 0


def test_Piecewise():  # noqa
    f = Piecewise((-z + x*y, Eq(y, 0)), (-z - x*y, True))
    ans = cse(f)
    actual_ans = ([(x0, -z), (x1, x*y)],
                  [Piecewise((x0+x1, Eq(y, 0)), (x0 - x1, True))])
    assert ans == actual_ans


def test_name_conflict():
    z1 = x0 + y
    z2 = x2 + x3
    l = [cos(z1) + z1, cos(z2) + z2, x0 + x2]
    substs, reduced = cse(l)
    assert [e.subs(reversed(substs)) for e in reduced] == l


def test_name_conflict_cust_symbols():
    z1 = x0 + y
    z2 = x2 + x3
    l = [cos(z1) + z1, cos(z2) + z2, x0 + x2]
    substs, reduced = cse(l, symbols("x:10"))
    assert [e.subs(reversed(substs)) for e in reduced] == l


def test_symbols_exhausted_error():
    l = cos(x+y)+x+y+cos(w+y)+sin(w+y)
    sym = [x, y, z]
    with pytest.raises(ValueError):
        print(cse(l, symbols=sym))


def test_issue_7840():
    # daveknippers' example
    C393 = sympify(  # noqa
        'Piecewise((C391 - 1.65, C390 < 0.5), (Piecewise((C391 - 1.65, \
        C391 > 2.35), (C392, True)), True))'
    )
    C391 = sympify(  # noqa
        'Piecewise((2.05*C390**(-1.03), C390 < 0.5), (2.5*C390**(-0.625), True))'
    )
    C393 = C393.subs('C391',C391)  # noqa
    # simple substitution
    sub = {}
    sub['C390'] = 0.703451854
    sub['C392'] = 1.01417794
    ss_answer = C393.subs(sub)
    # cse
    substitutions, new_eqn = cse(C393)
    for pair in substitutions:
        sub[pair[0].name] = pair[1].subs(sub)
    cse_answer = new_eqn[0].subs(sub)
    # both methods should be the same
    assert ss_answer == cse_answer

    # GitRay's example
    expr = sympify(
        "Piecewise((Symbol('ON'), Equality(Symbol('mode'), Symbol('ON'))), \
        (Piecewise((Piecewise((Symbol('OFF'), StrictLessThan(Symbol('x'), \
        Symbol('threshold'))), (Symbol('ON'), S.true)), Equality(Symbol('mode'), \
        Symbol('AUTO'))), (Symbol('OFF'), S.true)), S.true))"
    )
    substitutions, new_eqn = cse(expr)
    # this Piecewise should be exactly the same
    assert new_eqn[0] == expr
    # there should not be any replacements
    assert len(substitutions) < 1


def test_recursive_matching():
    assert cse([x+y, 2+x+y, x+y+z, 3+x+y+z]) == \
        ([(x0, x + y), (x1, x0 + z)], [x0, x0 + 2, x1, x1 + 3])
    assert cse(reversed([x+y, 2+x+y, x+y+z, 3+x+y+z])) == \
        ([(x0, x + y), (x1, x0 + z)], [x1 + 3, x1, x0 + 2, x0])
    # sympy 1.0 gives ([(x0, x*y*z)], [5*x0, w*(x*y), 3*x0])
    assert cse([x*y*z*5, x*y*w, x*y*z*3]) == \
        ([(x0, x*y), (x1, x0*z)], [5*x1, w*x0, 3*x1])
    # sympy 1.0 gives ([(x4, x*y*z)], [5*x4, w*x3*x4, 3*x*x0*x1*x2*y])
    assert cse([x*y*z*5, x*y*z*w*x3, x*y*3*x0*x1*x2]) == \
        ([(x4, x*y), (x5, x4*z)], [5*x5, w*x3*x5, 3*x0*x1*x2*x4])
    assert cse([2*x*x, x*x*y, x*x*y*w, x*x*y*w*x0, x*x*y*w*x2]) == \
        ([(x1, x**2), (x3, x1*y), (x4, w*x3)], [2*x1, x3, x4, x0*x4, x2*x4])


if __name__ == "__main__":
    if len(sys.argv) > 1:
        exec(sys.argv[1])
    else:
        from py.test.cmdline import main
        main([__file__])

# vim: fdm=marker