import threading
import time
import random

class MemoryManager:
    def __init__(self, total_pages: int = 32):
        self.page_size = 1024  # 页面大小为1K [cite: 73]
        self.total_pages = total_pages # 用户内存容量为4页到32页 [cite: 74]
        self.memory_bitmap = [0] * total_pages # 0 表示空闲，1 表示占用
        self.lock = threading.Lock() # 两个线程保持同步 [cite: 68]
        
        # 启动后台监控线程
        self.monitor_thread = threading.Thread(target=self._tracker_thread, daemon=True)
        self.monitor_thread.start()

    def allocate(self, pid: int, pages_needed: int) -> list:
        """用于内存分配的接口 [cite: 66]"""
        with self.lock:
            # TODO: 实现连续或非连续的页分配算法，更新 bitmap
            pass
            
    def free(self, pid: int, pages: list):
        """释放内存页"""
        with self.lock:
            # TODO: 清理 bitmap 对应的页
            pass

    def _tracker_thread(self):
        """用于跟踪内存分配情况，并且打印内存信息的线程 [cite: 67]"""
        while True:
            time.sleep(5) # 每5秒打印一次
            with self.lock:
                # TODO: 打印内存的使用率、空闲页和占用分布
                pass