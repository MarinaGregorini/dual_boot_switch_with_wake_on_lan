# Dual Boot Switch With Wake-on-LAN Role

An Ansible role for remotely switching between Windows and Ubuntu in a dual-boot system using Wake-on-LAN, SSH e WinRM.

---

## Requirements

### Control Machine Requirements

* Ansible 2.9+
* Python 3.6+
* `python3-venv` and `python3-pip` packages
* `paramiko` (instalado automaticamente via `requirements.txt`)

### Target Machine Requirements

* Dual-boot system with Windows and Ubuntu
* rEFInd boot manager with pre-configured `.conf` files
* SSH habilitado no Ubuntu
* WinRM habilitado no Windows (porta 5985)
* Wake-on-LAN habilitado na BIOS
* Python 3 instalado em ambos sistemas
* `python3-venv` e `python3-pip` no Ubuntu
* Acesso `sudo` à partição EFI

---

## Role Variables

### Required Variables

Essas variáveis devem ser definidas na execução do playbook ou em arquivos separados:

#### Vault-protected credentials (`secrets.yml`):

```yaml
ssh_username_imagem_lab: <username>
ssh_password_imagem_lab: <password>
```

#### Parâmetros em tempo de execução (`-e`):

* `desired_os`: Sistema alvo (`ubuntu`, `windows` ou `lastos`)
* `nodes`: Grupo do inventário com os hosts de destino

#### Variáveis por host (no inventário):

Cada host de destino deve conter:

```ini
[grupo]
host1 mac=AA:BB:CC:DD:EE:FF
```

#### Variáveis internas (`vars/main.yml`):

* `script_dir`: Caminho da role
* `venv_path`: Caminho do virtualenv
* `venv_python`: Caminho do binário Python no virtualenv
* `requirements_file`: Requisitos Python (pip)
* `log_dir`: Diretório para logs

---

## Usage Example

```bash
ansible-playbook -i ./inventories \
  --ask-vault-pass \
  plays/dual_boot_switch.yml \
  -e "desired_os=ubuntu nodes=test" \
  --ask-become-pass
```

### Explicação dos parâmetros:

* `-i`: Caminho para o inventário
* `--ask-vault-pass`: Solicita senha para descriptografar `secrets.yml`
* `-e`: Define variáveis extras (`desired_os` e `nodes`)
* `--ask-become-pass`: Solicita senha sudo (para configurar EFI, instalar pacotes, etc)

---

## Target Machine Configuration

### Arquivos exigidos:

* `/boot/efi/EFI/refind/refind.conf.windows`
* `/boot/efi/EFI/refind/refind.conf.ubuntu`
* `/boot/efi/EFI/refind/refind.conf.lastOS`

### Conteúdo esperado:

#### `refind.conf.windows`

```ini
default_selection windows
```

#### `refind.conf.ubuntu`

```ini
default_selection ubuntu
```

#### `refind.conf.lastOS`

```ini
# Deixe a seleção comentada
```

---

## Como Funciona

1. Cria ambiente virtual Python local
2. Instala dependências via `requirements.txt`
3. Para cada host:

   * Resolve IP via DNS
   * Envia pacote Wake-on-LAN
   * Aguarda resposta via ping
   * Detecta sistema atual via SSH (Ubuntu) ou WinRM (Windows)
   * Cria ambiente virtual e copia script remoto
   * Executa `dual_boot_switcher.py` para trocar sistema operacional via rEFInd
   * Aguarda e verifica se o sistema alvo foi ativado
   * Registra logs em caso de falha ou inconsistência

---

## Logs

Logs são salvos automaticamente em:

* `logs/wol_failures_*.log` – Hosts que não responderam ao Wake-on-LAN
* `logs/dual_boot_failures.log` – Hosts que falharam na troca de sistema
* `logs/os_mismatches.log` – Hosts que reiniciaram, mas com OS incorreto

---

## Troubleshooting

### Problemas comuns:

* **WOL não funciona:** verifique configurações de BIOS e placa de rede
* **WinRM falha:** verifique firewall, porta 5985 e permissões
* **Permissões EFI:** scripts exigem acesso de superusuário para modificar arquivos do `rEFInd`
* **Erro de parsing JSON:** logs indicarão problemas com os scripts Python

---

