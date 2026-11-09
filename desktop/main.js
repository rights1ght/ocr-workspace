// OCR Workspace — обёртка Electron (Task 8, ТЗ §10.2).
//
// Жизненный цикл: обёртка запускает backend (uvicorn, 127.0.0.1:8765),
// ждёт /health и грузит prod-сборку фронтенда прямо из FastAPI-статики.
// При закрытии окна: SIGTERM → backend корректно завершается; через 5 с SIGKILL.
//
// Примечание: на этапе 1 llama-server не нужен (OCR сканов — этап 2);
// движок стартует лениво при первом «Обработать» скан-документа.

const { app, BrowserWindow, dialog, ipcMain } = require("electron");
const { spawn, execSync } = require("child_process");
const path = require("path");
const http = require("http");

const BACKEND_DIR = path.join(__dirname, "..", "backend");
const VENV_PY = path.join(__dirname, "..", "spike", ".venv", "bin", "python");
const SERVER_URL = "http://127.0.0.1:8765";
const HEALTH_TIMEOUT_MS = 30_000;

let serverProc = null;
let win = null;
let shuttingDown = false;

function healthCheck() {
  return new Promise((resolve) => {
    const req = http.get(`${SERVER_URL}/health`, { timeout: 2000 }, (res) => {
      res.resume();
      resolve(res.statusCode === 200);
    });
    req.on("error", () => resolve(false));
    req.on("timeout", () => {
      req.destroy();
      resolve(false);
    });
  });
}

function procsAlive(pid) {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

// Если backend висит на порту, но запущен вне обёртки, — прибираем его,
// чтобы жизненный цикл принадлежал нам.
function killOrphanBackend() {
  try {
    const out = execSync("pgrep -f 'uvicorn app.main:app'", { encoding: "utf8" });
    if (out.trim()) {
      console.log("[shell] найден работающий backend, останавливаю:", out.trim().split("\n").join(", "));
      try { execSync("pkill -TERM -f 'uvicorn app.main:app'"); } catch { /* уже умер */ }
    }
  } catch {
    // pgrep ничего не нашёл — норма
  }
}

function startBackend() {
  killOrphanBackend();
  console.log("[shell] запускаю backend (uvicorn :8765)…");
  serverProc = spawn(VENV_PY, ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8765"], {
    cwd: BACKEND_DIR,
    stdio: ["ignore", "pipe", "pipe"],
  });
  serverProc.stdout.on("data", (d) => process.stdout.write("[api] " + d));
  serverProc.stderr.on("data", (d) => process.stderr.write("[api] " + d));
  serverProc.on("exit", (code) => {
    console.log(`[shell] backend завершился (code=${code})`);
    if (!shuttingDown) {
      shuttingDown = true;
      app.quit(); // backend умер сам — окно не нужно
    }
  });
}

async function waitBackend() {
  const t1 = Date.now();
  while (Date.now() - t1 < HEALTH_TIMEOUT_MS) {
    if (await healthCheck()) {
      console.log(`[shell] backend готов за ${((Date.now() - t1) / 1000).toFixed(1)} с`);
      return true;
    }
    if (!procsAlive(serverProc.pid)) return false;
    await new Promise((r) => setTimeout(r, 250));
  }
  return false;
}

async function stopServer() {
  shuttingDown = true;
  if (!serverProc || serverProc.exitCode !== null) return;
  console.log("[shell] останавливаю backend (SIGTERM)…");
  const pid = serverProc.pid;
  try { process.kill(pid, "SIGTERM"); } catch { /* уже умер */ }

  for (let i = 0; i < 50; i++) {
    if (!procsAlive(pid)) {
      console.log("[shell] backend остановлен, порт свободен");
      return;
    }
    await new Promise((r) => setTimeout(r, 100));
  }
  try { process.kill(pid, "SIGKILL"); console.log("[shell] SIGKILL после 5 с ожидания"); } catch {}
}

function createWindow() {
  win = new BrowserWindow({
    width: 1180,
    height: 780,
    title: "OCR Workspace",
    show: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, "preload.js"),
    },
  });
  win.loadURL(SERVER_URL);
  win.once("ready-to-show", () => win.show());
  win.on("closed", () => { win = null; });
}

ipcMain.handle("engine-status", () => ({
  running: serverProc !== null && serverProc.exitCode === null,
  pid: serverProc && serverProc.exitCode === null ? serverProc.pid : null,
}));

app.whenReady().then(async () => {
  createWindow();
  startBackend();
  const ok = await waitBackend();
  if (!ok) {
    dialog.showErrorBox("OCR Workspace", "Не удалось запустить backend. См. вывод в терминале.");
    app.quit();
    return;
  }
  if (win && !win.isDestroyed()) {
    win.loadURL(SERVER_URL); // health_ok → грузим интерфейс
  }
});

// Закрытие окна → полный выход → stopServer()
app.on("window-all-closed", () => app.quit());
app.on("before-quit", async (e) => {
  if (shuttingDown) return;
  shuttingDown = true;
  e.preventDefault();
  await stopServer();
  app.exit(0);
});
process.on("SIGINT", () => { stopServer().finally(() => app.exit(0)); });
process.on("SIGTERM", () => { stopServer().finally(() => app.exit(0)); });
