import os.path
from QuESTFunc import *
from QuESTTypes import *
from testset import tests
import importlib.util
import importlib.machinery


# Add .test to valid python names
importlib.machinery.SOURCE_SUFFIXES += ['.test']

# Make publically accessible
logFile = None
unitPath = None
Env = None
testResults = None
def init_tests(unitTestPath, logFilePath, tolerance=None, quiet=False):
    global logFile
    global unitPath
    global Env
    global testResults
    unitPath = unitTestPath
    logFile = open(logFilePath,'w')
    Env = createQuESTEnv()
    testResults = TestResults(tolerance, not quiet)
    return testResults

def finalise_tests():
    global unitPath
    global logFile
    global Env
    global testResults
    del unitPath
    logFile.close()
    del logFile
    destroyQuESTEnv(Env)
    del Env
    del testResults
 
class QuESTTestFile:
    """ Class containing test file information """
    
    def __init__(self,filename):
        self.File = open(filename,'r')
        
        self.name = filename[filename.rfind('/')+1:] # Remove path
        self.nLine= 0
        temp = ''
        try:
            temp = self.readline()
            self.nTests = int(temp)
        except ValueError:
            raise IOError(fileWarning.format(message='Header of file :\n'+temp+"\n does not contain the number of tests",
                                             file=self.name, line=self.nLine))
        
    def __del__(self):
        self.File.close()
        
    def readline(self,retSkip=False):
        """ Reads a line from a test file """
        skip = []
        for line in self.File:
            self.nLine += 1
            if line.find('#') > -1:
                lineStrip = line[:line.find('#')].strip()
            else:
                lineStrip = line.strip()
            if lineStrip:
                if retSkip:
                    return lineStrip, skip
                else:
                    return lineStrip
            else:
                if line.lstrip('#').strip():
                    skip += [line.lstrip('#').strip()]
        raise IOError(fileWarning.format(message='Unexpected end of file',file=self.name, line=self.nLine))

    def parse_args(self, line):
        """ Split arguments, but maintain arrays and complex arrays as a block """
        line = self.remove_brackets(line)
        return line.split()

    def remove_brackets(self, line):
        """ Remove all brackets from a given string (for parsing complex/arrays nicely) """
        remBrac = ''.maketrans('[{()}]','      ','[{()}]')
        return line.translate(remBrac)
                
    def read_state_vec(self, numQubits = 0, denMat=False):
        """ Read the expected state vector into a qubit state """
        if denMat:
            QubitsOut = createDensityQureg(numQubits, Env)
        else:
            QubitsOut = createQureg(numQubits, Env)

        for state in range(QubitsOut.numAmpsTotal): # Compare final with expected states
            try:
                stateElem = argComplex(self.readline())
            except ValueError:
                raise IOError(fileWarning.format(message='Bad state line', file=self.name, line=self.nLine))
            #setAmps(QubitsOut, state, qreal(stateElem.real), qreal(stateElem.imag), 1)
            QubitsOut.stateVec.real[state] = stateElem.real
            QubitsOut.stateVec.imag[state] = stateElem.imag
        return QubitsOut
        
