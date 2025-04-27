import subprocess

class Gcc:
    def __init__(self, executable_path):
        self.executable_path = executable_path
        self._default_include_paths = None

    def default_include_paths(self):
        if self._default_include_paths is not None:
            return self._default_include_paths
        # Run the gcc command to get the include paths
        process = subprocess.Popen(
            [self.executable_path, '-E', '-v', '-'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Capture the output
        stdout, stderr = process.communicate(input=b'')
        
        # Decode the stderr output as it contains the include paths
        output = stderr.decode('utf-8')
        
        # Find the relevant section in the output
        start_marker = "#include <...> search starts here:"
        end_marker = "End of search list."
        
        include_paths = []
        in_include_section = False
        
        for line in output.splitlines():
            if start_marker in line:
                in_include_section = True
                continue
            if end_marker in line:
                break
            if in_include_section:
                include_paths.append(line.strip())
        
        self._default_include_paths = include_paths
        return include_paths

    def default_macros(self):
        # Run the gcc command to get the default macros
        process = subprocess.Popen(
            [self.executable_path, '-dM', '-E', '-'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Capture the output
        stdout, stderr = process.communicate(input=b'')
        
        # Decode the stdout output as it contains the macros
        output = stdout.decode('utf-8')
        
        macros = {}
        for line in output.splitlines():
            if line.startswith("#define"):
                parts = line.split(" ", 2)
                macro_name = parts[1]
                macro_value = parts[2] if len(parts) > 2 else ""
                macros[macro_name] = macro_value.strip()
        
        return macros



class Tcc:
    def __init__(self, executable_path):
        self.executable_path = executable_path
        self._default_include_paths = None

    def default_include_paths(self):
        if self._default_include_paths is not None:
            return self._default_include_paths
        # Run the tcc command to get the include paths
        process = subprocess.Popen(
            [self.executable_path, '-print-search-dirs'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Capture the output
        stdout, stderr = process.communicate()
        
        # Decode the stdout output as it contains the include paths
        output = stdout.decode('utf-8')
        
        include_paths = []
        in_include_section = False
        
        for line in output.splitlines():
            line = line.strip()
            if not in_include_section and line.startswith("include:"):
                in_include_section = True
                continue
            elif in_include_section and line.endswith(":") and line[0] != ' ':
                break

            if in_include_section and line:
                include_paths.append(line.strip())
        
        self._default_include_paths = include_paths
        return include_paths

    def default_macros(self):
        # Run the tcc command to get the default macros
        process = subprocess.Popen(
            [self.executable_path, '-dM', '-E', '-'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Capture the output
        stdout, stderr = process.communicate(input=b'')
        
        # Decode the stdout output as it contains the macros
        output = stdout.decode('utf-8')
        
        macros = {}
        for line in output.splitlines():
            if line.startswith("#define"):
                parts = line.split(" ", 2)
                macro_name = parts[1]
                macro_value = parts[2] if len(parts) > 2 else ""
                macros[macro_name] = macro_value.strip()
        
        return macros

def identify_c_compiler(executable_path):
    # List of commands to try, starting with the most specific
    version_flags = ['-v', '-V', '--version']

    compiler_info = ""

    for flag in version_flags:
            # Run the compiler with the version flag
            process = subprocess.Popen(
                [executable_path, flag],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate()
            
            # Combine stdout and stderr for comprehensive checking
            compiler_info = stdout.decode('utf-8') + stderr.decode('utf-8')
            # Check for known compiler signatures in the output
            if 'gcc' in compiler_info.lower():
                return Gcc(executable_path)
            elif 'clang' in compiler_info.lower():
                assert False, 'not implemented: Clang'
            elif 'tcc' in compiler_info.lower():
                return Tcc(executable_path)
            elif 'icc' in compiler_info.lower():
                assert False, 'not implemented: Intel C Compiler (ICC)'
            elif 'mingw' in compiler_info.lower():
                assert False, 'not implemented: MinGW'
            elif 'msvc' in compiler_info.lower() or 'microsoft' in compiler_info.lower():
                assert False, 'not implemented: Microsoft Visual C++ (MSVC)'
            elif 'solaris' in compiler_info.lower() or 'sunpro' in compiler_info.lower():
                assert False, 'not implemented: SunPro C Compiler'
            elif 'armcc' in compiler_info.lower():
                assert False, 'not implemented: ARM Compiler'
            # Add more checks as needed for different compilers

    # If no known compiler was identified, return unknown
    return 'Unknown Compiler'
