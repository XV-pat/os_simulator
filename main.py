import threading
import time
from process_manager import ProcessManager
from memory_manager import MemoryManager
from file_manager import FileManager

class SimulatorOS:
    def __init__(self):
        self.pm = ProcessManager()
        self.mm = MemoryManager(total_pages=16) # 取 4 到 32 之间
        self.fm = FileManager()
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
                # ========== 文件系统命令 ==========
            elif action == "mkdir":
                if len(cmd) < 2:
                    print("用法: mkdir [path]")
                    continue
                self.fm.mkdir(cmd[1])
                
            elif action == "rmdir":
                if len(cmd) < 2:
                    print("用法: rmdir [path]")
                    continue
                self.fm.rmdir(cmd[1])
                
            elif action == "ls":
                path = cmd[1] if len(cmd) > 1 else '.'
                self.fm.show_dir(path)
                
            elif action == "cd":
                if len(cmd) < 2:
                    print("用法: cd [path]")
                    continue
                self.fm.cd(cmd[1])
                
            elif action == "pwd":
                print(self.fm.pwd())
                
            elif action == "touch": #创文件
                if len(cmd) < 2:
                    print("用法: touch [path]")
                    continue
                self.fm.touch(cmd[1])
                
            elif action == "cat": #查看文件
                if len(cmd) < 2:
                    print("用法: cat [path]")
                    continue
                content = self.fm.read(cmd[1])
                print("-" * 40)
                print(content)
                print("-" * 40)
                
            elif action == "write": #写文件内容
                if len(cmd) < 3:
                    print("用法: write [path] [content]")
                    continue
                self.fm.write(cmd[1], ' '.join(cmd[2:]), append=False)
                
            elif action == "append": #追加文件内容
                if len(cmd) < 3:
                    print("用法: append [path] [content]")
                    continue
                self.fm.write(cmd[1], ' '.join(cmd[2:]), append=True)
                
            elif action == "rm":
                if len(cmd) < 2:
                    print("用法: rm [path]")
                    continue
                self.fm.delete(cmd[1])
                
            elif action == "info": #查看文件信息
                if len(cmd) < 2:
                    print("用法: info [path]")
                    continue
                self.fm.show_info(cmd[1])
                
            elif action == "save": #文件信息的持久化保存，下面的load是取消
                self.fm.save()
                
            elif action == "load":
                self.fm.load()
                
            elif action == "exit":
                self.is_running = False
            ##以上就是所有的文件系统的命令
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