#!/usr/bin/env python3
"""
打包脚本：一键将 gui.py 打包为 .exe
用法: python build.py
"""
import os
import sys
import shutil
import subprocess
import glob

def run(cmd, check=True):
    """执行命令并打印输出"""
    print(f"\n>>> {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    if check and result.returncode != 0:
        print(f"命令失败，退出码: {result.returncode}")
        sys.exit(1)
    return result

def main():
    print("=" * 50)
    print("  同声传译 - 打包为 .exe")
    print("=" * 50)

    # 1. 检查 PyInstaller
    print("\n[1/5] 检查 PyInstaller...")
    result = subprocess.run(["pyinstaller", "--version"], capture_output=True, text=True)
    if result.returncode != 0:
        print("PyInstaller 未安装，正在安装...")
        run([sys.executable, "-m", "pip", "install", "pyinstaller"])
    else:
        print(f"PyInstaller 已安装: {result.stdout.strip()}")

    # 2. 清理旧构建
    print("\n[2/5] 清理旧构建...")
    for path in ["build", "dist"]:
        if os.path.isdir(path):
            shutil.rmtree(path)
            print(f"  删除 {path}/")
    for f in glob.glob("*.spec"):
        os.remove(f)
        print(f"  删除 {f}")

    # 3. 找到 webrtcvad 文件路径
    print("\n[3/5] 定位 webrtcvad 文件...")
    import webrtcvad
    site_packages = os.path.dirname(webrtcvad.__file__)
    pyd_file = os.path.join(site_packages, "_webrtcvad.cp311-win_amd64.pyd")
    py_file = os.path.join(site_packages, "webrtcvad.py")

    if not os.path.exists(pyd_file):
        pyd_files = glob.glob(os.path.join(site_packages, "_webrtcvad*.pyd"))
        if pyd_files:
            pyd_file = pyd_files[0]
        else:
            print(f"错误: 找不到 _webrtcvad*.pyd 文件")
            sys.exit(1)

    print(f"  .pyd: {pyd_file}")
    print(f"  .py:  {py_file}")

    # 3.5 显式创建 build 目录，避免 PyInstaller 找不到路径
    build_dir = os.path.join("build", "VoiceTranslator")
    os.makedirs(build_dir, exist_ok=True)
    print(f"  创建目录: {build_dir}")

    # 4. 打包
    print("\n[4/5] 开始打包...")
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name", "VoiceTranslator",
        "--add-binary", f"{pyd_file};.",
        "--add-data", f"{py_file};.",
        "--hidden-import", "webrtcvad",
        "--collect-all", "faster_whisper",
        "--collect-all", "transformers",
        "gui.py"
    ]
    run(cmd)

    # 5. 复制资源
    print("\n[5/5] 复制资源文件...")
    dist_dir = os.path.join("dist", "VoiceTranslator")

    for src in ["voices", "piper"]:
        if os.path.exists(src):
            dst = os.path.join(dist_dir, src)
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            print(f"  复制 {src}/ -> {dst}")
        else:
            print(f"  [警告] {src}/ 不存在，跳过")

    if os.path.exists("settings.json"):
        shutil.copy2("settings.json", dist_dir)
        print(f"  复制 settings.json")

    print("\n" + "=" * 50)
    print("  打包完成!")
    print(f"  输出目录: {os.path.abspath(dist_dir)}")
    print(f"  可执行文件: {os.path.join(dist_dir, 'VoiceTranslator.exe')}")
    print("\n  提示:")
    print("  - 首次运行需要下载模型（约 4GB），请保持联网")
    print("  - 运行时请以管理员身份运行，否则快捷键无效")
    print("  - 如果被杀毒软件删除，请在 Windows 安全中心添加排除项")
    print("=" * 50)

    input("\n按 Enter 退出...")

if __name__ == "__main__":
    main()
