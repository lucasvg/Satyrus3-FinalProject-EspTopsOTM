"""
"""
## Standard Library
import itertools as it

## Third-Party
from ply import lex, yacc

## Local
from ...satlib import stderr, stdout, Source, Stack
from ..types.error import SatParserError, SatLexerError, SatSyntaxError, SatExit
from ..types import Expr, Var, Number, String, SatType
from ..types.symbols import SYS_CONFIG, DEF_CONSTANT, DEF_ARRAY, DEF_CONSTRAINT
from ..types.symbols.tokens import T_IDX

def regex(pattern: str):
    def decor(callback):
        callback.__doc__ = pattern
        return callback
    return decor

class SatLexer(object):
    ## List of token names.
    tokens = (
        'NAME', 'NUMBER',

        'FORALL', 'EXISTS', 'EXISTS_ONE',

        'NOT', 'AND', 'OR', 'XOR',

        'IMP', 'RIMP', 'IFF',

        'CONFIG',

        'ENDL',

        'COMMA',

        'ASSIGN',

        'EQ', # equal
        'GT', # greater than
        'LT', # less than

        'GE', # greater or equal
        'LE', # less or equal

        'NE', # not equal

        'MUL', 'DIV', 'MOD', 'ADD', 'SUB',

        'DOTS',

        'LBRA', 'RBRA', 'LPAR', 'RPAR', 'LCUR', 'RCUR',

        'STRING',
        )

    # Regular expression rules for tokens
    t_DOTS = r'\:'

    t_LBRA = r'\['
    t_RBRA = r'\]'

    t_LPAR = r'\('
    t_RPAR = r'\)'

    t_LCUR = r'\{'
    t_RCUR = r'\}'

    t_FORALL = r'\@'
    t_EXISTS = r'\$'
    t_EXISTS_ONE = r'\!\$'

    t_NOT = r'\~'

    t_AND = r'\&'

    t_OR = r'\|'

    t_XOR = r'\^'

    t_IMP = r'\-\>'

    t_RIMP = r'\<\-'

    t_IFF = r'\<\-\>'

    t_COMMA = r'\,'

    t_DIV = r'\/'

    t_MOD = r'\%'

    t_MUL = r'\*'

    t_ADD = r'\+'

    t_SUB = r'\-'

    t_ENDL = r'\;'

    t_ASSIGN = r'\='

    t_EQ = r'\=\='
    t_GT = r'\>'
    t_LT = r'\<'

    t_GE = r'\>\='
    t_LE = r'\<\='

    t_NE = r'\!\='

    t_CONFIG = r'\?'

    @regex(r'\".*\"')
    def t_STRING(self, t):
        t.value = String(t.value[1:-1])
        return t

    @regex(r"\n")
    def t_newline(self, t):
        self.lexer.lineno += 1
        return None

    @regex(r"[a-zA-Z_][a-zA-Z0-9_]*")
    def t_NAME(self, t):
        t.value = Var(t.value)
        return t

    @regex(r"[-+]?[0-9]*\.?[0-9]+([Ee][-+]?[0-9]+)?")
    def t_NUMBER(self, t):
        t.value = Number(t.value)
        return t

    # String containing ignored characters between tokens
    t_ignore = ' \t'
    t_ignore_COMMENT = r'\#.*'

    @regex(r'\#\{[\s\S]*?\}\#')
    def t_ignore_MULTICOMMENT(self, t):
        self.lexer.lineno += str(t.value).count('\n')
        return None

    def t_error(self, t):
        stderr << f"Unknown token '{t.value}' at line {t.lineno}"
        if t:
            stderr << f"Syntax Error at line {t.lineno}:"
            stderr << self.source.lines[t.lineno-1]
            stderr << f'{" " * (self.chrpos(t.lineno, t.lexpos))}^'
        else:
            stderr << "Unexpected End Of File."

    def __init__(self, source, **kwargs):
        self.lexer = lex.lex(object=self, **kwargs)
        self.source = source

    def chrpos(self, lineno, lexpos):
        return (lexpos - self.source.table[lineno - 1] + 1)

