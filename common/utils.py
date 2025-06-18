import subprocess
import logging


logger = logging.getLogger(__name__)


def run_subprocess(commandline: list[str], log_stdout=False):
    result = subprocess.run(commandline, capture_output=True)
    stderr_message = result.stderr.decode("utf-8").splitlines()
    for line in stderr_message:
        logger.debug("stderr: {}".format(line))
    if log_stdout:
        stdout_message = result.stdout.decode("utf-8").splitlines()
        for line in stdout_message:
            logger.debug("stdout: {}".format(line))
    return result
