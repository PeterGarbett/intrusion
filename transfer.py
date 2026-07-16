"""Transfer files using scp via a subprocess rather than paramiko,
the overwhelming advantage being it is reliable"""

import subprocess

TIMEOUT = 120


def command(cli_list):
    """Run a command given a list of [command,parameters...]"""

    try:
        # check=True raises CalledProcessError on non-zero exit
        result = subprocess.run(
            cli_list, capture_output=True, text=True, timeout=TIMEOUT, check=True
        )
        print("Success")
        # print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        # Access error output from the exception
        print(f"Command failed with code {e.returncode}")
        print(f"Error output: {e.stderr}")
        return False


def send_file(filename, user, hostname, remote_path):
    """file transfer using system scp"""

    scp_command = ["/usr/bin/scp","-p", filename, user + "@" + hostname + ":" + remote_path]

    print("attempt to send", filename, "command=", scp_command)

    retcode = command(scp_command)

    return retcode


def main():
    """Entry point to test routine"""
    filename = "transfer.py"
    user = "embed"
    hostname = "garbett.cloudns.org"
    remote_path = "/home/embed/"

    retcode = send_file(filename, user, hostname, remote_path)


if __name__ == "__main__":
    main()
