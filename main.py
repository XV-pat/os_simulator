import threading
import time
import sys
from process_manager import ProcessManager
from memory_manager import MemoryManager
# from file_manager import FileManager


def _setup_console_encoding():
    """在 Windows 下统一使用 UTF-8，避免运行面板出现中文乱码。"""
    if sys.platform.startswith("win"):
        try:
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8")
            if hasattr(sys.stderr, "reconfigure"):
                sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            # 编码设置失败时不影响主流程。
            pass


_setup_console_encoding()

class SimulatorOS:
    def __init__(self):
        self.mm = MemoryManager(total_pages=16) # 取 4 到 32 之间
        self.pm = ProcessManager(memory_manager=self.mm)
        # self.fm = FileManager()
        self.is_running = True

    def system_tick(self):
        """全局时钟，模拟时间流逝驱动系统流转"""
        while self.is_running:
            time.sleep(1) # 以一秒钟作为时间片单位进行推进 [cite: 56]
            self.pm.schedule()

    def shell(self):
        """模拟命令行终端"""
        print("=== 欢迎进入 OS Simulator ===")
        print("输入 help 查看命令")
        while self.is_running:
            cmd = input("root@os-sim# ").strip().split()
            if not cmd:
                continue
            
            action = cmd[0]
            if action in ("help", "?"):
                print("可用命令:")
                print("  create_process <name> <priority> <required_time> [pages]")
                print("  kill <pid>")
                print("  block <pid>")
                print("  unblock <pid>")
                print("  ps")
                print("  mem")
                print("  exit")
            elif action == "create_process":
                # 用法: create_process [name] [priority] [time] [pages]
                if len(cmd) < 4:
                    print("参数不足。用法: create_process <name> <priority> <required_time> [pages]")
                    continue
                try:
                    priority = int(cmd[2])
                    required_time = int(cmd[3])
                    pages = int(cmd[4]) if len(cmd) > 4 else 1
                except ValueError:
                    print("priority/required_time/pages 必须为整数")
                    continue

                proc = self.pm.create_process(cmd[1], priority, required_time, pages)
                if proc is None:
                    print("进程创建失败: 内存不足")
                else:
                    print(f"进程 {proc.name} 创建成功，PID={proc.pid}, 内存页={proc.memory_pages}")
            elif action == "kill":
                if len(cmd) != 2:
                    print("用法: kill <pid>")
                    continue
                try:
                    pid = int(cmd[1])
                except ValueError:
                    print("pid 必须为整数")
                    continue
                ok = self.pm.kill_process(pid)
                print("进程已撤销" if ok else "未找到该进程")
            elif action == "block":
                if len(cmd) != 2:
                    print("用法: block <pid>")
                    continue
                try:
                    pid = int(cmd[1])
                except ValueError:
                    print("pid 必须为整数")
                    continue
                ok = self.pm.block_process(pid)
                print("进程已阻塞" if ok else "阻塞失败: 未找到该进程")
            elif action == "unblock":
                if len(cmd) != 2:
                    print("用法: unblock <pid>")
                    continue
                try:
                    pid = int(cmd[1])
                except ValueError:
                    print("pid 必须为整数")
                    continue
                ok = self.pm.unblock_process(pid)
                print("进程已唤醒" if ok else "唤醒失败: 未找到该进程")
            elif action == "ps":
                self.pm.show_queues()
            elif action == "mem":
                status = self.mm.get_status()
                print("\n===== 内存状态 =====")
                print(f"已用页: {status['used_pages']}/{status['total_pages']}")
                print(f"空闲页: {status['free_pages']}")
                print(f"使用率: {status['usage_rate']:.2f}%")
                print(f"位图: {status['bitmap']}")
                print(f"分配表: {status['allocations'] if status['allocations'] else '<empty>'}")
                print("====================\n")
            elif action == "exit":
                self.is_running = False
            else:
                print(f"未知命令: {action}")

if __name__ == "__main__":
    os_sim = SimulatorOS()
    
    # 启动硬件时钟线程
    tick_thread = threading.Thread(target=os_sim.system_tick)
    tick_thread.start()
    
    # 启动交互主线程
    os_sim.shell()
    
    tick_thread.join()