class TestResults:
    """ Main class regarding testing framework stores results and comparisons """
    
    def __init__(self, tolerance = 1.e-6, printToScreen = True):
        self.passes, self.fails, self.numTests = [0]*3
        self.tolerance = tolerance
        self.printToScreen = printToScreen
        
    def compareStates(self, a, b, tol = None):
        if tol is None:
            tol = self.tolerance

        if a.isDensityMatrix and not b.isDensityMatrix or a.isDensityMatrix and not b.isDensityMatrix:
            raise TypeError('A and B are not both density matrices')
            
        if a.numQubitsRepresented != b.numQubitsRepresented:
            raise IndexError('A and B registers are not the same size')

        # Compare final with expected states
        if a.isDensityMatrix and b.isDensityMatrix:
            
            for row in range(a.numQubitsRepresented): 
                for col in range(b.numQubitsRepresented): 
                    aState = getDensityAmp(a,row,col)
                    bState = getDensityAmp(b,row,col)
                    if not self.compareComplex(aState,bState,tol): return False
                
        else:
            for state in range(getNumAmps(a)): 
                aState = getAmp(a,state)
                bState = getAmp(b,state)
                if not self.compareComplex(aState,bState,tol): return False
                
        return True

    def write_term(self, *out, **kwargs):
        if self.printToScreen: print(*out, **kwargs)
    
    def compareReals(self, a, b, tol = None):
        if tol is None:
            tol = self.tolerance
        if abs(a - b) > tol: return False
        return True

    def compareComplex(self, a, b, tol = None):
        if tol is None:
            tol = self.tolerance
        if abs(a.real - b.real) > tol or abs(a.imag - b.imag) > tol: return False
        return True
                
    def pass_test(self, test=""):
        self.write_term('.',end='')
        logFile.write('{} Passed\n'.format(test.strip()))
        self.numTests += 1
        self.passes += 1

    def fail_test(self, test = "", message = ""):
        self.write_term('F',end='')
        if test or message:
            logFile.write('Test {} failed: {}\n'.format(test,message))
        self.numTests += 1
        self.fails += 1

    def validate(self, arg, test = "", message = ""):
        if arg:
            self.pass_test(test)
        else:
            self.fail_test(test, message)
            
    def print_results(self):
        self.write_term('\nPassed {} of {} tests, {} failed.\n'.format(self.passes,self.numTests,self.fails))
        
    def run_test(self, testFunc, testFile):
        qubitTypeNames = {"Z":"Zero ", "C":"Custom ", "B":"BitState ", "P":"Plus ", "D":"Debug "}
        for test in range(testFile.nTests):
            line, testComment = testFile.readline(True)

            qubitType,nBits,*args = testFile.parse_args(line)

            bitString = ""
            if qubitType in "CBcb":
                bitString = args[0]
                del args[0]
                Qubits = argQureg(nBits, qubitType, testFile, initBits = bitString, denMat = testFunc.denMat)
            else:
                Qubits = argQureg(nBits, qubitType, testFile, denMat = testFunc.denMat)

            args.insert(0,Qubits)

            retType = testFunc.thisFunc.restype
            if retType is None:
                testFunc(args)
                expectState = testFile.read_state_vec(nBits,denMat = testFunc.denMat)
                success = testResults.compareStates(Qubits, expectState)
            else:
                result = testFunc(args)

                if retType is Complex:
                    expect = argComplex(testFile.readline())
                    success = self.compareComplex(result,expect)
                elif retType is c_double:
                    expect = float(testFile.readline())
                    success = self.compareReals(result,expect)
                elif retType is c_int:
                    expect = int(testFile.readline())
                    success = expect == result
                    
                else:
                    raise TypeError('Cannot test type {} currently'.format(retType.__name__))
                    
    
            if success:
                self.pass_test("{}{}".format(qubitTypeNames[qubitType],bitString))
            else:
                if testComment:
                    logFile.write('Test {Func}:{Comm} failed in {File}\n'.format(
                        Func = testFunc.funcname,
                        Comm = "\n".join(testComment),
                        File = testFile.name))
                else:
                    logFile.write('Testing {Func} failed in {File}\n'.format(
                        Func =testFunc.funcname,
                        File =testFile.name))
                if retType is None:
                    for state in range(getNumAmps(Qubits)):
                        a = getAmp(Qubits, state)
                        b = getAmp(expectState, state)
                        logFile.write('{} {}\n'.format(a, b))
                else:
                    logFile.write('{} {}\n'.format( result, expect))
                self.fail_test()
                
            destroyQureg(Qubits,Env)

        del testFile

    def run_std_test(self, testFuncsList,name=''):
    
        self.write_term('Running tests '+name+":", end=' ')
        
        for testFunc in testFuncsList:
    
            logFile.write('\nRunning test {}\n'.format(testFunc.funcname))
            
            testPath = unitPath+testFunc.funcname+'.test'
            

            if os.path.isfile(testPath) :
                with open(testPath,'r') as testFile:
                    testPyth = testFile.readline().lstrip('# ').strip()
                
                    if testPyth == "Python": # If file flagged as Python
                        self.run_python_test(testPath)
                        continue
                testFile = QuESTTestFile(testPath)
            else:
                logFile.write(fnfWarning.format(testPath))
                self.fail_test()
                continue
    
            self.run_test(testFunc, testFile)
    
        self.write_term()

    def run_python_test(self, testPath):
        spec = importlib.util.spec_from_file_location("templib", testPath)
        templib = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(templib)
        templib.run_tests()
        del templib

    def run_cust_test(self, testFileName):
    
        if os.path.isfile(testFileName):
            testPath = testFileName
        elif os.path.isfile(unitPath+testFileName+'.test'):
            testPath = unitPath+testFileName+'.test'
        else:
            logFile.write(fnfWarning.format(testFileName))
            self.fail_test()
            print()
            return
            
            
        print('Running test '+testPath+":", end=' ')
    
        if testPath.endswith('.test'): # Run standard formatted tests
            with open(testPath,'r') as testFile:
                testFunc = testFile.readline().lstrip('# ').strip()
                
                if testFunc.capitalize() == "Python": # If file flagged as Python
                    self.run_python_test(testPath)
                    return
                
                if testFunc not in list_funcnames():
                    raise IOError(funWarning.format(testFunc.funcname))
            testFunc = tests[testFunc]
            testFile = QuESTTestFile(testPath)

            self.run_test(*testFunc, testFile)
    
    
        elif testPath.endswith('.py'): # Run custom test scripts
            self.run_python_test(testPath)
        else:
            raise IOError('Unrecognised filetype in test run of file {}'.format(testPath))
                
        print()

