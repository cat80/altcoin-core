#!/usr/bin/python3
import subprocess
import os
import signal
import sys
import time


def find_and_kill_processes():
    """
    查找并终止包含特定关键词的进程。
    """
    # 1. 获取当前脚本的PID，避免“自杀”
    my_pid = os.getpid()
    print(f"当前脚本 PID: {my_pid}，将自动跳过此进程。")

    # 2. 运行 'ps -ef' 并获取输出
    try:
        # 使用 subprocess.run 来执行命令
        result = subprocess.run(
            ['ps', '-ef'],
            capture_output=True,
            text=True,
            check=True,
            encoding='utf-8'
        )
        process_list = result.stdout.strip().split('\n')

    except FileNotFoundError:
        print("[错误] 'ps' 命令未找到。请确保您在类 Unix 系统 (Linux/macOS) 上运行。")
        return
    except subprocess.CalledProcessError as e:
        print(f"[错误] 执行 'ps -ef' 失败: {e.stderr}")
        return
    except Exception as e:
        print(f"[错误] 获取进程列表时发生未知错误: {e}")
        return

    # 3. 定义您要查找的关键词
    keyword_1 = "python"  # 您的第一个关键词
    keyword_2 = "main.py"  # 您的第二个关键词

    print(f"\n--- 正在查找同时包含 '{keyword_1}' 和 '{keyword_2}' 的进程 ---")

    found_processes = []

    # 4. 遍历进程列表 (跳过第一行列标题)
    for line in process_list[1:]:
        if not line:
            continue

        try:
            parts = line.split()
            pid = int(parts[1])

            # 完整的命令行（通常是第8列及之后的所有内容）
            command_line = " ".join(parts[7:])

            # 5. 检查是否匹配关键词，并确保不是当前脚本
            if keyword_1 in command_line and keyword_2 in command_line and pid != my_pid:
                print(f"[找到匹配] PID: {pid:<8} | CMD: {command_line}")
                found_processes.append((pid, command_line))

        except (IndexError, ValueError):
            # 忽略解析失败的行（例如格式不正确的行）
            pass

    # 6. 如果没有找到，则告知用户
    if not found_processes:
        print("--- 未找到任何匹配的进程。 ---")
        return

    print(f"\n--- 准备终止 {len(found_processes)} 个进程 ---")

    # 7. 循环执行 kill -9
    for pid, command_line in found_processes:
        try:
            # os.kill 发送 SIGKILL 信号 (等同于 kill -9)
            os.kill(pid, signal.SIGKILL)
            print(f"  [成功] 已发送 'kill -9' 到 PID: {pid}")
        except ProcessLookupError:
            print(f"  [警告] 无法查找到 PID: {pid} (可能已提前退出)")
        except PermissionError:
            print(f"  [错误] 权限不足，无法终止 PID: {pid} (您可能需要使用 sudo 运行此脚本)")
        except Exception as e:
            print(f"  [错误] 终止 PID: {pid} 时发生未知错误: {e}")

    print("--- 操作完成 ---")


if __name__ == "__main__":
    print("===================== 进程终止脚本 =====================")
    print(" 警告：此脚本将使用 'kill -9' (SIGKILL) 强制终止进程。")
    print(" 这可能导致被终止进程的数据丢失或文件损坏。")
    print("==========================================================")

    try:
        # 增加一个最终确认步骤
        confirm = input("是否确定要继续执行？ (输入 'yes' 继续): ").strip().lower()
        if confirm == 'yes':
            print("正在执行...")
            time.sleep(1)  # 短暂暂停，让用户有机会看到
            find_and_kill_processes()
        else:
            print("操作已取消。")

    except KeyboardInterrupt:
        print("\n操作被用户(Ctrl+C)中断。")
        sys.exit(0)