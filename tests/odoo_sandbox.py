"""Offline harness for the Studio server actions.

1. Sandbox check: the opcode whitelist, forbidden names and builtins below are copied from
   Odoo 20.0 odoo/tools/safe_eval/evaluation.py (commit 2993e06c, LGPL-3). Code that fails
   here would be rejected when pasted into an Odoo server action.
2. Fake ORM: just enough of the recordset API (search, create, write, mapped, filtered,
   message_post) and of base_automation's "On create and edit" trigger-field behaviour to run
   the action files unchanged. It is not Odoo: it proves the logic, not the platform.
"""
import datetime as _dt
import dis
import functools
import sys
from zoneinfo import ZoneInfo
from opcode import opmap
from types import CodeType

_BLACKLIST = {'IMPORT_STAR', 'IMPORT_NAME', 'IMPORT_FROM', 'STORE_ATTR', 'DELETE_ATTR',
              'STORE_GLOBAL', 'DELETE_GLOBAL'}
_CONST = {'POP_TOP', 'ROT_TWO', 'ROT_THREE', 'ROT_FOUR', 'DUP_TOP', 'DUP_TOP_TWO', 'LOAD_CONST',
          'RETURN_VALUE', 'BUILD_LIST', 'BUILD_MAP', 'BUILD_TUPLE', 'BUILD_SET', 'BUILD_CONST_KEY_MAP',
          'LIST_EXTEND', 'SET_UPDATE', 'COPY', 'SWAP', 'RESUME', 'RETURN_CONST', 'TO_BOOL',
          'LOAD_SMALL_INT'}
_OPS = ['POWER', 'MULTIPLY', 'FLOOR_DIVIDE', 'TRUE_DIVIDE', 'MODULO', 'ADD', 'SUBTRACT', 'LSHIFT',
        'RSHIFT', 'AND', 'XOR', 'OR']
_EXPR = _CONST | {'UNARY_POSITIVE', 'UNARY_NEGATIVE', 'UNARY_NOT', 'UNARY_INVERT',
                  *('BINARY_' + o for o in _OPS), 'BINARY_SUBSCR', *('INPLACE_' + o for o in _OPS),
                  'BUILD_SLICE', 'LIST_APPEND', 'MAP_ADD', 'SET_ADD', 'COMPARE_OP', 'IS_OP',
                  'CONTAINS_OP', 'DICT_MERGE', 'DICT_UPDATE', 'GEN_START', 'BINARY_OP', 'BINARY_SLICE'}
_SAFE = _EXPR | {
    'POP_BLOCK', 'POP_EXCEPT', 'SETUP_LOOP', 'SETUP_EXCEPT', 'BREAK_LOOP', 'CONTINUE_LOOP',
    'EXTENDED_ARG', 'MAKE_FUNCTION', 'CALL_FUNCTION', 'CALL_FUNCTION_KW', 'CALL_FUNCTION_EX',
    'CALL_METHOD', 'LOAD_METHOD', 'GET_ITER', 'FOR_ITER', 'YIELD_VALUE', 'JUMP_FORWARD',
    'JUMP_ABSOLUTE', 'JUMP_BACKWARD', 'JUMP_IF_FALSE_OR_POP', 'JUMP_IF_TRUE_OR_POP',
    'POP_JUMP_IF_FALSE', 'POP_JUMP_IF_TRUE', 'SETUP_FINALLY', 'END_FINALLY', 'BEGIN_FINALLY',
    'CALL_FINALLY', 'POP_FINALLY', 'RAISE_VARARGS', 'LOAD_NAME', 'STORE_NAME', 'DELETE_NAME',
    'LOAD_ATTR', 'LOAD_FAST', 'STORE_FAST', 'DELETE_FAST', 'UNPACK_SEQUENCE', 'STORE_SUBSCR',
    'LOAD_GLOBAL', 'RERAISE', 'JUMP_IF_NOT_EXC_MATCH', 'PUSH_NULL', 'PRECALL', 'CALL', 'KW_NAMES',
    'POP_JUMP_FORWARD_IF_FALSE', 'POP_JUMP_FORWARD_IF_TRUE', 'POP_JUMP_BACKWARD_IF_FALSE',
    'POP_JUMP_BACKWARD_IF_TRUE', 'POP_JUMP_FORWARD_IF_NONE', 'POP_JUMP_BACKWARD_IF_NONE',
    'POP_JUMP_FORWARD_IF_NOT_NONE', 'POP_JUMP_BACKWARD_IF_NOT_NONE', 'CHECK_EXC_MATCH',
    'RETURN_GENERATOR', 'PUSH_EXC_INFO', 'NOP', 'FORMAT_VALUE', 'BUILD_STRING', 'END_FOR',
    'LOAD_FAST_AND_CLEAR', 'LOAD_FAST_CHECK', 'POP_JUMP_IF_NOT_NONE', 'POP_JUMP_IF_NONE',
    'CALL_INTRINSIC_1', 'STORE_SLICE', 'CALL_KW', 'LOAD_FAST_LOAD_FAST', 'STORE_FAST_STORE_FAST',
    'STORE_FAST_LOAD_FAST', 'CONVERT_VALUE', 'FORMAT_SIMPLE', 'FORMAT_WITH_SPEC',
    'SET_FUNCTION_ATTRIBUTE', 'LOAD_FAST_BORROW', 'LOAD_FAST_BORROW_LOAD_FAST_BORROW', 'POP_ITER',
    'JUMP_BACKWARD_NO_INTERRUPT', 'LOAD_COMMON_CONSTANT', 'NOT_TAKEN'}
