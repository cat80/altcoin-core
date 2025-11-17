import subprocess
import sys
import time
import psutil

def start_all():
    # --- 请根据你的环境修改以下配置 ---

    # 1. 节点配置
    base_port_or_id = 17880  # 你的配置文件起始编号
    num_nodes = 2  # 你想启动的节点总数

    # 2. WSL 中的路径配置
    # WSL 中的 Python 解释器路径
    wsl_python_executable = "/home/cat80/.virtualenvs/altcoin-core/bin/python"
    # WSL 中的主脚本路径
    wsl_script_path = "/mnt/d/prj/web3/altcoin-core/src/main.py"
    # WSL 中的配置文件目录
    wsl_config_dir = "/mnt/d/prj/web3/altcoin-core/src/config"

    # --- 配置结束 ---

    print(f"准备启动 {num_nodes} 个 WSL 节点...")

    for index in range(num_nodes):
        node_id = base_port_or_id + index*2

        # 假设你的配置文件名是 nodeXXXXX_config.yaml
        config_file_name = f"node{node_id}_config.yaml"
        wsl_config_path = f"{wsl_config_dir}/{config_file_name}"

        # 要在 WSL 内部执行的完整命令
        linux_cmd = f"{wsl_python_executable} {wsl_script_path} {node_id }"

        # 在 Windows 中使用 'start' 命令来为 wsl.exe 打开一个新窗口
        # 'start "Title" wsl.exe <command>'
        cmd_string = f'start "WSL Node {node_id}" cmd /k wsl.exe {linux_cmd}'

        print(f"正在执行: {cmd_string}")
        # 备注：我们假设你的 Python 脚本 (main.py) 是一个长期运行的服务，
        # 所以 wsl.exe 进程会保持存活，窗口也不会自动关闭。
        subprocess.Popen(cmd_string, shell=True)

        # 稍微错开启动时间
        if index == 0:
            print('第一个节点启动后等待1.5秒...')
            time.sleep(1.5)
        else:
            time.sleep(0.5)

    print(f"全部 {num_nodes} 个节点的启动命令已发出。")


import subprocess


def stop_all():
    prefix = "wsl.exe"
    script_filename = 'altcoin-core/src/main.py'
    killed_count = 0

    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # print(proc)
            # print(proc.info)
            if not proc.info['cmdline']:
                continue
            cmd_line_str = " ".join(proc.info['cmdline'])
            # print(cmd_line_str)
            # 我们这里假设 'P2P Node X' 是作为参数传给了脚本
            # 比如 python test_app.py "P2P Node 1"
            if script_filename in cmd_line_str and prefix in cmd_line_str:
                print(f"  找到匹配进程 (PID: {proc.info['pid']}): {cmd_line_str}")

                p = psutil.Process(proc.info['pid'])
                p.terminate()
                killed_count += 1

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass


if __name__ == "__main__":
    # 重要：请确保你的配置文件已存在于 WSL 路径中
    # 例如: /mnt/d/prj/web3/altcoin-core/src/config/node12231_config.yaml
    #      /mnt/d/prj/web3/altcoin-core/src/config/node12232_config.yaml
    #      /mnt/d/prj/web3/altcoin-core/src/config/node12233_config.yaml
    if len(sys.argv) >0 and sys.argv[-1] == 'killall':
        stop_all()
    else:
        start_all()