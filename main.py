import threading
import time
from process_manager import ProcessManager
from memory_manager import MemoryManager
# from file_manager import FileManager

class SimulatorOS:
    def __init__(self):
        self.pm = ProcessManager()
        self.mm = MemoryManager(total_pages=16) # 取 4 到 32 之间
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
        while self.is_running:
            cmd = input("root@os-sim# ").strip().split()
            if not cmd:
                continue
            
            action = cmd[0]
            if action == "create_process":
                # 用法: create_process [name] [priority] [time]
                self.pm.create_process(cmd[1], int(cmd[2]), int(cmd[3]))
                print(f"进程 {cmd[1]} 创建成功")
            elif action == "ps":
                self.pm.show_queues()
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