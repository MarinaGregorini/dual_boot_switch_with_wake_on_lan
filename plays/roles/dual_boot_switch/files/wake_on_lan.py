import socket
import subprocess
import time
import sys
import os
import json
import paramiko
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor


def send_wol(mac, ip):
    """Send Wake-on-LAN packet."""
    try:
        mac_bytes = bytes.fromhex(mac.replace(':', ''))
        magic_packet = b'\xff' * 6 + mac_bytes * 16
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.sendto(magic_packet, (ip, 9))
        print(f"[WOL] Packet sent to {mac} ({ip})")
        return (True, mac)
    except Exception as e:
        print(f"[ERROR] Failed to send WOL to {mac} ({ip}): {str(e)}")
        return (False, mac)


def wait_for_host(ip, mac=None, timeout_minutes=5):
    """Keep sending WOL and wait for the host to respond to ping with timeout."""
    print(f"[WAITING] Waiting for {ip} to respond (timeout: {timeout_minutes} minutes)...")
    ping_cmd = ('ping', '-c', '1', '-W', '1', ip)
    start_time = datetime.now()
    timeout = timedelta(minutes=timeout_minutes)
    
    while datetime.now() - start_time < timeout:
        send_wol(mac, ip)
        if subprocess.call(
            ping_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        ) == 0:
            print(f"[SUCCESS] Host {ip}, {mac} responding!")
            return (True, mac)
        time.sleep(5)  # Espera 5 segundos entre tentativas
    
    print(f"[ERROR] Host {ip}, {mac} did not respond within {timeout_minutes} minutes.")
    return (False, mac)


def get_system(ip):
    ssh_password = os.getenv("SUDO_PASSWORD")
    ssh_user = os.getenv("SUDO_USER")
    if not ssh_password:
        raise ValueError("SUDO_PASSWORD is not defined!")
    if not ssh_user:
        raise ValueError("SUDO_USER is not defined!")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(ip, username=ssh_user, password=ssh_password, timeout=5)
        stdin, stdout, stderr = client.exec_command("uname -s")
        system = stdout.read().decode().strip().lower()
        return "ubuntu" if "linux" in system else "windows"
    except Exception as e:
        print(f"[ERROR] SSH failed for {ip}: {str(e)}")
        return "unknown"
    finally:
        client.close()


def process_host(host):
    """Process a single host"""
    mac = host.get('mac')
    ip = host.get('ip')
    print(f"\n[PROCESSING] Starting WOL for ({mac}, {ip})")
    success, _ = wait_for_host(ip, mac)
    if not success:
        return (False, mac, ip, "unknown")
    system = get_system(ip)
    return (True, mac, ip, system)


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} '<JSON_HOSTS_LIST>' ")
        sys.exit(1)
    try:
        json_str = sys.argv[1].strip("'\"")
        hosts = json.loads((json_str).strip('"\''))
    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid JSON: {str(e)}")
        print(f"Input recebido: {sys.argv[1]}")
        sys.exit(1)
    failed_hosts = []
    os_detected = {}
    with ThreadPoolExecutor(max_workers=12) as executor:
        results = list(executor.map(process_host, hosts))
    for result in results:
        success, mac, ip, system = result
        if not success:
            failed_hosts.append((mac, ip))
        os_detected[ip] = system
    print(json.dumps({
        "os_detected": os_detected,
        "failed_hosts": failed_hosts
    }))
    if failed_hosts:
        print(
            "\n[FAILED] The following hosts failed to wake up:",
            file=sys.stderr
        )
        for i, (mac, ip) in enumerate(failed_hosts, 1):
            print(f"{i}. {mac} {ip}")
        sys.exit(2 if len(failed_hosts) < len(hosts) else 1)
    else:
        print(
            "\n[SUCCESS] All hosts were successfully woken.",
            file=sys.stderr
        )
        sys.exit(0)


if __name__ == "__main__":
    main()
