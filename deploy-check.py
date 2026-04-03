#!/usr/bin/env python3
"""
部署前检查脚本
检查环境、依赖、配置等
"""
import os
import sys
import subprocess
from pathlib import Path


class DeploymentChecker:
    """部署检查器"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.errors = []
        self.warnings = []
        self.success = []
    
    def run(self):
        """运行所有检查"""
        print("🔍 开始部署前检查...\n")
        
        self.check_python_version()
        self.check_dependencies()
        self.check_env_file()
        self.check_directories()
        self.check_permissions()
        self.check_config_values()
        
        self.print_report()
        return len(self.errors) == 0
    
    def check_python_version(self):
        """检查 Python 版本"""
        version = sys.version_info
        if version.major >= 3 and version.minor >= 8:
            self.success.append(f"✅ Python 版本: {version.major}.{version.minor}.{version.micro}")
        else:
            self.errors.append(f"❌ Python 版本过低: {version.major}.{version.minor} (需要 3.8+)")
    
    def check_dependencies(self):
        """检查依赖包"""
        requirements_file = self.project_root / 'requirements.txt'
        
        if not requirements_file.exists():
            self.errors.append("❌ 找不到 requirements.txt")
            return
        
        try:
            result = subprocess.run(
                ['pip', 'list', '--format=json'],
                capture_output=True,
                text=True,
                timeout=10
            )
            installed = {pkg['name'].lower() for pkg in __import__('json').loads(result.stdout)}
            
            required = []
            with open(requirements_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        pkg_name = line.split('>=')[0].split('==')[0].split('<')[0].lower()
                        required.append(pkg_name)
            
            missing = [pkg for pkg in required if pkg not in installed]
            
            if missing:
                self.warnings.append(f"⚠️  缺少依赖: {', '.join(missing)}")
                self.warnings.append("   运行: pip install -r requirements.txt")
            else:
                self.success.append("✅ 所有依赖已安装")
        
        except Exception as e:
            self.warnings.append(f"⚠️  无法检查依赖: {e}")
    
    def check_env_file(self):
        """检查 .env 文件"""
        env_file = self.project_root / '.env'
        env_example = self.project_root / '.env.example'
        
        if not env_file.exists():
            self.errors.append("❌ 缺少 .env 文件")
            if env_example.exists():
                self.errors.append("   运行: cp .env.example .env")
            return
        
        self.success.append("✅ .env 文件存在")
    
    def check_directories(self):
        """检查必要的目录"""
        dirs_to_check = [
            'core',
            'handlers',
            'api',
            'services',
        ]
        
        missing = []
        for dir_name in dirs_to_check:
            dir_path = self.project_root / dir_name
            if not dir_path.exists():
                missing.append(dir_name)
        
        if missing:
            self.errors.append(f"❌ 缺少目录: {', '.join(missing)}")
        else:
            self.success.append("✅ 所有必要目录存在")
    
    def check_permissions(self):
        """检查文件权限"""
        main_py = self.project_root / 'main.py'
        
        if main_py.exists():
            if os.access(main_py, os.X_OK):
                self.success.append("✅ main.py 可执行")
            else:
                self.warnings.append("⚠️  main.py 不可执行")
                self.warnings.append("   运行: chmod +x main.py")
    
    def check_config_values(self):
        """检查配置值"""
        env_file = self.project_root / '.env'
        
        if not env_file.exists():
            return
        
        required_keys = [
            'TG_BOT_TOKEN',
            'TG_ADMIN_UID',
            'NODESEEK_COOKIES',
            'NODESEEK_ADMIN_UID',
        ]
        
        with open(env_file) as f:
            content = f.read()
        
        missing_keys = []
        placeholder_keys = []
        
        for key in required_keys:
            if key not in content:
                missing_keys.append(key)
            elif f'{key}=your_' in content or f'{key}=' in content and content.split(f'{key}=')[1].split('\n')[0].strip() in ['', 'your_bot_token_here', 'your_telegram_id_here', 'your_cookies_here', 'your_nodeseek_uid_here']:
                placeholder_keys.append(key)
        
        if missing_keys:
            self.errors.append(f"❌ 缺少必要配置: {', '.join(missing_keys)}")
        
        if placeholder_keys:
            self.warnings.append(f"⚠️  配置值未填写: {', '.join(placeholder_keys)}")
        
        if not missing_keys and not placeholder_keys:
            self.success.append("✅ 所有必要配置已填写")
    
    def print_report(self):
        """打印检查报告"""
        print("\n" + "="*50)
        
        if self.success:
            print("\n✅ 成功检查:")
            for msg in self.success:
                print(f"  {msg}")
        
        if self.warnings:
            print("\n⚠️  警告:")
            for msg in self.warnings:
                print(f"  {msg}")
        
        if self.errors:
            print("\n❌ 错误:")
            for msg in self.errors:
                print(f"  {msg}")
        
        print("\n" + "="*50)
        
        if self.errors:
            print("\n❌ 部署检查失败，请修复上述错误后重试")
            return False
        elif self.warnings:
            print("\n⚠️  部署检查完成，但有警告需要注意")
            return True
        else:
            print("\n✅ 部署检查通过，可以开始部署了！")
            return True


if __name__ == '__main__':
    checker = DeploymentChecker()
    success = checker.run()
    sys.exit(0 if success else 1)
