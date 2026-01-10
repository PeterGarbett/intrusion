"""Transfer files using scp via a subprocess rather than paramiko,
the overwhelming advantage being it is reliable"""

import subprocess

TIMEOUT = 120


def command(cli_list):
    """Run a command given a list of [command,parameters...]"""

    try:
        result = subprocess.run(
            cli_list, capture_output=True, text=True, timeout=TIMEOUT, check=True
        )
        if result.returncode != 0:
            response = result.stderr
            print(response)
            return False
        return True

    except Exception as err:
        print(err)
        return False


def send_file(filename, user, hostname, remote_path):
    """file transfer using system scp"""

    scp_command = ["/usr/bin/scp", filename, user + "@" + hostname + ":" + remote_path]

    print("attempt to send", filename, "command=", scp_command)

    retcode = command(scp_command)

    return retcode