SAFE_OPCODES = {opmap[n] for n in _SAFE - _BLACKLIST if n in opmap}
UNSAFE_ATTRIBUTES = {'f_builtins', 'f_code', 'f_globals', 'f_locals', 'f_generator', 'func_code',
                     'func_globals', 'co_code', '_co_code_adaptive', 'mro', 'tb_frame', 'gi_code',
                     'gi_frame', 'gi_yieldfrom', 'cr_await', 'cr_code', 'cr_frame', 'ag_await',
                     'ag_code', 'ag_frame'}
for _m in ('_strptime', 'math', 'time'):  # Odoo's _ALLOWED_MODULES, pre-imported
    __import__(_m)


def _import(name, globals=None, locals=None, fromlist=None, level=-1):
    """Odoo's mock __import__: only satisfies C-level imports of already-loaded modules."""
    if name not in sys.modules:
        raise ImportError(f'module {name} should be imported before calling safe_eval()')


SAFE_BUILTINS = {
    '__import__': _import,
    'True': True, 'False': False, 'None': None, 'bytes': bytes, 'str': str, 'unicode': str,
    'bool': bool, 'int': int, 'float': float, 'enumerate': enumerate, 'dict': dict, 'list': list,
    'tuple': tuple, 'map': map, 'abs': abs, 'min': min, 'max': max, 'sum': sum,
    'reduce': functools.reduce, 'filter': filter, 'sorted': sorted, 'round': round, 'len': len,
    'repr': repr, 'set': set, 'all': all, 'any': any, 'ord': ord, 'chr': chr, 'divmod': divmod,
    'isinstance': isinstance, 'range': range, 'xrange': range, 'zip': zip, 'Exception': Exception,
}


def check_code(code_obj, name):
    """Raise if code_obj would be rejected by Odoo 20 test_python_expr(mode='exec')."""
    for n in code_obj.co_names:
        if '__' in n or n in UNSAFE_ATTRIBUTES:
            raise NameError(f'{name}: forbidden name {n!r}')
    bad = {i.opname for i in dis.get_instructions(code_obj) if i.opcode not in SAFE_OPCODES}
    if bad:
        raise ValueError(f'{name}: forbidden opcode(s) {sorted(bad)}')
    for const in code_obj.co_consts:
        if isinstance(const, CodeType):
            check_code(const, name)


class UserError(Exception):
    pass


class WrappedDatetime:
    """Stand-in for safe_eval.datetime (a wrapped module exposing datetime/timedelta)."""
    datetime = _dt.datetime
    timedelta = _dt.timedelta
    date = _dt.date
    timezone = _dt.timezone


# ---------------------------------------------------------------------- fake ORM

