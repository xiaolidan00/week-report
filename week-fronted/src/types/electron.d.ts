/** 渲染进程可见的 Electron 主进程 API（纯浏览器环境不存在） */
interface ElectronApi {
  /** 打开原生目录选择框，返回绝对路径；取消返回 null */
  selectFolder(): Promise<string | null>
}

interface Window {
  electronApi?: ElectronApi
}
