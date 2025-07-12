import time
import subprocess
import sys
import platform


def detect_os():
    active_os = platform.system()
    print(active_os)
    if active_os == "Linux":
        return "ubuntu"
    else:
        return "windows"


def get_active_users(active_os):
    """Returns list of active sessions excluding 'admindi',
    for Windows or Ubuntu."""
    if active_os == 'windows':
        try:
            result = subprocess.run(
                ['qwinsta'],
                capture_output=True,
                text=True,
                check=True
            )
            for line in result.stdout.splitlines():
                if 'Active' in line:
                    parts = line.split()
                    if len(parts) >= 3:
                        username = parts[0]
                        session_id = parts[2]
                        if username.lower() != 'admindi':
                            return session_id
                        else:
                            return False
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Failed to execute 'qwinsta': {e}")
            return False
    elif active_os == "ubuntu":
        try:
            result = subprocess.run(
                ['who', '-u'],
                capture_output=True,
                text=True,
                check=True
            )
            print("[DEBUG] 'who -u' output:")
            print(result.stdout)
            for line in result.stdout.splitlines():
                parts = line.split()
                if (len(parts) >= 1
                        and 'login screen' in line
                        and parts[0].lower() != 'admindi'):
                    user = (parts[0].lower())
                    return user
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Failed to execute 'who -u': {e}")
            return False


def notify_active_session(active_os):
    session = get_active_users(active_os)
    if session:
        if active_os == "windows":
            msg = "MANUTENÇÃO. O computador será reiniciado em 5 minutos. " \
                    "Por favor, guarde o seu trabalho."
            subprocess.run(['msg', session, msg], check=True)
        elif active_os == "ubuntu":
            uid = subprocess.run(
                ['id', '-u', session],
                capture_output=True,
                text=True
            ).stdout.strip()
            message = (
                'O computador será reiniciado em 5 minutos. '
                'Por favor, guarde o seu trabalho.'
            )
            subprocess.run([
                'sudo', '-u', session,
                'DISPLAY=:0',
                f'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{uid}/bus',
                'notify-send', '-u', 'critical', '-t', '300000',
                'MANUTENÇÃO', message
            ], check=True)
        print("[NOTICE] Waiting 5 minutes before proceeding...")
        time.sleep(30)
        return True
    else:
        print("[INFO] No active session detected. Proceeding...")
        return True


def windows_as_default(desired_config):
    """Set Windows as default boot in rEFInd (run locally from Ubuntu)."""
    print("[INFO] Setting Windows as default boot in rEFInd...")
    try:
        subprocess.run([
            'sudo',
            'cp',
            f'/boot/efi/EFI/refind/refind.conf{desired_config}',
            '/boot/efi/EFI/refind/refind.conf'
        ], check=True)
        subprocess.run(['sudo', 'systemctl', 'reboot'], check=True)
        print("[OK] Windows set as default and system rebooting...")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Failed to switch to Windows: {e}")
    return False


def ubuntu_as_default(desired_config):
    """Set Ubuntu as default boot in rEFInd (run locally from Windows)."""
    print("[INFO] Setting Ubuntu as default boot in rEFInd...")
    try:
        with open('mount_efi.txt', 'w') as f:
            f.write(f"select disk 0\nselect partition 1\nassign letter=S\nexit\n")
        subprocess.run(['diskpart', '/s', 'mount_efi.txt'], check=True)
        print(f"[OK] EFI partition mounted as S")
    except subprocess.CalledProcessError as e:
        if "is not free to be assigned" in str(e.stdout):
            print(
                f"[INFO] Drive letter: "
                f"is in use, trying next..."
            )
            raise
    subprocess.run(
        f'copy S:\\EFI\\refind\\'
        f'refind.conf{desired_config} '
        f'S:\\EFI\\refind\\refind.conf /Y',
        shell=True,
        check=True
    )
    print(
        f"[INFO] Unmounting EFI partition "
        f"S: before reboot..."
    )
    with open('unmount_efi.txt', 'w') as f:
        f.write(f"select disk 0\nselect partition 1\nremove letter=S\nexit\n")
    subprocess.run(['diskpart', '/s', 'unmount_efi.txt'], check=True)

    try:
        subprocess.run(
            f'dir S:',
            shell=True,
            check=True,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE
        )
        print("[WARNING] Drive still appears to be mounted!")
    except subprocess.CalledProcessError:
        print("[OK] Drive successfully unmounted")
        print("[INFO] Initiating system reboot...")
        subprocess.run(['shutdown', '/r', '/t', '0'], check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Failed during Ubuntu switch: {e}")


def lastOS_as_default(active_os, desired_config):
    print("[INFO] Restoring last OS as default boot in rEFInd...")
    if active_os == "ubuntu":
        return windows_as_default(desired_config)
    elif active_os == "windows":
        return ubuntu_as_default(desired_config)
    else:
        print("[ERROR] Unknown current OS")
        return False


# --- Main ---


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <ubuntu|windows|lastOS>")
        sys.exit(1)
    desired_os = sys.argv[1].lower()
    if desired_os not in ("ubuntu", "windows", "lastos"):
        print("[ERROR] Invalid system. Use 'ubuntu', 'windows', or 'lastOS'.")
        sys.exit(1)
    active_os = detect_os()
    print(f"[INFO] Current system OS: {active_os}")
    print(f"[INFO] Desired system: {desired_os}")
    if notify_active_session(active_os):
        desired_config = (f'.{desired_os}')
        if desired_os == "windows" and active_os == "ubuntu":
            success = windows_as_default(desired_config)
        elif desired_os == "ubuntu" and active_os == "windows":
            success = ubuntu_as_default(desired_config)
        elif desired_os == "lastos":
            success = lastOS_as_default(active_os, desired_config)
        else:
            print(f"[INFO] {desired_os} is already active. Nothing to do.")
            success = True
        if not success:
            print("[FAILURE] System switch failed.")
            sys.exit(1)

        print("[INFO] Success!")


if __name__ == "__main__":
    main()