class Recordset:
    def __init__(self, env, model, ids):
        object.__setattr__(self, '_env', env)
        object.__setattr__(self, '_model', model)
        object.__setattr__(self, '_ids', list(ids))

    def __setattr__(self, name, value):  # mirror Odoo: assignment is not how actions should write
        raise AttributeError('use write()')

    @property
    def ids(self):
        return list(self._ids)

    @property
    def id(self):
        return self._ids[0] if self._ids else False

    def __iter__(self):
        return (Recordset(self._env, self._model, [i]) for i in self._ids)

    def __len__(self):
        return len(self._ids)

    def __bool__(self):
        return bool(self._ids)

    def __eq__(self, other):
        return isinstance(other, Recordset) and (self._model, self._ids) == (other._model, other._ids)

    def __hash__(self):
        return hash((self._model, tuple(self._ids)))

    def __getattr__(self, name):
        spec = self._env.schema[self._model].get(name)
        if not self._ids:
            return Recordset(self._env, spec[1], []) if spec and spec[0] in ('m2o', 'x2m') else False
        assert len(self._ids) == 1, f'{self._model}.{name} on {len(self._ids)} records'
        row = self._env.data[self._model][self._ids[0]]
        if spec and spec[0] == 'm2o':
            return Recordset(self._env, spec[1], [row[name]] if row.get(name) else [])
        if spec and spec[0] == 'x2m':
            return Recordset(self._env, spec[1], row.get(name, []))
        if name not in row and name != 'id':
            if name in self._env.schema[self._model] or name.startswith('x_'):
                return False
            raise AttributeError(f'{self._model} has no field {name}')
        return row.get(name, False)

    def filtered(self, func):
        return Recordset(self._env, self._model, [r.id for r in self if func(r)])

    def mapped(self, path):
        recs = [self]
        for part in path.split('.'):
            out, is_rec = [], False
            for rs in recs:
                for r in rs:
                    v = getattr(r, part)
                    if isinstance(v, Recordset):
                        is_rec = True
                    out.append(v)
            if is_rec:
                model = out[0]._model if out else None
                ids = []
                for v in out:
                    ids += [i for i in v._ids if i not in ids]
                recs = [Recordset(self._env, model, ids)]
            else:
                return out
        return recs[0]

    def write(self, vals):
        for i in self._ids:
            self._env.data[self._model][i].update(vals)
        self._env.fire(self._model, self, set(vals))
        return True

    def unlink(self):
        for i in self._ids:
            del self._env.data[self._model][i]
        return True

    def sudo(self):
        return self

    def message_post(self, body):
        for i in self._ids:
            self._env.messages.setdefault((self._model, i), []).append(body)

    # model-level API (called on an empty recordset)
    def search(self, domain, limit=None, order=None):
        rows = [i for i, row in self._env.data[self._model].items() if self._match(i, row, domain)]
        if order:
            rows.sort(key=lambda i: self._env.data[self._model][i].get(order.split()[0]))
        return Recordset(self._env, self._model, rows[:limit] if limit else rows)

    def search_count(self, domain):
        return len(self.search(domain))

    def create(self, vals):
        i = self._env.next_id()
        self._env.data[self._model][i] = dict(vals)
        rec = Recordset(self._env, self._model, [i])
        self._env.fire(self._model, rec, set(vals), create=True)
        return rec

    def _match(self, i, row, domain):
        for field, op, value in domain:
            v = i if field == 'id' else row.get(field, False)
            ops = {'=': lambda: v == value, '!=': lambda: v != value, 'in': lambda: v in value,
                   '<=': lambda: v is not False and v <= value, '>=': lambda: v is not False and v >= value}
            if not ops[op]():
                return False
        return True


class User:
    name = 'Store Manager'


class Env:
    def __init__(self, schema):
        self.schema = schema
        self.data = {m: {} for m in schema}
        self.messages = {}
        self.automations = []  # (model, trigger_fields or None for create, code, name)
        self.uid = 2
        self.user = User()
        self._seq = 0
        self._running = set()

    def __getitem__(self, model):
        return Recordset(self, model, [])

    def next_id(self):
        self._seq += 1
        return self._seq

    def fire(self, model, records, changed, create=False):
        for auto_model, fields, code, name in self.automations:
            if auto_model != model or not (create or fields & changed):
                continue
            key = (name, tuple(records.ids))
            if key in self._running:  # base_automation does not re-run a rule on the same records
                continue
            self._running.add(key)
            try:
                run(code, name, self, records)
            finally:
                self._running.discard(key)

    def rec(self, model, i):
        return Recordset(self, model, [i])


def compile_action(path):
    src = open(path, encoding='utf-8').read()
    code = compile(src, str(path), 'exec')
    check_code(code, str(path))
    return code


def run(code, name, env, records, **extra):
    ctx = {'__builtins__': SAFE_BUILTINS, 'env': env, 'records': records,
           'record': next(iter(records), records), 'datetime': WrappedDatetime,
           'UserError': UserError, 'timezone': ZoneInfo, 'uid': env.uid, 'user': env.user, **extra}
    exec(code, ctx)
