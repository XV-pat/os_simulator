import unittest
from unittest.mock import patch
import io
import sys
import threading
from main import SimulatorOS

class TestSimulatorBatch(unittest.TestCase):
    
    def run_sim_with_inputs(self, commands, test_name="未命名测试", show_logs=True):
        """
        测试辅助核心：用于模拟终端输入并捕获所有系统的 print 输出
        增加 show_logs 参数，控制是否在终端打印详细执行过程
        """
        # 确保最后一个命令永远是 exit，否则测试会卡死无法退出
        if commands[-1] != 'exit':
            commands.append('exit')
            
        captured_output = io.StringIO()
        # 将标准输出重定向到我们的“拦截器”
        sys.stdout = captured_output

        os_sim = SimulatorOS()
        # 启动后台全局时钟线程
        tick_thread = threading.Thread(target=os_sim.system_tick)
        tick_thread.start()
        
        # 使用 patch 替换内置的 input 函数，让它依次读取 commands 列表里的指令
        with patch('builtins.input', side_effect=commands):
            os_sim.shell()
            
        # 等待线程安全退出并恢复真实的屏幕标准输出
        tick_thread.join()
        sys.stdout = sys.__stdout__
        
        # 获取被拦截的所有系统日志
        out = captured_output.getvalue()
        
        # 将拦截到的日志打印到屏幕上，方便查错
        if show_logs:
            print(f"\n{'='*20} 🔽 [{test_name}] 详细日志 🔽 {'='*20}")
            print(out.strip())  
            print(f"{'='*20} 🔼 [{test_name}] 日志结束 🔼 {'='*20}\n")
            
        return out

    # ==========================================
    # 场景 1：文件系统基础与容错测试 (File System)
    # ==========================================
    def test_file_system_operations(self):
        inputs = [
            'mkdir /test_dir',
            'mkdir /test_dir',         # 故意创建同名目录，期望触发异常
            'touch /test_dir/1.txt',
            'rmdir /test_dir',         # 故意删除非空目录，期望触发异常
            'exit'
        ]
        out = self.run_sim_with_inputs(inputs, test_name="文件系统测试")
        
        # 断言正常逻辑是否通过
        self.assertIn("目录创建成功: /test_dir", out)
        self.assertIn("文件创建成功: /test_dir/1.txt", out)
        
        # 断言容错逻辑是否被 main.py 里的 except Exception 成功拦截并打印
        self.assertIn("执行异常: 目录 'test_dir' 已存在", out)
        self.assertIn("执行异常: 目录 '/test_dir' 非空，无法删除", out)

    # ==========================================
    # 场景 2：内存越界与资源释放测试 (Memory Limits)
    # ==========================================
    def test_memory_allocation_and_free(self):
        inputs = [
            'create_process p_huge 10 50 35',  # 申请35页，超过总容量32页，期望拒绝
            'create_process p_normal 10 50 5', # 正常申请5页
            'mem',                             # 查看内存分配是否正确
            'kill 1',                          # 强制撤销进程1
            'mem',                             # 再次查看内存确保资源已全部归还
            'exit'
        ]
        out = self.run_sim_with_inputs(inputs, test_name="内存分配与释放测试")
        
        self.assertIn("创建失败 (内存不足)", out)
        self.assertIn("分配内存页: [0, 1, 2, 3, 4]", out)
        self.assertIn("已强制撤销并释放资源", out)

    # ==========================================
    # 场景 3：进程状态流转测试 (Process State)
    # ==========================================
    def test_process_state_transitions(self):
        inputs = [
            'create_process p1 10 100 1',
            'create_process p2 5 100 1',
            'block 2',    # 将 p2 移入阻塞队列
            'ps',         # 打印队列查看 p2 是否真的在 BLOCKED 列表
            'unblock 2',  # 将 p2 恢复到就绪队列
            'exit'
        ]
        out = self.run_sim_with_inputs(inputs, test_name="进程状态流转测试")
        
        self.assertIn("进程 PID=2 已挂起", out)
        self.assertIn("进程 PID=2 已解除阻塞", out)
        self.assertIn("BLOCKED:", out)

    # ==========================================
    # 场景 4：瞎敲键盘与参数错误测试 (Bad Inputs)
    # ==========================================
    def test_shell_bad_commands(self):
        inputs = [
            'hello_world',                      # 随便敲的不存在的指令，期望触发 "未知命令"
            'create_process p_bad abc def',     # 凑够了4个参数绕过长度检查，但含字母，期望触发 ValueError
            'kill',                             # 故意少填 pid 参数，期望触发 IndexError
            'exit'
        ]
        out = self.run_sim_with_inputs(inputs, test_name="乱敲指令与瞎填参数测试")
        
        # 验证主循环的 try...except 拦截网是否足够稳固
        self.assertIn("未知命令: hello_world", out)
        self.assertIn("参数错误：时间、优先级或 PID 必须为纯数字格式", out)
        self.assertIn("参数错误：指令缺省，请检查输入格式", out)

if __name__ == '__main__':
    # verbosity=2 可以让测试框架在最下方打印出每个用例（如 test_shell_bad_commands）是否 ok
    unittest.main(verbosity=2)