class SatParser(object):

    tokens = SatLexer.tokens

    precedence = (

        ('left', 'ADD', 'SUB'),
        ('left', 'MUL', 'DIV', 'MOD'),

        ('left', 'XOR', 'OR'),
        ('left', 'AND'),
        ('left', 'NOT'),

        ('left', 'IMP', 'RIMP', 'IFF'),

        ('left', 'EQ', 'NE', 'GE', 'LE', 'GT', 'LT'),

        ('left', 'FORALL', 'EXISTS', 'EXISTS_ONE'),

        ('left', 'LBRA', 'RBRA'),

        ('left', 'LCUR', 'RCUR'),
        ('left', 'LPAR', 'RPAR'),
        
        ('left', 'DOTS'),

        ('left', 'CONFIG'),

        ('left', 'NAME'),
        ('left', 'STRING', 'NUMBER'),

        ('left', 'ENDL'),
    )

    def __init__(self):
        ## Input
        self.source = None
        ## Output
        self.bytecode = None

        ## Lex & Yacc
        self.lexer = None
        self.parser = None

        self.error_stack = Stack()

    def __lshift__(self, error: SatParserError):
        self.error_stack.push(error)

    def exit(self, code: int):
        raise SatExit(code)

    def interrupt(self):
        """
        """
        while self.error_stack:
            error = self.error_stack.pop()
            stderr << error
        else:
            self.exit(1)

    def checkpoint(self):
        """
        """
        if self.error_stack: self.interrupt()

    def parse(self, source: Source):
        ## Input
        self.source = source
        
        ## Initialize Lexer
        self.lexer = SatLexer(self.source)

        ## Initialize Parser
        self.parser = yacc.yacc(module=self)
        
        ## Run Parser
        self.parser.parse(self.source)

        ## Checkpoint
        self.checkpoint()

        ## Output
        return self.bytecode
            
    def run(self, code : list):
        self.bytecode = code

    def get_arg(self, p, index: int=None, track: bool=True):
        if index is None:
            value = p
            if track:
                value.lexinfo = {
                    'lineno' : None,
                    'lexpos' : None,
                    'chrpos' : None,
                    'source' : self.source,
                }
        else:
            value = p[index]
            if track:
                lineno = p.lineno(index)
                lexpos = p.lexpos(index)
                value.lexinfo = {
                    'lineno' : lineno,
                    'lexpos' : lexpos,
                    'chrpos' : self.chrpos(lineno, lexpos),
                    'source' : self.source,
                }
        return value

    def p_start(self, p):
        """ start : code
        """
        self.run(p[1])

    def p_code(self, p):
        """ code : code stmt
                 | stmt
        """
        if len(p) == 3:
            p[0] = [*p[1], p[2]]
        else:
            p[0] = [ p[1],]

    def p_stmt(self, p):
        """ stmt : sys_config ENDL
                 | def_constant ENDL
                 | def_array ENDL
                 | def_constraint ENDL
        """
        p[0] = p[1]

    def p_sys_config(self, p):
        """ sys_config : CONFIG NAME DOTS sys_config_args
        """
        name = self.get_arg(p, 2)
        args = p[4]
        p[0] = (SYS_CONFIG, name, args)

    def p_sys_config_args(self, p):
        """ sys_config_args : sys_config_args COMMA sys_config_arg
                            | sys_config_arg
        """
        if len(p) == 4:
            p[0] = [*p[1], self.get_arg(p, 3)]
        else:
            p[0] = [self.get_arg(p, 1)]

    def p_sys_config_arg(self, p):
        """ sys_config_arg : NUMBER
                           | STRING
        """
        p[0] = p[1]

    def p_def_constant(self, p):
        """ def_constant : NAME ASSIGN expr
        """
        name = self.get_arg(p, 1)
        value = self.get_arg(p, 3)
        p[0] = (DEF_CONSTANT, name, value)

    def p_literal(self, p):
        """ literal : NUMBER
                    | NAME
        """
        p[0] = self.get_arg(p, 1)

    def p_def_array(self, p):
        """ def_array : NAME shape ASSIGN array_buffer
                      | NAME shape
        """
        name = self.get_arg(p, 1)
        shape = p[2]

        if len(p) == 5: # array declared
            buffer = p[4]
        else: # implicit array
            buffer = None
        
        p[0] = (DEF_ARRAY, name, shape, buffer)

    def p_shape(self, p):
        """ shape : shape index
                  | index
        """
        if len(p) == 3:
            p[0] = (*p[1], self.get_arg(p, 2))
        else:
            p[0] = (self.get_arg(p, 1),)

    def p_index(self, p):
        """ index : LBRA expr RBRA
        """
        p[0] = p[2]

    def p_array_buffer(self, p):
        """ array_buffer : LCUR array RCUR
        """
        p[0] = p[2]

    def p_array(self, p):
        """ array : array COMMA array_item
                  | array_item
        """
        if len(p) == 4:
            p[0] = [*p[1], p[3]]
        else:
            p[0] = [ p[1],]

    def p_array_item(self, p):
        """ array_item : array_index DOTS expr
        """
        p[0] = (p[1], p[3])

    def p_array_index(self, p):
        """ array_index : LPAR literal_seq RPAR
        """
        p[0] = p[2]

    def p_literal_seq(self, p):
        """ literal_seq : literal_seq COMMA literal
                        | literal
        """
        if len(p) == 4:
            p[0] = (*p[1], p[3])
        else:
            p[0] = ( p[1],)

    def p_def_constraint(self, p):
        """ def_constraint : LPAR NAME RPAR NAME LBRA literal RBRA DOTS loops expr
                           | LPAR NAME RPAR NAME DOTS loops expr
        """
        type_= self.get_arg(p, 2)
        name = self.get_arg(p, 4)
        
        if len(p) == 11:
            level = self.get_arg(p, 6, track=False)
            loops = self.get_arg(p, 9, track=False)
            expr  = self.get_arg(p, 10, track=False)
        else:
            level = None
            loops = self.get_arg(p, 6, track=False)
            expr  = self.get_arg(p, 7, track=False)

        p[0] = (DEF_CONSTRAINT, type_, name, loops, expr, level)

    def p_loops(self, p):
        """ loops : loops loop
                  | loop
        """
        if len(p) == 3:
            p[0] = [*p[1], p[2]]
        else:
            p[0] = [ p[1],]

    def p_loop(self, p):
        """ loop : quant LCUR NAME ASSIGN domain COMMA conditions RCUR
                 | quant LCUR NAME ASSIGN domain RCUR
        """
        if len(p) == 9:
            p[0] = (p[1], self.get_arg(p, 3), p[5], p[7])
        else:
            p[0] = (p[1], self.get_arg(p, 3), p[5], None)

    def p_quant(self, p):
        """ quant : FORALL
                  | EXISTS
                  | EXISTS_ONE
        """
        p[0] = p[1]

    def p_domain(self, p):
        """ domain : LBRA expr DOTS expr DOTS expr RBRA
                   | LBRA expr DOTS expr RBRA
        """
        if len(p) == 8:
            p[0] = (p[2], p[4], p[6])
        else:
            p[0] = (p[2], p[4], None)

    def p_conditions(self, p):
        """ conditions : conditions COMMA condition
                       | condition
        """
        if len(p) == 4:
            p[0] = [*p[1], p[2]]
        else:
            p[0] = [p[1],]

    def p_condition(self, p):
        """ condition : expr EQ expr
                      | expr GT expr
                      | expr LT expr
                      | expr GE expr
                      | expr LE expr
                      | expr NE expr
        """
        p[0] = Expr(p[2], p[1], p[3])

    def p_condition_expr(self, p):
        """ condition : expr
        """
        p[0] = p[1]

    def p_expr(self, p):
        """ expr : literal
        """
        p[0] = p[1]

    def p_expr1(self, p):
        """ expr : NOT expr
                 | ADD expr
                 | SUB expr
        """
        p[0] = Expr(p[1], p[2])

    def p_expr2(self, p):
        """ expr : expr AND expr
                 | expr OR expr
                 | expr XOR expr
                 | expr ADD expr
                 | expr SUB expr
                 | expr MUL expr
                 | expr DIV expr
                 | expr MOD expr
                 | expr IMP expr
                 | expr RIMP expr
                 | expr IFF expr
        """
        p[0] = Expr(p[2], p[1], p[3])

    def p_expr_index(self, p):
        """ expr : expr LBRA expr RBRA
        """
        p[0] = Expr(T_IDX, p[1], p[3])

    def p_expr_par(self, p):
        """ expr : LPAR expr RPAR
        """
        p[0] = p[2]

    def p_error(self, t):
        target = SatType()
        if t:
            target.lexinfo = {
                'lineno' : t.lineno,
                'lexpos' : t.lexpos,
                'chrpos' : self.chrpos(t.lineno, t.lexpos),
                'source' : self.source,
            }
            msg = "Invalid Syntax"
        else:
            lineno = len(self.source.lines) - 1
            lexpos = len(self.source.lines[lineno]) - 1
            target.lexinfo = {
                'lineno' : lineno,
                'lexpos' : lexpos,
                'chrpos' : self.chrpos(lineno, lexpos),
                'source' : self.source,
            }
            msg = "Unexpected End Of File."
        self << SatSyntaxError(msg=msg, target=target)
        return None

    def chrpos(self, lineno: int, lexpos: int):
        return (lexpos - self.source.table[lineno - 1] + 1)