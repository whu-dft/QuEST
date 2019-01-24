from ctypes import *
import random
import math

# Declare several warnings which may occur
argWarning  = 'Bad argument list in {0:s} expected {1:d}, recieved {2:d} \n'
fileWarning = '{message} in {file} at line {line} \n'
fnfWarning  = 'File {} not found \n'
funWarning  = 'Function {} does not exist \n'
typeWarning = 'Unrecognised type {} requested in function {} \n'

QuESTLib = CDLL('./QuEST.so')

qreal = c_double

class QASMLogger(Structure):
    _fields_ = [("buffer",c_char_p),
               ("bufferSize",c_int),
               ("bufferFill",c_int),
               ("isLogging",c_int)]

class ComplexArray(Structure):
    _fields_ = [("real", POINTER(qreal)),
               ("imag", POINTER(qreal))]

class Complex(Structure):
    __str__ = lambda self:"({:15.13f},{:15.13f})".format(self.real,self.imag)
    __add__ = lambda self, b: Complex(self.real+b.real, self.imag+b.imag)
    __sub__ = lambda self, b: Complex(self.real-b.real, self.imag-b.imag)
    __mul__ = lambda self, b: Complex(self.real*b.real - self.imag*b.imag, self.real*b.imag + self.imag*b.real)
    __truediv__ = lambda self, b: Complex(self.real*b.real + self.imag*b.imag / (b.real*b.real + b.imag*b.imag),
                                      self.imag*b.real - self.real*b.imag / (b.real*b.real + b.imag*b.imag))
    conj = lambda self: Complex(self.real, -self.imag)
    __abs__ = lambda self: math.sqrt( (self*self.conj()).real )
    _fields_ = [("real",qreal),
                ("imag",qreal)]

class ComplexMatrix2(Structure):
    __str__ = lambda self:"[({:15.13f},{:15.13f}),({:15.13f},{:15.13f}),({:15.13f},{:15.13f}),({:15.13f},{:15.13f})]".format(
        self.r0c0.real,self.r0c0.imag,
        self.r0c1.real,self.r0c1.imag,
        self.r1c0.real,self.r1c0.imag,
        self.r1c1.real,self.r1c1.imag)
    __abs__ = lambda self: abs(self.r0c0*self.r1c1 - self.r1c0*self.r0c1)
    _fields_ = [("r0c0",Complex),("r0c1",Complex),
                ("r1c0",Complex),("r1c1",Complex)]

class Vector(Structure):
    __str__ = lambda self:"[{},{},{}]".format(self.x,self.y,self.z)
    __add__ = lambda self, b: Vector(self.x+b.x, self.y+b.y, self.z+b.z)
    __sub__ = lambda self, b: Vector(self.x-b.x, self.y-b.y, self.z-b.z)
    _fields_ = [("x",qreal),("y",qreal),("z",qreal)]

class Qureg(Structure):
    def __str__(self):
        stateVec = []
        for state in range(self.numAmpsTotal):
            stateVec+= [Complex(self.stateVec.real[state], self.stateVec.imag[state])]
        return "\n".join(list(map(Complex.__str__, stateVec)))
    _fields_ = [("isDensityMatrix", c_int),
                ("numQubitsRepresented", c_int),
                ("numQubitsInStateVec", c_int),
                ("numAmpsPerChunk",c_longlong),
                ("numAmpsTotal",   c_longlong),
                ("chunkId", c_int),
                ("numChunks", c_int),
                ("stateVec", ComplexArray),
                ("pairStateVec", ComplexArray),
                ("deviceStateVec", ComplexArray),
                ("firstLevelReduction",POINTER(qreal)),("secondLevelReduction",POINTER(qreal)),
                ("qasmLog",POINTER(QASMLogger))]

class QuESTEnv(Structure):
    _fields_ = [("rank",c_int),("numRanks",c_int)]

def stringToList(a):
    a = a.split(',')
    try :
        return list(map(float, a))
    except ValueError:
        raise IOError('Bad array in input file')

def stringToListInt(a):
    a = a.split(',')
    try :
        return list(map(int, a))
    except ValueError:
        raise IOError('Bad array in input file')

def stringToComplex(a):
    a=a.lstrip('(').rstrip(')')
    return list(map(float,a.split(',')))

def argVector(arg):
    return Vector(*stringToList(arg))

def argComplexMatrix2(arg):
    vals = stringToList(arg)
    elements = []
    for i in range(0,len(vals),2):
        elements.append(Complex(vals[i],vals[i+1]))
    return ComplexMatrix2(*elements)

def argComplex(arg):
    return Complex(*stringToComplex(arg))

def argComplexArray(arg):
    vals = stringToList(arg)
    real = vals[0::2]
    imag = vals[1::2]
    return ComplexArray(byref(real),byref(imag))

