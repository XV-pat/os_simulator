from models import PCB, ProcessState

class ProcessManager:
    def __init__(self):
        self.ready_queue = []   # 就绪队列 [cite: 45]
        self.running_proc = None # 运行队列 (单核CPU，仅一个) [cite: 45, 46]
        self.blocked_queue = [] # 阻塞队列 [cite: 45]
        self.pid_counter = 1
        self.all_processes = {} # 记录所有存在的进程信息

    def create_process(self, name: str, priority: int, required_time: int) -> PCB:
        """进程的创建 [cite: 40]"""
        pcb = PCB(self.pid_counter, name, priority, required_time)
        self.all_processes[self.pid_counter] = pcb
        self.pid_counter += 1
        self.ready_queue.append(pcb)
        return pcb

    def kill_process(self, pid: int):
        """进程的撤销 [cite: 40]"""
        pass # TODO: 从所在队列移除，并通知内存管理器释放其占用的内存

    def schedule(self):
        """单处理器进程调度功能等调度算法实现 [cite: 46]
        (由 main.py 中的全局 Tick 触发)
        """
        # TODO: 1. 检查 running_proc 的时间片是否用完，若用完则放入 ready_queue
        # TODO: 2. 从 ready_queue 中选出优先级最高的进程投入运行
        pass
    
    def show_queues(self):
        """查看各进程状态、各进程队列内容 [cite: 51]"""
        pass # TODO: 格式化打印当前各队列的进程名和参数