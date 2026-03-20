# file_manager.py
"""
文件系统管理器 - 提供文件和目录管理功能
"""

import time
import pickle
from typing import Dict, List, Optional


# ==================== 异常定义 ====================
class FileSystemError(Exception):
    pass

class FileNotFoundError(FileSystemError):
    pass

class FileExistsError(FileSystemError):
    pass

class NotADirectoryError(FileSystemError):
    pass

class IsADirectoryError(FileSystemError):
    pass

class DirectoryNotEmptyError(FileSystemError):
    pass


# ==================== 数据模型 ====================
class Entry:
    """文件系统条目基类"""
    def __init__(self, name: str, parent=None):
        self.name = name
        self.parent = parent
        self.created = time.time()
        self.modified = time.time()
    
    def get_path(self) -> str:
        """获取绝对路径"""
        if self.parent is None:
            return '/'
        parts = []
        cur = self
        while cur.parent:
            parts.append(cur.name)
            cur = cur.parent
        return '/' + '/'.join(reversed(parts))
    
    def is_file(self) -> bool:
        return isinstance(self, File)
    
    def is_dir(self) -> bool:
        return isinstance(self, Directory)


class File(Entry):
    """普通文件"""
    def __init__(self, name: str, parent=None, content: str = ''):
        super().__init__(name, parent)
        self._content = content
    
    def read(self) -> str:
        self.modified = time.time()
        return self._content
    
    def write(self, content: str, append: bool = False):
        if append:
            self._content += content
        else:
            self._content = content
        self.modified = time.time()
    
    @property
    def size(self) -> int:
        return len(self._content)


class Directory(Entry):
    """目录"""
    def __init__(self, name: str, parent=None):
        super().__init__(name, parent)
        self._entries: Dict[str, Entry] = {}
    
    def add(self, entry: Entry):
        if entry.name in self._entries:
            raise FileExistsError(f"'{entry.name}' already exists")
        self._entries[entry.name] = entry
        entry.parent = self
    
    def remove(self, name: str):
        if name not in self._entries:
            raise FileNotFoundError(f"'{name}' not found")
        del self._entries[name]
    
    def get(self, name: str) -> Optional[Entry]:
        return self._entries.get(name)
    
    def list(self) -> List[str]:
        return list(self._entries.keys())
    
    def is_empty(self) -> bool:
        return len(self._entries) == 0


# ==================== 路径解析器 ====================
class PathResolver:
    """路径解析器"""
    def __init__(self, root: Directory, cwd: Directory):
        self.root = root
        self.cwd = cwd
    
    def resolve(self, path: str) -> Entry:
        """解析路径，返回Entry对象"""
        if not path:
            raise FileSystemError("Empty path")
        
        if path.startswith('/'):
            current = self.root
            parts = [p for p in path.split('/')[1:] if p]
        else:
            current = self.cwd
            parts = [p for p in path.split('/') if p]
        
        for part in parts:
            if part == '.':
                continue
            if part == '..':
                if current.parent:
                    current = current.parent
                continue
            
            if not current.is_dir():
                raise NotADirectoryError(f"'{current.name}' is not a directory")
            
            entry = current.get(part)
            if entry is None:
                raise FileNotFoundError(f"'{part}' not found")
            current = entry
        
        return current
    
    def resolve_parent(self, path: str):
        """解析父目录和最后组件名"""
        if path == '/':
            raise FileSystemError("Cannot operate on root")
        
        path = path.rstrip('/')
        if path.startswith('/'):
            parts = [p for p in path.split('/')[1:] if p]
        else:
            parts = [p for p in path.split('/') if p]
        
        if not parts:
            raise FileSystemError(f"Invalid path: {path}")
        
        last = parts[-1]
        parent_path = '/' + '/'.join(parts[:-1]) if len(parts) > 1 else '/'
        
        parent = self.resolve(parent_path)
        if not parent.is_dir():
            raise NotADirectoryError(f"'{parent_path}' is not a directory")
        
        return parent, last


