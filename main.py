# main.py
import threading
import time
from process_manager import ProcessManager
from memory_manager import MemoryManager
from file_manager import FileManager

class SimulatorOS:
    def __init__(self):
        self.mm = MemoryManager(total_pages=32) # 取 4 到 32 之间
        # 关键修正：将内存管理器注入，让进程创建时能申请到内存
        self.pm = ProcessManager(memory_manager=self.mm) 
        self.fm = FileManager()
        self.is_running = True

    def system_tick(self):
        """全局时钟，模拟时间流逝驱动系统流转"""
        while self.is_running:
            time.sleep(1) # 以一秒钟作为时间片单位进行推进
            self.pm.schedule()

    def shell(self):
        """模拟命令行终端"""
        print("=== 欢迎进入 OS Simulator ===")
        print("输入 'help' 查看所有可用指令")
        
        while self.is_running:
            try:
                cmd_input = input("root@os-sim# ").strip()
                if not cmd_input:
                    continue
                
                cmd = cmd_input.split()
                action = cmd[0]
                
                # ========== 系统级与内存指令 ==========
                if action == "exit":
                    self.is_running = False
                    print("系统正在安全关闭...")
                    break
                elif action == "help":
                    self._show_help()
                elif action == "mem":
                    status = self.mm.get_status()
                    print(f"\n[内存状态] 使用率: {status['usage_rate']:.2f}% | 占用: {status['used_pages']}页 | 空闲: {status['free_pages']}页")
                    print(f"位图: {status['bitmap']}\n")

                # ========== 进程管理指令 ==========
                elif action == "create_process":
                    # 用法: create_process [name] [priority] [time] [pages]
                    if len(cmd) < 4:
                        print("用法: create_process [name] [priority] [time] [可选: pages]")
                        continue
                    pages = int(cmd[4]) if len(cmd) > 4 else 1
                    pcb = self.pm.create_process(cmd[1], int(cmd[2]), int(cmd[3]), pages)
                    if pcb:
                        print(f"进程 {cmd[1]} (PID={pcb.pid}) 创建成功，分配内存页: {pcb.memory_pages}")
                    else:
                        print(f"进程 {cmd[1]} 创建失败 (内存不足)")
                        
                elif action == "ps":
                    self.pm.show_queues()
                elif action == "kill":
                    if self.pm.kill_process(int(cmd[1])):
                        print(f"进程 PID={cmd[1]} 已强制撤销并释放资源")
                    else:
                        print(f"未找到 PID={cmd[1]} 的进程")
                elif action == "block":
                    self.pm.block_process(int(cmd[1]))
                    print(f"进程 PID={cmd[1]} 已挂起")
                elif action == "unblock":
                    self.pm.unblock_process(int(cmd[1]))
                    print(f"进程 PID={cmd[1]} 已解除阻塞")

                # ========== 文件系统指令 ==========
                elif action == "mkdir":
                    self.fm.mkdir(cmd[1])
                elif action == "rmdir":
                    self.fm.rmdir(cmd[1])
                elif action == "ls":
                    path = cmd[1] if len(cmd) > 1 else '.'
                    self.fm.show_dir(path)
                elif action == "cd":
                    self.fm.cd(cmd[1])
                elif action == "pwd":
                    print(self.fm.pwd())
                elif action == "touch":
                    self.fm.touch(cmd[1])
                elif action == "cat":
                    print("-" * 40)
                    print(self.fm.read(cmd[1]))
                    print("-" * 40)
                elif action == "write":
                    self.fm.write(cmd[1], ' '.join(cmd[2:]), append=False)
                elif action == "append":
                    self.fm.write(cmd[1], ' '.join(cmd[2:]), append=True)
                elif action == "rm":
                    self.fm.delete(cmd[1])
                elif action == "info":
                    self.fm.show_info(cmd[1])
                elif action == "save":
                    self.fm.save()
                elif action == "load":
                    self.fm.load()
                else:
                    print(f"未知命令: {action}")
                    
            except ValueError:
                print("参数错误：时间、优先级或 PID 必须为纯数字格式。")
            except IndexError:
                print("参数错误：指令缺省，请检查输入格式。")
            except Exception as e:
                # 捕获文件系统自定义的错误或其他预期外异常
                print(f"执行异常: {e}")

    def _show_help(self):
        print("\n--- 可用指令清单 ---")
        print("进程: create_process <name> <pri> <time> [pages], ps, kill <pid>, block <pid>, unblock <pid>")
        print("内存: mem")
        print("文件: ls, cd, pwd, mkdir, rmdir, touch, cat, write, append, rm, info, save, load")
        print("系统: help, exit\n")

if __name__ == "__main__":
    os_sim = SimulatorOS()
    
    tick_thread = threading.Thread(target=os_sim.system_tick)
    tick_thread.start()
    
    os_sim.shell()
    
    tick_thread.join()