def argPointerQreal(arg):
    if isinstance(arg,str):
        arg = stringToList(arg)
    
    if isinstance(arg,list):
        newArg = (qreal*len(arg))()
        for i in range(len(arg)):
            newArg[i] = arg[i]
        return newArg
    elif isinstance(arg, qreal):
        return arg

def argPointerInt(arg):
    if isinstance(arg,str):
        arg = stringToListInt(arg)

    if isinstance(arg,list):
        return (c_int*len(arg))(*arg)
    elif isinstance(arg, c_int):
        return arg

def argPointerLongInt(arg):
    if isinstance(arg,str):
        arg = stringToListInt(arg)

    if isinstance(arg,list):
        return (c_long*len(arg))(*arg)
    elif isinstance(arg, c_int):
        return arg

    
class QuESTTestee:
    basicTypeConv = {"c_int":int, "c_long":int, "c_ulong":int, "c_longlong":int, "c_double":float,
                     "Vector":argVector, "ComplexMatrix2":argComplexMatrix2, "ComplexArray":argComplexArray,
                     "Complex":argComplex, "LP_c_double":argPointerQreal, "LP_c_int":argPointerInt, "LP_c_long":argPointerLongInt }

    funcsList = []
    funcsDict = {}
    
    def __init__(self, funcname=None, retType=None, argType=[], defArg=[], denMat=False):
        self.funcname = funcname
        if not QuESTLib[funcname]:
            raise IOError(funcname+' not found in QuEST API')
        self.thisFunc = QuESTLib[funcname]

        if self.funcname not in list_funcnames():
            QuESTTestee.funcsList.append(self)
            QuESTTestee.funcsDict[self.funcname] = self
        else:
            raise IOError(funcname+' already defined')

        self.thisFunc.restype = retType
        self.thisFunc.argtypes = argType
        self.nArgs = len(argType) or 0
        self.defArg = defArg
        self.denMat = denMat
        
        if self.defArg is not None and len(self.defArg) != self.nArgs:
            raise IOError(argWarning.format(self.funcname, self.nArgs, len(self.defArg)))
        
    def __call__(self,*argsList):
        # If packed as list, otherwise receive as variables
        if len(argsList) == 1 and isinstance(argsList[0],list):
            specArg = argsList[0]
        else:
            specArg = list(argsList)

        if (len(specArg) == 0 and self.nArgs != 0) or (self.nArgs == 0):
            self.fix_types(specArg)
            return self.thisFunc(*self.defArg)
        elif isinstance(specArg,list) and len(specArg) == self.nArgs:
            self.fix_types(specArg)
            try:
                return self.thisFunc(*specArg)
            except ArgumentError:
                print(specArg)
                raise IOError('Bad arguments in function {}'.format(self.funcname))
        else:
            print(specArg)
            raise IOError(argWarning.format(self.funcname, self.nArgs, len(specArg)))

    def fix_types(self,args):
        for i in range(self.nArgs):
            reqType = self.thisFunc.argtypes[i]
            reqTypeName = self.thisFunc.argtypes[i].__name__
            if isinstance(args[i],reqType):
                pass
            elif reqTypeName in QuESTTestee.basicTypeConv:
                args[i] = QuESTTestee.basicTypeConv[reqTypeName](args[i])
            else:
                print(args[i], reqTypeName)
                raise IOError(typeWarning.format(reqTypeName, self.funcname))

def dict_funcs():
    return QuESTTestee.funcsDict
    
def list_funcs():
    return QuESTTestee.funcsList

def list_funcnames():
    return list(map(lambda x: x.funcname, QuESTTestee.funcsList))

# Define some simple basic constants
complex0 = Complex(0.,0.)
complex1 = Complex(1.,0.)
complexi = Complex(0.,1.)
complexHalf = Complex(0.5,0.)
complexSqr2 = Complex(1./math.sqrt(2),0.0)
unitMatrix = ComplexMatrix2(complex1,complex0,complex0,complex1)
xDir = Vector(1.,0.,0.)
yDir = Vector(0.,1.,0.)
zDir = Vector(0.,0.,1.)

def rand_norm_comp():
    newComplex = Complex(random.random(), random.random())
    norm = abs(newComplex)
    newComplex.imag /= norm
    newComplex.real /= norm
    return newComplex

def rand_norm_comp_pair():
    return rand_norm_comp()*complexSqr2, rand_norm_comp()*complexSqr2

def rand_norm_mat():
    elems = []
    elems += [complexSqr2*rand_norm_comp()]
    elems += [complexSqr2*rand_norm_comp()]
    elems += [Complex(0,0)-elems[1].conj()]
    elems += [elems[0].conj()]
    newMat = ComplexMatrix2(*elems)

    return newMat