# ==================== 文件管理器主类 ====================
class FileManager:
    """
    文件管理器 - 提供完整的文件系统操作
    
    与 ProcessManager、MemoryManager 保持一致的接口风格
    """
    
    def __init__(self):
        """初始化文件系统"""
        self.root = Directory('')
        self.root.parent = None
        self.cwd = self.root
        self._resolver = PathResolver(self.root, self.cwd)
        print("文件系统初始化完成")
    
    def _update_resolver(self):
        """更新解析器的当前目录"""
        self._resolver.cwd = self.cwd
    
    # ==================== 目录操作 ====================
    
    def mkdir(self, path: str):
        """创建目录"""
        self._update_resolver()
        parent, name = self._resolver.resolve_parent(path)
        
        if parent.get(name):
            raise FileExistsError(f"目录 '{name}' 已存在")
        
        parent.add(Directory(name, parent))
        print(f"目录创建成功: {path}")
    
    def rmdir(self, path: str):
        """删除空目录"""
        self._update_resolver()
        target = self._resolver.resolve(path)
        
        if not target.is_dir():
            raise NotADirectoryError(f"'{path}' 不是目录")
        
        if not target.is_empty():
            raise DirectoryNotEmptyError(f"目录 '{path}' 非空，无法删除")
        
        if target.parent:
            target.parent.remove(target.name)
            print(f"目录删除成功: {path}")
    
    def ls(self, path: str = '.') -> List[str]:
        """列出目录内容"""
        self._update_resolver()
        target = self._resolver.resolve(path)
        
        if not target.is_dir():
            raise NotADirectoryError(f"'{path}' 不是目录")
        
        entries = target.list()
        return entries
    
    def show_dir(self, path: str = '.'):
        """显示目录内容（带图标）"""
        entries = self.ls(path)
        if not entries:
            print("  (空目录)")
            return
        
        for name in sorted(entries):
            entry = self._resolver.resolve(f"{path}/{name}" if path != '.' else name)
            if entry.is_dir():
                print(f"{name}/")
            else:
                print(f"{name} ({entry.size} 字节)")
    
    # ==================== 文件操作 ====================
    
    def touch(self, path: str, content: str = ''):
        """创建文件（存在则更新修改时间）"""
        self._update_resolver()
        parent, name = self._resolver.resolve_parent(path)
        
        existing = parent.get(name)
        if existing:
            if existing.is_file():
                existing.modified = time.time()
                print(f"文件已存在，更新时间戳: {path}")
                return
            raise FileExistsError(f"'{name}' 是目录")
        
        parent.add(File(name, parent, content))
        print(f"文件创建成功: {path}")
    
    def create(self, path: str, content: str = ''):
        """创建文件（存在则覆盖）"""
        self._update_resolver()
        parent, name = self._resolver.resolve_parent(path)
        
        existing = parent.get(name)
        if existing:
            if existing.is_file():
                parent.remove(name)
            else:
                raise IsADirectoryError(f"'{name}' 是目录")
        
        parent.add(File(name, parent, content))
        print(f"文件创建/覆盖成功: {path}")
    
    def read(self, path: str) -> str:
        """读取文件内容"""
        self._update_resolver()
        target = self._resolver.resolve(path)
        
        if not target.is_file():
            raise IsADirectoryError(f"'{path}' 是目录")
        
        return target.read()
    
    def write(self, path: str, content: str, append: bool = False):
        """写入文件内容"""
        self._update_resolver()
        target = self._resolver.resolve(path)
        
        if not target.is_file():
            raise IsADirectoryError(f"'{path}' 是目录")
        
        target.write(content, append)
        print(f"写入成功: {path}")
    
    def delete(self, path: str):
        """删除文件"""
        self._update_resolver()
        target = self._resolver.resolve(path)
        
        if not target.is_file():
            raise IsADirectoryError(f"'{path}' 是目录，请用 rmdir")
        
        if target.parent:
            target.parent.remove(target.name)
            print(f"文件删除成功: {path}")
    
    # ==================== 路径操作 ====================
    
    def cd(self, path: str):
        """切换目录"""
        self._update_resolver()
        target = self._resolver.resolve(path)
        
        if not target.is_dir():
            raise NotADirectoryError(f"'{path}' 不是目录")
        
        self.cwd = target
        self._update_resolver()
    
    def pwd(self) -> str:
        """获取当前路径"""
        return self.cwd.get_path()
    
    def exists(self, path: str) -> bool:
        """检查路径是否存在"""
        try:
            self._update_resolver()
            self._resolver.resolve(path)
            return True
        except FileNotFoundError:
            return False
    
    # ==================== 信息查询 ====================
    
    def get_info(self, path: str) -> dict:
        """获取文件/目录信息"""
        target = self._resolver.resolve(path)
        return {
            'name': target.name,
            'path': target.get_path(),
            'type': 'file' if target.is_file() else 'directory',
            'size': target.size if target.is_file() else None,
            'created': target.created,
            'modified': target.modified,
        }
    
    def show_info(self, path: str):
        """显示文件/目录详细信息"""
        info = self.get_info(path)
        print(f"名称: {info['name']}")
        print(f"类型: {info['type']}")
        print(f"路径: {info['path']}")
        if info['size'] is not None:
            print(f"大小: {info['size']} 字节")
        print(f"创建时间: {time.ctime(info['created'])}")
        print(f"修改时间: {time.ctime(info['modified'])}")
    
    # ==================== 持久化 ====================
    
    def save(self, filename: str = "fs_state.dat"):
        """保存文件系统状态"""
        try:
            state = self._serialize()
            with open(filename, 'wb') as f:
                pickle.dump(state, f)
            print(f"文件系统已保存到: {filename}")
            return True
        except Exception as e:
            print(f"保存失败: {e}")
            return False
    
    def load(self, filename: str = "fs_state.dat"):
        """加载文件系统状态"""
        try:
            with open(filename, 'rb') as f:
                state = pickle.load(f)
            self._deserialize(state)
            self._update_resolver()
            print(f"文件系统已从 {filename} 加载")
            return True
        except FileNotFoundError:
            return False
        except Exception as e:
            print(f"加载失败: {e}")
            return False
    
    def _serialize(self) -> dict:
        """序列化"""
        def _serialize(entry):
            if entry.is_file():
                return {
                    'type': 'file',
                    'name': entry.name,
                    'content': entry._content,
                    'created': entry.created,
                    'modified': entry.modified,
                }
            else:
                children = {}
                for name, child in entry._entries.items():
                    children[name] = _serialize(child)
                return {
                    'type': 'dir',
                    'name': entry.name,
                    'children': children,
                    'created': entry.created,
                    'modified': entry.modified,
                }
        
        return {
            'root': _serialize(self.root),
            'cwd_path': self.cwd.get_path()
        }
    
    def _deserialize(self, state: dict):
        """反序列化"""
        def _deserialize(data, parent=None):
            if data['type'] == 'file':
                entry = File(data['name'], parent, data['content'])
                entry.created = data['created']
                entry.modified = data['modified']
                return entry
            else:
                entry = Directory(data['name'], parent)
                entry.created = data['created']
                entry.modified = data['modified']
                for name, child_data in data['children'].items():
                    child = _deserialize(child_data, entry)
                    entry._entries[name] = child
                return entry
        
        self.root = _deserialize(state['root'])
        self.cwd = self.root
        if state['cwd_path'] != '/':
            try:
                resolver = PathResolver(self.root, self.root)
                self.cwd = resolver.resolve(state['cwd_path'])
            except:
                pass