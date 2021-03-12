__author__ = "6ru"

import logging
import subprocess
import yaml
#from pydub import AudioSegment
#from pydub.playback import play

CNT = 10
SEPARATOR = "==="

logger = logging.getLogger(__name__)


def print_separator():
    print(CNT * SEPARATOR)


def read_config(config):
    with open(config, 'r') as f:
        params = yaml.load(f, Loader=yaml.FullLoader)
    return params


def run_shell_cmd(cmd):
    """
    Takes a command and executes it with the help of Popen.

    :param cmd: the command to execute in form of a list
    :return: rc, status code of the process
    """
    # Run cmd
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Catch stdout and stderr
    stdout, stderr = process.communicate()

    rc = process.wait()

    # Logs result
    if stdout:
        logger.info(stdout.strip().decode("utf-8"))
    if stderr:
        logger.info(stderr.strip().decode("utf-8"))

    return rc


def run_cmd_with_output(cmd):
    """
    Takes a command and executes it with the help of Popen. The stdout will be received and returned.
    :param cmd: the command to execute in form of a list
    :return: stdout, a string containing the contents stdout
    """
    # Run cmd
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # Catch stdout and stderr
    stdout, stderr = process.communicate()

    return stdout.decode("utf-8")


def run_basic_shell_cmd(cmd):
    """
    Takes a command and executes it with the help of Popen.
    """

    # Run cmd
    subprocess.run(cmd, shell=True, check=True)


def wait_for_confirm():
    # Play audio alert to gather attention
    #https://freesound.org/people/SgtPepperArc360/sounds/344957/
    #wav = AudioSegment.from_wav("./alert.wav")
    #play(wav)

    is_done = False
    while not is_done:
        c = input("Please type 'y' to continue\n")
        if c.lower() == "y":
            is_done = True
