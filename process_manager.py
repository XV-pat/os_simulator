from models import PCB, ProcessState
import threading

class ProcessManager:
    def __init__(self, memory_manager=None, default_time_slice: int = 2):
        self.ready_queue = []   # 就绪队列 [cite: 45]
        self.running_proc = None # 运行队列 (单核CPU，仅一个) [cite: 45, 46]
        self.blocked_queue = [] # 阻塞队列 [cite: 45]
        self.pid_counter = 1
        self.all_processes = {} # 记录所有存在的进程信息
        self.memory_manager = memory_manager
        self.default_time_slice = max(1, default_time_slice)
        self.lock = threading.Lock()

    def set_memory_manager(self, memory_manager):
        self.memory_manager = memory_manager

    def _get_process(self, pid: int):
        return self.all_processes.get(pid)

    def _pop_from_queue(self, queue: list, pid: int):
        for idx, proc in enumerate(queue):
            if proc.pid == pid:
                return queue.pop(idx)
        return None

    def create_process(self, name: str, priority: int, required_time: int, pages_needed: int = 1):
        """进程的创建 [cite: 40]"""
        with self.lock:
            pid = self.pid_counter
            allocated_pages = []
            if self.memory_manager:
                allocated_pages = self.memory_manager.allocate(pid, pages_needed)
                if pages_needed > 0 and not allocated_pages:
                    return None

            pcb = PCB(pid, name, priority, required_time)
            pcb.memory_pages = allocated_pages
            self.all_processes[pid] = pcb
            self.pid_counter += 1
            self.ready_queue.append(pcb)
            return pcb

    def kill_process(self, pid: int):
        """进程的撤销 [cite: 40]"""
        with self.lock:
            target = None
            if self.running_proc and self.running_proc.pid == pid:
                target = self.running_proc
                self.running_proc = None
            if target is None:
                target = self._pop_from_queue(self.ready_queue, pid)
            if target is None:
                target = self._pop_from_queue(self.blocked_queue, pid)
            if target is None:
                return False

            target.state = ProcessState.TERMINATED
            if self.memory_manager and target.memory_pages:
                self.memory_manager.free(target.pid, target.memory_pages)
                target.memory_pages = []
            return True

    def block_process(self, pid: int):
        with self.lock:
            target = None
            if self.running_proc and self.running_proc.pid == pid:
                target = self.running_proc
                self.running_proc = None
            if target is None:
                target = self._pop_from_queue(self.ready_queue, pid)
            if target is None:
                return False
            target.state = ProcessState.BLOCKED
            self.blocked_queue.append(target)
            return True

    def unblock_process(self, pid: int):
        with self.lock:
            target = self._pop_from_queue(self.blocked_queue, pid)
            if target is None:
                return False
            target.state = ProcessState.READY
            self.ready_queue.append(target)
            return True

    def grow_process_memory(self, pid: int, pages: int) -> bool:
        """为指定进程追加内存页。"""
        with self.lock:
            if not self.memory_manager or pages <= 0:
                return False
            target = self._get_process(pid)
            if target is None or target.state == ProcessState.TERMINATED:
                return False
            new_pages = self.memory_manager.allocate(pid, pages)
            if len(new_pages) != pages:
                return False
            target.memory_pages.extend(new_pages)
            return True

    def shrink_process_memory(self, pid: int, pages: int) -> bool:
        """为指定进程释放部分内存页（从尾部回收）。"""
        with self.lock:
            if not self.memory_manager or pages <= 0:
                return False
            target = self._get_process(pid)
            if target is None or target.state == ProcessState.TERMINATED:
                return False
            if pages > len(target.memory_pages):
                return False
            release_pages = target.memory_pages[-pages:]
            freed = self.memory_manager.free(pid, release_pages)
            if freed != pages:
                return False
            target.memory_pages = target.memory_pages[:-pages]
            return True

    def compact_memory(self) -> bool:
        """触发内存紧凑，并同步刷新所有 PCB 的页索引。"""
        with self.lock:
            if not self.memory_manager:
                return False
            result = self.memory_manager.compact()
            after = result.get("after", {})
            for pid, pcb in self.all_processes.items():
                if pcb.state == ProcessState.TERMINATED:
                    continue
                pcb.memory_pages = after.get(pid, [])[:]
            return True

    def _dispatch_next(self):
        if not self.ready_queue:
            return
        # 优先级越高越先运行；同优先级时 PID 小者优先。
        next_proc = max(self.ready_queue, key=lambda p: (p.priority, -p.pid))
        self.ready_queue.remove(next_proc)
        next_proc.state = ProcessState.RUNNING
        next_proc.time_slice = max(1, min(5, self.default_time_slice + next_proc.priority // 3))
        self.running_proc = next_proc
        print(f"[Scheduler] 调度进程 PID={next_proc.pid} NAME={next_proc.name} TIME_SLICE={next_proc.time_slice}")

    def schedule(self):
        """单处理器进程调度功能等调度算法实现 [cite: 46]
        (由 main.py 中的全局 Tick 触发)
        """
        with self.lock:
            if self.running_proc:
                proc = self.running_proc
                proc.run_time += 1
                proc.time_slice -= 1

                if proc.run_time >= proc.required_time:
                    print(f"[Scheduler] 进程完成 PID={proc.pid} NAME={proc.name}")
                    proc.state = ProcessState.TERMINATED
                    if self.memory_manager and proc.memory_pages:
                        self.memory_manager.free(proc.pid, proc.memory_pages)
                        proc.memory_pages = []
                    self.running_proc = None
                elif proc.time_slice <= 0:
                    proc.state = ProcessState.READY
                    self.ready_queue.append(proc)
                    print(f"[Scheduler] 时间片到期，进程回到就绪队列 PID={proc.pid} NAME={proc.name}")
                    self.running_proc = None

            if self.running_proc is None:
                self._dispatch_next()
    
    def show_queues(self):
        """查看各进程状态、各进程队列内容 [cite: 51]"""
        with self.lock:
            def fmt(proc: PCB) -> str:
                return (
                    f"PID={proc.pid},NAME={proc.name},PRI={proc.priority},"
                    f"STATE={proc.state.value},RUN={proc.run_time}/{proc.required_time},"
                    f"SLICE={proc.time_slice},MEM={proc.memory_pages}"
                )

            running_text = fmt(self.running_proc) if self.running_proc else "<empty>"
            ready_text = [fmt(proc) for proc in self.ready_queue] or ["<empty>"]
            blocked_text = [fmt(proc) for proc in self.blocked_queue] or ["<empty>"]

            print("\n===== 进程队列状态 =====")
            print(f"RUNNING: {running_text}")
            print("READY:")
            for item in ready_text:
                print(f"  - {item}")
            print("BLOCKED:")
            for item in blocked_text:
                print(f"  - {item}")
            print("========================\n")