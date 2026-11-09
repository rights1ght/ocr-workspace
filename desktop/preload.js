// Мост окно → main: статус движка без доступа к node/сети у рендерера.
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("engine", {
  status: () => ipcRenderer.invoke("engine-status"),
  onReady: (cb) => ipcRenderer.on("engine-ready", (_e, ok) => cb(ok)),
});
