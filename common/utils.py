import subprocess
import logging


logger = logging.getLogger(__name__)


def run_subprocess(commandline: list[str], log_stdout=False, capture_out=True):
    logger.debug("starting process")
    result = subprocess.run(commandline, capture_output=capture_out)
    logger.debug("process executed and done")
    if capture_out:
        stderr_message = result.stderr.decode("utf-8").splitlines()
        for line in stderr_message:
            logger.debug("stderr: {}".format(line))
        if log_stdout:
            stdout_message = result.stdout.decode("utf-8").splitlines()
            for line in stdout_message:
                logger.debug("stdout: {}".format(line))
    logger.debug("all logging is done")
    return result


def bit_round(number, precision: int = 0):
    scale = 1

    if precision > 0:
        scale = 2 ** precision
        number *= scale
    elif precision < 0:
        scale = 2 ** (precision * -1)
        number /= scale

    number = round(number)

    if precision > 0:
        number /= scale
    elif precision < 0:
        number *= scale

    return number
