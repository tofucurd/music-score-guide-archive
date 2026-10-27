"""Prevent silent renderer/toolchain changes across resumed chunks."""
import sys,subprocess,platform
from importlib.metadata import version
CHROME='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
def runtime_environment():
 commands={'python':[sys.executable,'--version'],'node':['node','--version'],'ffmpeg':['ffmpeg','-version'],'ffprobe':['ffprobe','-version'],'chrome':[CHROME,'--version']}
 result={k:subprocess.check_output(v,text=True).splitlines()[0] for k,v in commands.items()}
 result['os']=platform.platform();result['python_packages']={name:version(name) for name in ['numpy','scipy','Pillow']}
 return result
