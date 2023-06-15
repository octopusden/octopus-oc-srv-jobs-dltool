from sys import version_info
import subprocess
import logging

strtype = str

class SubprocessWrapper(object):
    """
    Popen factory
    """

    def _set_popen(self, popen_call = subprocess.Popen):
        self._Popen = popen_call

    def __init__(self, popen_call = subprocess.Popen):
        self.code = None
        self.out = None
        self.err = None
        self._Popen = popen_call

    def _execute(self, args, options = {}):
        """
        Executes a program and returns process object
        """
        if type(args) != list:
            raise(TypeError('args must be list!'))

        if type(options) != dict: 
            raise(TypeError('options must be dict!'))

        logging.debug('Subprocess wrapper: executing %s', " ".join(args))

        if len(options) == 0: 
            return self._Popen(args)

        return self._Popen(args, **options)

    def _execute_and_wait(self, args, options = {}, fail = False):
        """
        Executes a program, waits for finish and returns code
        """
        proc = self._execute(args, options)
        n = proc.wait()
        self.code = n 
        if fail and n != 0: raise(subprocess.CalledProcessError(n, ' '.join(args), None))
        return n

    def _execute_and_get(self, args, options = {}, inputdata = None, fail = False):
        """
        Executes a program and returns (stdoutdata, stderrdata, returncode) tuple
        """
        options = options.copy()
        options['stdout'] = subprocess.PIPE
        options['stderr'] = subprocess.PIPE
        if (inputdata != None): options['stdin'] = subprocess.PIPE
        proc = self._execute(args, options)
        (stdoutdata,stderrdata) = proc.communicate(inputdata)
        (self.out, self.err, self.code) = (stdoutdata, stderrdata, proc.returncode)
        if fail and proc.returncode != 0: raise(subprocess.CalledProcessError(proc.returncode, ' '.join(args), stderrdata))
        return (stdoutdata, stderrdata, proc.returncode)