def argQureg(nBits, qubitType, testFile=None, initBits = None, denMat = False):
    nBits = int(nBits)
        
    #Upcase qubitType
    qubitType = qubitType.upper()
    # Initialise Qubits
    if denMat :
        Qubits = createDensityQureg(nBits, Env)
    else :
        Qubits = createQureg(nBits, Env)

    qubitTypes = {"Z":initZeroState,"P":initPlusState,"D":initDebugState,"C":setAmps,"B":setAmps}
    
    if qubitType not in qubitTypes:
        raise IOError(fileWarning.format(message = 'Unrecognised qubit initialisation state "'+qubitType+'"',
                                  file = testFile.name, line=testFile.nLine))

    elif qubitType == "B":
        if any(bit not in "01" for bit in initBits ):
            raise IOError(fileWarning.format(message = 'Expected qubit state, received {}'.format(state)))

        try:
            state = int(initBits, 2)
        except TypeError:
            raise IOError(fileWarning.format(message = 'Expected qubit state, received {}'.format(state)))
        
        nIn = len(initBits)
        if (nBits != nIn):
            raise IOError(
                fileWarning.format(message = 'Bad number of states expected {}, received {}'.format(nBits, nIn)),
                file = testFile.name, line=testFile.nLine)

        initClassicalState(Qubits, state)
        
        del nIn
        
    
    elif qubitType == "C": # Handle custom initialisation
        nStates = getNumAmps(Qubits)
        nReqStates = nStates*2 # Account for complexes
        initBits = stringToList(initBits)
        nInStates = len(initBits)

        if nReqStates != nInStates:
            raise IOError(
                fileWarning.format(message = 'Bad number of states expected {}, received {}'.format(nStates, nIn)),
                file = testFile.name, line=testFile.nLine)
        
        qAmpsReal, qAmpsImag = initBits[0::2], initBits[1::2] # Split into real and imag

        setAmps(Qubits, 0, qAmpsReal, qAmpsImag, nStates)
        
        del nStates, nReqStates, nInStates, qAmpsReal, qAmpsImag
    
    else:
        qubitTypes[qubitType](Qubits)

    return Qubits


def gen_test(testFunc, testFile):
    for i in range(1,testFunc.nArgs):
        if testFunc.defArg[i] is None:
            print('Unable to generate test for function {} invalid default arguments'.format(testFunc.funcname))
            return

    with open(testFile,'w') as outputFile:
        
        outputFile.write('# {}\n'.format(testFunc.funcname))
        # Standard run 3 tests
        outputFile.write('3\n')
        
        for qubitType in "ZPD":
            nQubits = 3
            args = [argQureg(nQubits, qubitType,denMat=testFunc.denMat)]
            argString = "{} {}".format(qubitType, nQubits)
            for arg in range(1,testFunc.nArgs):
                args += [testFunc.defArg[arg]]
                argString += " "+str(testFunc.defArg[arg])
            outputFile.write(argString+"\n")
            result = testFunc(*args)
            retType = testFunc.thisFunc.restype
            if retType is None:
                outputFile.write(str(args[0])+"\n")
            else:
                outputFile.write(str(result)+"\n")


def gen_tests(testsToGen=["all"]):
    from testset import tests
    for testSet in testToGen:
    
        for testFunc in tests[testSet] :
            if testFunc in tests["don't_generate"]: continue 
            gen_test(testFunc, unitPath+testFunc.funcname+".test")
