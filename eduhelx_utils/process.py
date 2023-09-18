import subprocess

def remove_trailing_newline(string: str) -> str:
    if string.endswith("\n"):
        return string[:-1]
    return string

def execute(cmd, **kwargs):
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        **kwargs
    )
    output, error = process.communicate()
    output = output.decode("utf-8")
    error = error.decode("utf-8")
    exit_code = process.returncode

    output = remove_trailing_newline(output)
    error = remove_trailing_newline(error)

    return (output, error, exit_code)
