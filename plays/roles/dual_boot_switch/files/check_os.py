import os
import sys
import json
import time
import subprocess
import paramiko
from concurrent.futures import ThreadPoolExecutor


def wait_for_host(ip):
    """Wait for the host to respond to ping."""
    cmd = ['ping', '-c', '1', '-W', '1', ip]
    result = subprocess.call(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    return result == 0


def get_system(host, desired_os):
    """Detects the OS and keeps checking until it matches
    desired_os or timeout."""
    ssh_password = os.getenv("SUDO_PASSWORD")
    ssh_user = os.getenv("SUDO_USER")
    ip = host["ip"]
    mac = host.get("mac", "")
    max_attempts = 60
    attempt = 0
    while attempt < max_attempts:
        attempt += 1
        print(f"[{ip}] Attempt {attempt}/{max_attempts}")
        if wait_for_host(ip):
            try:
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect(
                    ip,
                    username=ssh_user,
                    password=ssh_password,
                    timeout=5
                )
                stdin, stdout, _ = client.exec_command("uname -s")
                output = stdout.read().decode().strip().lower()
                os_detected = "ubuntu" if "linux" in output else "windows"
                client.close()
                if os_detected == desired_os or desired_os == "lastos":
                    print(f"[SUCCESS] {ip} now running {desired_os}")
                    return {
                        "ip": ip,
                        "mac": mac,
                        "os_detected": os_detected,
                        "status": "matched",
                        "attempts": attempt
                    }
                else:
                    print(
                        f"[INFO] {ip} running {os_detected}. "
                        f"Expected: {desired_os}"
                    )
            except Exception as e:
                print(f"[ERROR] {ip} SSH error: {str(e)}")
        time.sleep(10)
    print(f"[TIMEOUT] {ip} did not reach {desired_os} within 10 minutes")
    return {
        "ip": ip,
        "mac": mac,
        "os_detected": "timeout",
        "status": "failed",
        "attempts": attempt
    }


def main():
    if len(sys.argv) != 3:
        print(
            f"Usage: {sys.argv[0]} "
            f"'<JSON_HOSTS_LIST>' <ubuntu|windows|lastOS>"
        )
        sys.exit(1)
    try:
        hosts = json.loads(sys.argv[1].strip("'\""))
    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid JSON: {e}")
        sys.exit(1)
    desired_os = sys.argv[2].lower()
    if desired_os not in ("ubuntu", "windows", "lastos"):
        print(
            "[ERROR] Invalid desired OS. Use "
            "'ubuntu', 'windows', or 'lastOS'."
        )
        sys.exit(1)
    with ThreadPoolExecutor(max_workers=12) as executor:
        results = list(
            executor.map(
                lambda host: get_system(host, desired_os),
                hosts
            )
        )
    matched_hosts = [host for host in results if host["status"] == "matched"]
    failed_hosts = [host for host in results if host["status"] == "failed"]
    print(json.dumps({
        "matched_hosts": matched_hosts,
        "failed_hosts": failed_hosts,
        "desired_os": desired_os
    }, indent=2))
    sys.exit(1 if failed_hosts else 0)


if __name__ == "__main__":
    main()
